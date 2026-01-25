"""
Home Assistant Integration Module

This module provides Home Assistant-specific functionality:
- HARegistry: Query HA device/entity registries for speaker discovery
- HAMediaController: Control speakers via HA media_player services
- SonosPlayer: Direct Sonos control via SoCo library
- CastPlayer: Direct Cast control via pychromecast

ADDON CODE: This is specific to the Home Assistant addon deployment.
"""

from sonorium.ha.registry import (
    Speaker,
    Area,
    Floor,
    SpeakerHierarchy,
    HARegistry,
    create_registry_from_supervisor,
    WEBSOCKETS_AVAILABLE,
)
from sonorium.ha.media_controller import (
    HAMediaController,
    create_media_controller_from_supervisor,
)
from sonorium.ha.sonos_player import SonosPlayer
from sonorium.ha.cast_player import CastPlayer
from sonorium.ha.utils import (
    call_ha_service,
    call_ha_service_async,
    is_ha_environment,
    get_supervisor_token,
    get_ha_api_url,
    get_ha_state,
    get_all_media_players,
)
from sonorium.ha.mqtt_entities import (
    EntityConfig,
    SessionMQTTEntities,
    DirectSpeakerMQTTEntities,
    SonoriumMQTTManager,
)


__all__ = [
    # Registry
    "Speaker",
    "Area",
    "Floor",
    "SpeakerHierarchy",
    "HARegistry",
    "create_registry_from_supervisor",
    "WEBSOCKETS_AVAILABLE",
    # Media Controller
    "HAMediaController",
    "create_media_controller_from_supervisor",
    # Direct Players
    "SonosPlayer",
    "CastPlayer",
    # Utils
    "call_ha_service",
    "call_ha_service_async",
    "is_ha_environment",
    "get_supervisor_token",
    "get_ha_api_url",
    "get_ha_state",
    "get_all_media_players",
    # MQTT Entities
    "EntityConfig",
    "SessionMQTTEntities",
    "DirectSpeakerMQTTEntities",
    "SonoriumMQTTManager",
]
