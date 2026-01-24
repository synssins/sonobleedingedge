"""
Home Assistant Addon Settings.

Loads configuration from HA addon options.
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MQTTSettings:
    """MQTT connection settings from HA."""
    enabled: bool = True
    host: str = "core-mosquitto"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    topic_prefix: str = "sonorium"
    discovery_prefix: str = "homeassistant"


@dataclass
class HASettings:
    """Settings loaded from Home Assistant addon options."""

    # Web server
    port: int = 8008

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

    @classmethod
    def load(cls) -> "HASettings":
        """Load settings from HA addon options."""
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
    def _from_options(cls, options: dict) -> "HASettings":
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
            mqtt=mqtt,
            discovery_interval=options.get("discovery_interval", 300),
            default_volume=options.get("default_volume", 0.8),
            themes_path=Path(themes_path),
        )

    @classmethod
    def _from_env(cls) -> "HASettings":
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
            mqtt=mqtt,
            discovery_interval=int(os.environ.get("DISCOVERY_INTERVAL", "300")),
            default_volume=float(os.environ.get("DEFAULT_VOLUME", "0.8")),
        )
