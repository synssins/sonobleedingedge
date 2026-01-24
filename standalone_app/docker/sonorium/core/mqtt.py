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

CORE CODE: This module is shared across all platforms.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Callable, Any, TYPE_CHECKING

from ..models import MQTTSettings

if TYPE_CHECKING:
    from .state import StateStore

logger = logging.getLogger(__name__)

# Global MQTT bridge instance
_mqtt_bridge: Optional["MQTTBridge"] = None


class MQTTBridge:
    """
    MQTT bridge for Sonorium control and state publishing.

    Subscribes to control topics and publishes state changes.
    """

    def __init__(self, settings: MQTTSettings, state_store: Optional["StateStore"] = None):
        self.settings = settings
        self.prefix = settings.topic_prefix
        self._state_store = state_store
        self._client = None
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._unsubscribe_state: Optional[Callable] = None

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state_store(self) -> Optional["StateStore"]:
        return self._state_store

    @state_store.setter
    def state_store(self, value: Optional["StateStore"]):
        self._state_store = value

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

            # Publish online status
            self._publish(f"{self.prefix}/status", {
                "state": "online",
                "version": "0.2.0"
            }, retain=True)

            # Publish initial state
            if self._loop:
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
        if not self._state_store:
            logger.warning("No state store available for MQTT message handling")
            return

        # Parse topic
        parts = topic.replace(self.prefix + "/", "").split("/")

        if parts[0] == "speakers":
            await self._handle_speaker_command(parts, payload)
        elif parts[0] == "sessions":
            await self._handle_session_command(parts, payload)
        elif parts[0] == "settings":
            await self._handle_settings_command(payload)
        elif parts[0] == "command":
            await self._handle_command(payload)

    async def _handle_speaker_command(self, parts: list, payload: dict):
        """Handle speaker control commands."""
        if not self._state_store:
            return

        settings = self._state_store.settings

        if len(parts) >= 3 and parts[2] == "set":
            speaker_id = parts[1]

            if speaker_id == "all":
                # Control all speakers
                if payload.get("enabled") is True:
                    settings.enabled_speakers = []  # Empty = all enabled
                    logger.info("MQTT: Enabled all speakers")
                elif payload.get("enabled") is False:
                    settings.enabled_speakers = ["__none__"]  # Special value = none enabled
                    logger.info("MQTT: Disabled all speakers")
                self._state_store.save()
            else:
                # Control specific speaker
                if "enabled" in payload:
                    if payload["enabled"]:
                        # Enable speaker
                        if settings.enabled_speakers == ["__none__"]:
                            settings.enabled_speakers = [speaker_id]
                        elif speaker_id not in settings.enabled_speakers and settings.enabled_speakers:
                            settings.enabled_speakers.append(speaker_id)
                        logger.info(f"MQTT: Enabled speaker {speaker_id}")
                    else:
                        # Disable speaker
                        if speaker_id in settings.enabled_speakers:
                            settings.enabled_speakers.remove(speaker_id)
                        if not settings.enabled_speakers:
                            settings.enabled_speakers = ["__none__"]
                        logger.info(f"MQTT: Disabled speaker {speaker_id}")
                    self._state_store.save()

    async def _handle_session_command(self, parts: list, payload: dict):
        """Handle session control commands."""
        if not self._state_store:
            return

        if len(parts) >= 3 and parts[2] == "set":
            # Update existing session
            session_id = parts[1]
            session = self._state_store.sessions.get(session_id)
            if session:
                if payload.get("action") == "stop":
                    session.is_playing = False
                    self._state_store.save()
                    logger.info(f"MQTT: Stopped session {session_id}")
                if "volume" in payload:
                    session.volume = payload["volume"]
                    self._state_store.save()

    async def _handle_settings_command(self, payload: dict):
        """Handle settings update commands."""
        if not self._state_store:
            return

        settings = self._state_store.settings
        updated = False

        if "master_gain" in payload:
            settings.master_gain = payload["master_gain"]
            updated = True
        if "default_volume" in payload:
            settings.default_volume = payload["default_volume"]
            updated = True

        if updated:
            self._state_store.save()
            logger.info(f"MQTT: Updated settings")

    async def _handle_command(self, payload: dict):
        """Handle generic commands."""
        action = payload.get("action", "")

        if action == "stop_all":
            if self._state_store:
                for session in self._state_store.sessions.values():
                    if session.is_playing:
                        session.is_playing = False
                self._state_store.save()
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
        if not self._state_store:
            return

        # Publish sessions
        sessions_data = {
            sid: s.to_dict()
            for sid, s in self._state_store.sessions.items()
        }
        self._publish(f"{self.prefix}/sessions/state", sessions_data, retain=True)

        # Publish settings
        self._publish(
            f"{self.prefix}/settings/state",
            self._state_store.settings.to_dict(),
            retain=True
        )

        logger.debug("Published full state to MQTT")

    async def publish_session_state(self, session_id: str):
        """Publish state update for a specific session."""
        if not self._state_store:
            return

        session = self._state_store.sessions.get(session_id)
        if session:
            self._publish(
                f"{self.prefix}/sessions/{session_id}/state",
                session.to_dict(),
                retain=True
            )

    # ─────────────────────────────────────────────────────────────
    # Home Assistant Discovery
    # ─────────────────────────────────────────────────────────────

    async def publish_ha_discovery(self):
        """Publish Home Assistant MQTT discovery messages."""
        if not self.settings.ha_discovery_enabled:
            return

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

        logger.info("Published Home Assistant MQTT discovery")


# ─────────────────────────────────────────────────────────────────────
# Module-level functions
# ─────────────────────────────────────────────────────────────────────

async def init_mqtt_bridge(
    settings: MQTTSettings,
    state_store: Optional["StateStore"] = None
) -> Optional[MQTTBridge]:
    """Initialize the global MQTT bridge."""
    global _mqtt_bridge

    if not settings.enabled:
        logger.info("MQTT disabled")
        return None

    _mqtt_bridge = MQTTBridge(settings, state_store)
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
