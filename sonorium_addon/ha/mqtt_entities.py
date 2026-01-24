"""
MQTT Entity Exposure for Home Assistant.

Exposes Sonorium entities to HA via MQTT Discovery.
"""

import json
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class MQTTDiscoveryConfig:
    """MQTT Discovery configuration for HA entity auto-discovery."""
    discovery_prefix: str = "homeassistant"
    node_id: str = "sonorium"
    device_info: dict = None

    def __post_init__(self):
        if self.device_info is None:
            self.device_info = {
                "identifiers": ["sonorium"],
                "name": "Sonorium",
                "manufacturer": "Sonorium",
                "model": "Ambient Sound System",
                "sw_version": "0.1.0",
            }


class MQTTEntityExposer:
    """Exposes Sonorium entities to Home Assistant via MQTT Discovery."""

    def __init__(self, config: MQTTDiscoveryConfig):
        """Initialize with discovery configuration."""
        self.config = config
        self._published_entities: set[str] = set()

    def _discovery_topic(self, component: str, object_id: str) -> str:
        """Build MQTT discovery topic."""
        return f"{self.config.discovery_prefix}/{component}/{self.config.node_id}/{object_id}/config"

    def _build_base_config(self, name: str, object_id: str) -> dict:
        """Build base configuration shared by all entities."""
        return {
            "name": name,
            "unique_id": f"sonorium_{object_id}",
            "device": self.config.device_info,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Speaker Entities
    # ─────────────────────────────────────────────────────────────────────────

    def speaker_switch_config(self, speaker_id: str, speaker_name: str, topic_prefix: str) -> tuple[str, dict]:
        """Generate switch config for speaker enable/disable."""
        object_id = f"speaker_{speaker_id}_enabled"
        config = self._build_base_config(f"{speaker_name} Enabled", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/speakers/{speaker_id}/enabled/set",
            "state_topic": f"{topic_prefix}/speakers/{speaker_id}/enabled",
            "payload_on": "true",
            "payload_off": "false",
            "icon": "mdi:speaker",
        })
        return self._discovery_topic("switch", object_id), config

    def speaker_volume_config(self, speaker_id: str, speaker_name: str, topic_prefix: str) -> tuple[str, dict]:
        """Generate number config for speaker volume."""
        object_id = f"speaker_{speaker_id}_volume"
        config = self._build_base_config(f"{speaker_name} Volume", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/speakers/{speaker_id}/volume/set",
            "state_topic": f"{topic_prefix}/speakers/{speaker_id}/volume",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:volume-high",
        })
        return self._discovery_topic("number", object_id), config

    # ─────────────────────────────────────────────────────────────────────────
    # Session Entities
    # ─────────────────────────────────────────────────────────────────────────

    def session_sensor_config(self, session_id: str, theme_name: str, topic_prefix: str) -> tuple[str, dict]:
        """Generate sensor config for active session."""
        object_id = f"session_{session_id}"
        config = self._build_base_config(f"Session: {theme_name}", object_id)
        config.update({
            "state_topic": f"{topic_prefix}/sessions/{session_id}/state",
            "json_attributes_topic": f"{topic_prefix}/sessions/{session_id}/attributes",
            "icon": "mdi:music",
        })
        return self._discovery_topic("sensor", object_id), config

    def session_volume_config(self, session_id: str, theme_name: str, topic_prefix: str) -> tuple[str, dict]:
        """Generate number config for session volume."""
        object_id = f"session_{session_id}_volume"
        config = self._build_base_config(f"{theme_name} Volume", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/sessions/{session_id}/volume/set",
            "state_topic": f"{topic_prefix}/sessions/{session_id}/volume",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:volume-high",
        })
        return self._discovery_topic("number", object_id), config

    # ─────────────────────────────────────────────────────────────────────────
    # Global Entities
    # ─────────────────────────────────────────────────────────────────────────

    def master_volume_config(self, topic_prefix: str) -> tuple[str, dict]:
        """Generate number config for master volume."""
        object_id = "master_volume"
        config = self._build_base_config("Master Volume", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/master/volume/set",
            "state_topic": f"{topic_prefix}/master/volume",
            "min": 0,
            "max": 100,
            "step": 1,
            "unit_of_measurement": "%",
            "icon": "mdi:volume-high",
        })
        return self._discovery_topic("number", object_id), config

    def stop_all_button_config(self, topic_prefix: str) -> tuple[str, dict]:
        """Generate button config for stop all."""
        object_id = "stop_all"
        config = self._build_base_config("Stop All", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/command",
            "payload_press": "stop_all",
            "icon": "mdi:stop",
        })
        return self._discovery_topic("button", object_id), config

    # ─────────────────────────────────────────────────────────────────────────
    # Theme Entities
    # ─────────────────────────────────────────────────────────────────────────

    def theme_select_config(self, themes: list[dict], topic_prefix: str) -> tuple[str, dict]:
        """Generate select config for theme selection."""
        object_id = "theme_select"
        config = self._build_base_config("Select Theme", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/theme/select/set",
            "state_topic": f"{topic_prefix}/theme/select",
            "options": [t.get("name", t.get("id", "Unknown")) for t in themes],
            "icon": "mdi:music-box-multiple",
        })
        return self._discovery_topic("select", object_id), config

    def theme_play_button_config(self, topic_prefix: str) -> tuple[str, dict]:
        """Generate button config for playing selected theme."""
        object_id = "theme_play"
        config = self._build_base_config("Play Theme", object_id)
        config.update({
            "command_topic": f"{topic_prefix}/theme/play",
            "payload_press": "play",
            "icon": "mdi:play",
        })
        return self._discovery_topic("button", object_id), config
