"""
MQTT Bridge.

Provides full control of Sonorium via MQTT topics.
Enables integration with Node-RED, Home Assistant, and other automation systems.

Control Topics (subscribe):
    sonorium/speakers/{id}/set          - Enable/disable/volume for speaker
    sonorium/speakers/all/set           - Enable/disable all speakers
    sonorium/sessions/set               - Create/stop sessions
    sonorium/sessions/{id}/set          - Update specific session
    sonorium/settings/set               - Update settings
    sonorium/command                    - Execute commands

State Topics (publish):
    sonorium/status                     - Overall status
    sonorium/speakers/state             - All speakers state
    sonorium/speakers/{id}/state        - Individual speaker state
    sonorium/sessions/state             - All sessions state
    sonorium/themes/state               - Available themes
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Any

from ..models import MQTTSettings, Speaker, Session
from .state import get_state_manager, StateManager

logger = logging.getLogger(__name__)

# Global MQTT bridge instance
_mqtt_bridge: Optional["MQTTBridge"] = None


class MQTTBridge:
    """
    MQTT bridge for Sonorium control and state publishing.

    Subscribes to control topics and publishes state changes.
    """

    def __init__(self, settings: MQTTSettings):
        self.settings = settings
        self.prefix = settings.topic_prefix
        self._client = None
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._unsubscribe_state: Optional[Callable] = None

    @property
    def connected(self) -> bool:
        return self._connected

    # ─────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            import paho.mqtt.client as mqtt

            self._loop = asyncio.get_event_loop()
            self._client = mqtt.Client(
                client_id=self.settings.client_id,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Set credentials if provided
            if self.settings.username:
                self._client.username_pw_set(
                    self.settings.username,
                    self.settings.password
                )

            # Connect
            self._client.connect_async(
                self.settings.host,
                self.settings.port,
                keepalive=60
            )

            # Start network loop in background
            self._client.loop_start()

            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self._connected:
                    return True
                await asyncio.sleep(0.1)

            logger.warning("MQTT connection timeout")
            return False

        except ImportError:
            logger.error("paho-mqtt not installed")
            return False
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._unsubscribe_state:
            self._unsubscribe_state()

        if self._client:
            # Publish offline status
            self._publish(f"{self.prefix}/status", {"state": "offline"})

            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False

        logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Called when connected to broker."""
        if rc == 0:
            logger.info(f"MQTT connected to {self.settings.host}:{self.settings.port}")
            self._connected = True
            self._subscribe_topics()
            self._setup_state_listener()

            # Publish online status
            self._publish(f"{self.prefix}/status", {
                "state": "online",
                "version": "0.1.0"
            }, retain=True)

            # Publish initial state
            asyncio.run_coroutine_threadsafe(
                self._publish_full_state(),
                self._loop
            )
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc, properties=None, reasonCode=None):
        """Called when disconnected from broker."""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnect: {rc}")

    def _subscribe_topics(self):
        """Subscribe to control topics."""
        topics = [
            (f"{self.prefix}/speakers/+/set", 1),
            (f"{self.prefix}/speakers/all/set", 1),
            (f"{self.prefix}/sessions/set", 1),
            (f"{self.prefix}/sessions/+/set", 1),
            (f"{self.prefix}/settings/set", 1),
            (f"{self.prefix}/command", 1),
        ]
        for topic, qos in topics:
            self._client.subscribe(topic, qos)
            logger.debug(f"Subscribed to {topic}")

    def _setup_state_listener(self):
        """Subscribe to state changes for publishing."""
        manager = get_state_manager()
        self._unsubscribe_state = manager.on_change(self._on_state_change)

    def _on_state_change(self, state, key: str):
        """Called when state changes - publish updates."""
        if not self._connected:
            return

        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._publish_state_update(key),
                self._loop
            )

    # ─────────────────────────────────────────────────────────────
    # Message Handling
    # ─────────────────────────────────────────────────────────────

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages."""
        try:
            topic = message.topic
            payload = json.loads(message.payload.decode()) if message.payload else {}

            logger.debug(f"MQTT message: {topic} -> {payload}")

            # Route to appropriate handler
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._handle_message(topic, payload),
                    self._loop
                )

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in MQTT message: {message.payload}")
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")

    async def _handle_message(self, topic: str, payload: dict):
        """Route message to appropriate handler."""
        manager = get_state_manager()

        # Parse topic
        parts = topic.replace(self.prefix + "/", "").split("/")

        if parts[0] == "speakers":
            await self._handle_speaker_command(parts, payload, manager)
        elif parts[0] == "sessions":
            await self._handle_session_command(parts, payload, manager)
        elif parts[0] == "settings":
            await self._handle_settings_command(payload, manager)
        elif parts[0] == "command":
            await self._handle_command(payload, manager)

    async def _handle_speaker_command(self, parts: list, payload: dict, manager: StateManager):
        """Handle speaker control commands."""
        if len(parts) >= 3 and parts[2] == "set":
            speaker_id = parts[1]

            if speaker_id == "all":
                # Control all speakers
                if payload.get("enabled") is True:
                    manager.enable_all_speakers()
                    logger.info("MQTT: Enabled all speakers")
                elif payload.get("enabled") is False:
                    # Stop all sessions first
                    for session in manager.get_active_sessions():
                        session.mark_stopped()
                    manager.disable_all_speakers()
                    logger.info("MQTT: Disabled all speakers")
            else:
                # Control specific speaker
                if "enabled" in payload:
                    if payload["enabled"]:
                        manager.enable_speaker(speaker_id)
                        logger.info(f"MQTT: Enabled speaker {speaker_id}")
                    else:
                        # Stop sessions for this speaker
                        for session in manager.get_sessions_for_speaker(speaker_id):
                            session.remove_speaker(speaker_id)
                            if not session.speakers:
                                session.mark_stopped()
                        manager.disable_speaker(speaker_id)
                        logger.info(f"MQTT: Disabled speaker {speaker_id}")

                if "volume" in payload:
                    manager.set_speaker_volume(speaker_id, payload["volume"])
                    logger.info(f"MQTT: Set speaker {speaker_id} volume to {payload['volume']}")

    async def _handle_session_command(self, parts: list, payload: dict, manager: StateManager):
        """Handle session control commands."""
        if len(parts) >= 2 and parts[1] == "set":
            # Create new session
            if "theme" in payload and "speakers" in payload:
                from ..models import Session
                session = Session.create(
                    theme_id=payload["theme"],
                    speaker_ids=payload["speakers"]
                )
                session.volume = payload.get("volume", 1.0)
                manager.add_session(session)
                session.mark_started()
                logger.info(f"MQTT: Created session {session.id}")

        elif len(parts) >= 3 and parts[2] == "set":
            # Update existing session
            session_id = parts[1]
            session = manager.get_session(session_id)
            if session:
                if payload.get("action") == "stop":
                    session.mark_stopped()
                    logger.info(f"MQTT: Stopped session {session_id}")
                if "volume" in payload:
                    session.volume = payload["volume"]
                if "muted" in payload:
                    session.muted = payload["muted"]

    async def _handle_settings_command(self, payload: dict, manager: StateManager):
        """Handle settings update commands."""
        updates = {}
        if "master_volume" in payload:
            updates["master_volume"] = payload["master_volume"]
        if updates:
            manager.update_settings(**updates)
            logger.info(f"MQTT: Updated settings: {updates}")

    async def _handle_command(self, payload: dict, manager: StateManager):
        """Handle generic commands."""
        action = payload.get("action", "")

        if action == "discover_speakers":
            # TODO: Trigger discovery via plugin manager
            logger.info("MQTT: Speaker discovery triggered")

        elif action == "scan_themes":
            # TODO: Trigger theme scan
            logger.info("MQTT: Theme scan triggered")

        elif action == "stop_all":
            for session in manager.get_active_sessions():
                session.mark_stopped()
            logger.info("MQTT: Stopped all sessions")

    # ─────────────────────────────────────────────────────────────
    # State Publishing
    # ─────────────────────────────────────────────────────────────

    def _publish(self, topic: str, payload: Any, retain: bool = False):
        """Publish message to MQTT."""
        if self._client and self._connected:
            msg = json.dumps(payload)
            self._client.publish(topic, msg, retain=retain)

    async def _publish_full_state(self):
        """Publish complete state to MQTT."""
        manager = get_state_manager()
        state = manager.state

        # Publish speakers
        speakers_data = {sid: s.to_dict() for sid, s in state.speakers.items()}
        self._publish(f"{self.prefix}/speakers/state", speakers_data, retain=True)

        # Publish individual speaker states
        for speaker_id, speaker in state.speakers.items():
            self._publish(
                f"{self.prefix}/speakers/{speaker_id}/state",
                speaker.to_dict(),
                retain=True
            )

        # Publish sessions
        sessions_data = {sid: s.to_dict() for sid, s in state.sessions.items() if s.is_active}
        self._publish(f"{self.prefix}/sessions/state", sessions_data, retain=True)

        # Publish themes
        themes_data = {tid: t.to_dict() for tid, t in state.themes.items()}
        self._publish(f"{self.prefix}/themes/state", themes_data, retain=True)

        logger.debug("Published full state to MQTT")

    async def _publish_state_update(self, key: str):
        """Publish state update for specific key."""
        manager = get_state_manager()
        state = manager.state

        if key == "speakers":
            speakers_data = {sid: s.to_dict() for sid, s in state.speakers.items()}
            self._publish(f"{self.prefix}/speakers/state", speakers_data, retain=True)

            # Also publish individual states
            for speaker_id, speaker in state.speakers.items():
                self._publish(
                    f"{self.prefix}/speakers/{speaker_id}/state",
                    speaker.to_dict(),
                    retain=True
                )

        elif key == "sessions":
            sessions_data = {sid: s.to_dict() for sid, s in state.sessions.items() if s.is_active}
            self._publish(f"{self.prefix}/sessions/state", sessions_data, retain=True)

        elif key == "themes":
            themes_data = {tid: t.to_dict() for tid, t in state.themes.items()}
            self._publish(f"{self.prefix}/themes/state", themes_data, retain=True)

        elif key == "settings":
            self._publish(
                f"{self.prefix}/settings/state",
                state.settings.to_dict(),
                retain=True
            )

    # ─────────────────────────────────────────────────────────────
    # Home Assistant Discovery
    # ─────────────────────────────────────────────────────────────

    async def publish_ha_discovery(self):
        """Publish Home Assistant MQTT discovery messages."""
        if not self.settings.ha_discovery_enabled:
            return

        manager = get_state_manager()
        prefix = self.settings.ha_discovery_prefix

        # Publish Sonorium status sensor
        self._publish(
            f"{prefix}/sensor/sonorium_status/config",
            {
                "name": "Sonorium Status",
                "unique_id": "sonorium_status",
                "state_topic": f"{self.prefix}/status",
                "value_template": "{{ value_json.state }}",
                "icon": "mdi:speaker-multiple",
                "device": {
                    "identifiers": ["sonorium"],
                    "name": "Sonorium",
                    "model": "Ambient Soundscape Mixer",
                    "manufacturer": "Sonorium",
                }
            },
            retain=True
        )

        # Publish speaker switches
        for speaker_id, speaker in manager.state.speakers.items():
            safe_id = speaker_id.replace("-", "_").replace(":", "_")

            self._publish(
                f"{prefix}/switch/sonorium_{safe_id}/config",
                {
                    "name": f"Sonorium {speaker.name}",
                    "unique_id": f"sonorium_speaker_{safe_id}",
                    "state_topic": f"{self.prefix}/speakers/{speaker_id}/state",
                    "command_topic": f"{self.prefix}/speakers/{speaker_id}/set",
                    "value_template": "{{ 'ON' if value_json.enabled else 'OFF' }}",
                    "payload_on": '{"enabled": true}',
                    "payload_off": '{"enabled": false}',
                    "icon": "mdi:speaker",
                    "device": {
                        "identifiers": ["sonorium"],
                        "name": "Sonorium",
                    }
                },
                retain=True
            )

        logger.info("Published Home Assistant MQTT discovery")


# ─────────────────────────────────────────────────────────────────────
# Module-level functions
# ─────────────────────────────────────────────────────────────────────

async def init_mqtt_bridge(settings: MQTTSettings) -> Optional[MQTTBridge]:
    """Initialize the global MQTT bridge."""
    global _mqtt_bridge

    if not settings.enabled:
        logger.info("MQTT disabled")
        return None

    _mqtt_bridge = MQTTBridge(settings)
    if await _mqtt_bridge.connect():
        # Publish HA discovery
        await _mqtt_bridge.publish_ha_discovery()
        return _mqtt_bridge

    _mqtt_bridge = None
    return None


async def stop_mqtt_bridge():
    """Stop the global MQTT bridge."""
    global _mqtt_bridge
    if _mqtt_bridge:
        await _mqtt_bridge.disconnect()
        _mqtt_bridge = None


def get_mqtt_bridge() -> Optional[MQTTBridge]:
    """Get the global MQTT bridge instance."""
    return _mqtt_bridge
