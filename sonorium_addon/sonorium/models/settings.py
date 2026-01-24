"""
Settings data models.

Application settings and configuration.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class MQTTSettings:
    """MQTT connection settings."""
    enabled: bool = True
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    topic_prefix: str = "sonorium"
    client_id: str = "sonorium"

    # Home Assistant MQTT Discovery
    ha_discovery_enabled: bool = True
    ha_discovery_prefix: str = "homeassistant"

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "topic_prefix": self.topic_prefix,
            "client_id": self.client_id,
            "ha_discovery_enabled": self.ha_discovery_enabled,
            "ha_discovery_prefix": self.ha_discovery_prefix,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MQTTSettings":
        return cls(
            enabled=data.get("enabled", True),
            host=data.get("host", "localhost"),
            port=data.get("port", 1883),
            username=data.get("username"),
            password=data.get("password"),
            topic_prefix=data.get("topic_prefix", "sonorium"),
            client_id=data.get("client_id", "sonorium"),
            ha_discovery_enabled=data.get("ha_discovery_enabled", True),
            ha_discovery_prefix=data.get("ha_discovery_prefix", "homeassistant"),
        )


@dataclass
class DiscoverySettings:
    """Speaker discovery settings."""
    auto_discover: bool = True
    interval_seconds: int = 300         # How often to scan (5 minutes)
    enabled_protocols: list[str] = field(default_factory=lambda: [
        "sonos", "chromecast", "airplay", "dlna", "linkplay", "heos"
    ])
    timeout_seconds: int = 10           # Discovery timeout per protocol

    def to_dict(self) -> dict:
        return {
            "auto_discover": self.auto_discover,
            "interval_seconds": self.interval_seconds,
            "enabled_protocols": self.enabled_protocols,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiscoverySettings":
        return cls(
            auto_discover=data.get("auto_discover", True),
            interval_seconds=data.get("interval_seconds", 300),
            enabled_protocols=data.get("enabled_protocols", [
                "sonos", "chromecast", "airplay", "dlna", "linkplay", "heos"
            ]),
            timeout_seconds=data.get("timeout_seconds", 10),
        )


@dataclass
class AudioSettings:
    """Audio processing settings."""
    sample_rate: int = 44100
    channels: int = 2
    buffer_size: int = 4096
    crossfade_duration: float = 3.0     # Default crossfade between themes

    def to_dict(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "buffer_size": self.buffer_size,
            "crossfade_duration": self.crossfade_duration,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AudioSettings":
        return cls(
            sample_rate=data.get("sample_rate", 44100),
            channels=data.get("channels", 2),
            buffer_size=data.get("buffer_size", 4096),
            crossfade_duration=data.get("crossfade_duration", 3.0),
        )


@dataclass
class WebSettings:
    """Web server settings."""
    host: str = "0.0.0.0"
    port: int = 8099
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "cors_origins": self.cors_origins,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WebSettings":
        return cls(
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 8099),
            cors_origins=data.get("cors_origins", ["*"]),
        )


@dataclass
class Settings:
    """
    Application settings.

    Central configuration for all Sonorium components.
    """

    # General
    log_level: LogLevel = LogLevel.INFO
    data_dir: Optional[str] = None      # Data directory (themes, config)
    theme_dirs: list[str] = field(default_factory=list)  # Additional theme directories

    # Master volume
    master_volume: float = 0.8          # 0.0 - 1.0

    # Component settings
    mqtt: MQTTSettings = field(default_factory=MQTTSettings)
    discovery: DiscoverySettings = field(default_factory=DiscoverySettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    web: WebSettings = field(default_factory=WebSettings)

    def to_dict(self) -> dict:
        return {
            "log_level": self.log_level.value,
            "data_dir": self.data_dir,
            "theme_dirs": self.theme_dirs,
            "master_volume": self.master_volume,
            "mqtt": self.mqtt.to_dict(),
            "discovery": self.discovery.to_dict(),
            "audio": self.audio.to_dict(),
            "web": self.web.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        return cls(
            log_level=LogLevel(data.get("log_level", "info")),
            data_dir=data.get("data_dir"),
            theme_dirs=data.get("theme_dirs", []),
            master_volume=data.get("master_volume", 0.8),
            mqtt=MQTTSettings.from_dict(data.get("mqtt", {})),
            discovery=DiscoverySettings.from_dict(data.get("discovery", {})),
            audio=AudioSettings.from_dict(data.get("audio", {})),
            web=WebSettings.from_dict(data.get("web", {})),
        )

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        import os

        settings = cls()

        # Log level
        if log_level := os.environ.get("SONORIUM_LOG_LEVEL"):
            try:
                settings.log_level = LogLevel(log_level.lower())
            except ValueError:
                pass

        # Data directory
        if data_dir := os.environ.get("SONORIUM_DATA_DIR"):
            settings.data_dir = data_dir

        # Web settings
        if port := os.environ.get("SONORIUM_PORT"):
            try:
                settings.web.port = int(port)
            except ValueError:
                pass

        # MQTT settings
        if mqtt_enabled := os.environ.get("SONORIUM_MQTT_ENABLED"):
            settings.mqtt.enabled = mqtt_enabled.lower() in ("true", "1", "yes")
        if mqtt_host := os.environ.get("SONORIUM_MQTT_HOST"):
            settings.mqtt.host = mqtt_host
        if mqtt_port := os.environ.get("SONORIUM_MQTT_PORT"):
            try:
                settings.mqtt.port = int(mqtt_port)
            except ValueError:
                pass
        if mqtt_user := os.environ.get("SONORIUM_MQTT_USERNAME"):
            settings.mqtt.username = mqtt_user
        if mqtt_pass := os.environ.get("SONORIUM_MQTT_PASSWORD"):
            settings.mqtt.password = mqtt_pass

        return settings
