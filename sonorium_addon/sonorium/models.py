"""
Sonorium Models

Data models for MQTT settings and other configurations.

CORE CODE: This module is shared across all platforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MQTTSettings:
    """MQTT connection settings."""

    enabled: bool = False
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "sonorium"
    topic_prefix: str = "sonorium"

    # Home Assistant MQTT discovery
    ha_discovery_enabled: bool = True
    ha_discovery_prefix: str = "homeassistant"

    @classmethod
    def from_dict(cls, data: dict) -> MQTTSettings:
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "client_id": self.client_id,
            "topic_prefix": self.topic_prefix,
            "ha_discovery_enabled": self.ha_discovery_enabled,
            "ha_discovery_prefix": self.ha_discovery_prefix,
        }


# Note: Speaker and Session models are now in core/state.py
# This file exists for MQTT settings compatibility
