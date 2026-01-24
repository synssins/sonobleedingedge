"""
Home Assistant Addon Wrapper.

This module contains HA-specific implementations that are NOT synced.
- Supervisor API integration
- MQTT entity exposure
- HA device registry queries
- HA media_player control routing
"""

from .settings import HASettings
from .supervisor import SupervisorAPI

__all__ = ["HASettings", "SupervisorAPI"]
