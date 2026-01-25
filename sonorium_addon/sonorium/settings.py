"""
Sonorium Settings Module

Provides centralized access to configuration settings.
Loads from HA addon options and environment variables.

ADDON CODE: This is specific to the Home Assistant addon deployment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MQTTSettings:
    """MQTT connection settings."""
    enabled: bool = True
    host: str = "core-mosquitto"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    topic_prefix: str = "sonorium"
    discovery_prefix: str = "homeassistant"


@dataclass
class Settings:
    """
    Sonorium addon settings.

    Provides access to configuration from:
    - HA addon options (/data/options.json)
    - Environment variables (SUPERVISOR_TOKEN, etc.)
    """

    # Web server
    port: int = 8008
    stream_port: int = 8008

    # Home Assistant API
    token: Optional[str] = None
    ha_supervisor_api: str = "http://supervisor/core"

    # MQTT
    mqtt: MQTTSettings = field(default_factory=MQTTSettings)

    # Discovery
    discovery_interval: int = 300

    # Audio
    default_volume: float = 0.8

    # Paths
    config_path: Path = field(default_factory=lambda: Path("/config"))
    data_path: Path = field(default_factory=lambda: Path("/data"))
    themes_path: Path = field(default_factory=lambda: Path("/config/sonorium/themes"))

    # Sonos IPs (manual override)
    sonos_ips: str = ""

    def __post_init__(self):
        """Load token from environment if not provided."""
        if self.token is None:
            self.token = os.environ.get("SUPERVISOR_TOKEN")

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from HA addon options and environment."""
        options_path = Path("/data/options.json")

        if options_path.exists():
            try:
                with open(options_path) as f:
                    options = json.load(f)
                return cls._from_options(options)
            except Exception as e:
                print(f"Failed to load options.json: {e}")

        # Fall back to environment variables
        return cls._from_env()

    @classmethod
    def _from_options(cls, options: dict) -> "Settings":
        """Create settings from addon options dict."""
        mqtt_opts = options.get("mqtt", {})
        mqtt = MQTTSettings(
            enabled=mqtt_opts.get("enabled", True),
            host=mqtt_opts.get("host", "core-mosquitto"),
            port=mqtt_opts.get("port", 1883),
            username=mqtt_opts.get("username"),
            password=mqtt_opts.get("password"),
            topic_prefix=mqtt_opts.get("topic_prefix", "sonorium"),
            discovery_prefix=mqtt_opts.get("discovery_prefix", "homeassistant"),
        )

        themes_path = options.get("themes_path", "/config/sonorium/themes")

        return cls(
            port=options.get("port", 8008),
            stream_port=options.get("stream_port", 8008),
            token=os.environ.get("SUPERVISOR_TOKEN"),
            ha_supervisor_api=os.environ.get("SUPERVISOR_URL", "http://supervisor/core"),
            mqtt=mqtt,
            discovery_interval=options.get("discovery_interval", 300),
            default_volume=options.get("default_volume", 0.8),
            themes_path=Path(themes_path),
            sonos_ips=options.get("sonos_ips", ""),
        )

    @classmethod
    def _from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        mqtt = MQTTSettings(
            enabled=os.environ.get("MQTT_ENABLED", "true").lower() == "true",
            host=os.environ.get("MQTT_HOST", "core-mosquitto"),
            port=int(os.environ.get("MQTT_PORT", "1883")),
            username=os.environ.get("MQTT_USERNAME"),
            password=os.environ.get("MQTT_PASSWORD"),
            topic_prefix=os.environ.get("MQTT_TOPIC_PREFIX", "sonorium"),
            discovery_prefix=os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant"),
        )

        return cls(
            port=int(os.environ.get("SONORIUM_PORT", "8008")),
            stream_port=int(os.environ.get("SONORIUM_STREAM_PORT", "8008")),
            token=os.environ.get("SUPERVISOR_TOKEN"),
            ha_supervisor_api=os.environ.get("SUPERVISOR_URL", "http://supervisor/core"),
            mqtt=mqtt,
            discovery_interval=int(os.environ.get("DISCOVERY_INTERVAL", "300")),
            default_volume=float(os.environ.get("DEFAULT_VOLUME", "0.8")),
            sonos_ips=os.environ.get("SONORIUM__SONOS_IPS", ""),
        )


# Global settings singleton
settings = Settings.load()


__all__ = ["Settings", "MQTTSettings", "settings"]
