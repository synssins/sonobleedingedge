"""
Unified Speaker Model

Provides a common data model for speakers discovered from multiple sources
(Home Assistant, direct discovery via plugins, etc.).

This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Set


class DiscoverySource(str, Enum):
    """
    How a speaker was discovered.

    Speakers can be found by multiple sources simultaneously.
    """
    HA = "ha"                   # Home Assistant media_player entity
    SONOS = "sonos"             # SoCo direct discovery
    CHROMECAST = "chromecast"   # pychromecast discovery
    AIRPLAY = "airplay"         # pyatv/AirPlay discovery
    DLNA = "dlna"               # DLNA/UPnP discovery
    LINKPLAY = "linkplay"       # Linkplay/Arylic discovery
    HEOS = "heos"               # Denon HEOS discovery
    MANUAL = "manual"           # User-configured manual entry


class ControlMethod(str, Enum):
    """
    How to control a speaker for playback.

    When a speaker is found by multiple sources, we prefer HA control
    for better integration, falling back to direct protocol control.
    """
    HA_SERVICE = "ha_service"   # Control via HA media_player service calls
    DIRECT = "direct"           # Control via direct protocol (plugin)


@dataclass
class UnifiedSpeaker:
    """
    A speaker that may be discovered by multiple sources.

    This is the common representation used throughout Sonorium,
    combining information from HA registry and direct discovery.

    Attributes:
        canonical_id: Unique identifier used for deduplication.
                     Format: "unified_{mac}" or "unified_{uuid}" or "unified_{ip}"
        name: Display name (friendly name)
        ip_address: Network IP address (if known)
        mac_address: MAC address (if known, used for dedup)
        uuid: Device UUID (protocol-specific, used for dedup)
        entity_id: Home Assistant entity_id (if from HA)
        area_id: HA area ID (if from HA)
        area_name: HA area name (if from HA)
        floor_id: HA floor ID (if from HA)
        floor_name: HA floor name (if from HA)
        found_by: Set of discovery sources that found this speaker
        preferred_control: How this speaker should be controlled
        protocol: Primary protocol for direct control (e.g., "sonos", "chromecast")
        model: Device model name
        manufacturer: Device manufacturer
        capabilities: List of supported features
        extra: Protocol-specific extra data
    """
    canonical_id: str
    name: str

    # Network identifiers (used for deduplication)
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    uuid: Optional[str] = None

    # Home Assistant integration
    entity_id: Optional[str] = None
    area_id: Optional[str] = None
    area_name: Optional[str] = None
    floor_id: Optional[str] = None
    floor_name: Optional[str] = None

    # Discovery and control
    found_by: Set[str] = field(default_factory=set)
    preferred_control: ControlMethod = ControlMethod.DIRECT
    protocol: Optional[str] = None

    # Device info
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)

    # Protocol-specific data
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        """Ensure found_by is a set."""
        if isinstance(self.found_by, list):
            self.found_by = set(self.found_by)

    @property
    def has_ha_entity(self) -> bool:
        """Check if this speaker has a Home Assistant entity."""
        return bool(self.entity_id)

    @property
    def is_direct_only(self) -> bool:
        """Check if this speaker was only found by direct discovery."""
        return not self.has_ha_entity

    @property
    def found_by_list(self) -> list[str]:
        """Get found_by as a sorted list (for API serialization)."""
        return sorted(self.found_by)

    def to_dict(self) -> dict:
        """Serialize to dict for API responses."""
        return {
            "canonical_id": self.canonical_id,
            "name": self.name,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "uuid": self.uuid,
            "entity_id": self.entity_id,
            "area_id": self.area_id,
            "area_name": self.area_name,
            "floor_id": self.floor_id,
            "floor_name": self.floor_name,
            "found_by": self.found_by_list,
            "preferred_control": self.preferred_control.value,
            "protocol": self.protocol,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedSpeaker":
        """Create from dict (API deserialization)."""
        found_by = data.get("found_by", [])
        if isinstance(found_by, list):
            found_by = set(found_by)

        control = data.get("preferred_control", "direct")
        if isinstance(control, str):
            control = ControlMethod(control)

        return cls(
            canonical_id=data["canonical_id"],
            name=data["name"],
            ip_address=data.get("ip_address"),
            mac_address=data.get("mac_address"),
            uuid=data.get("uuid"),
            entity_id=data.get("entity_id"),
            area_id=data.get("area_id"),
            area_name=data.get("area_name"),
            floor_id=data.get("floor_id"),
            floor_name=data.get("floor_name"),
            found_by=found_by,
            preferred_control=control,
            protocol=data.get("protocol"),
            model=data.get("model"),
            manufacturer=data.get("manufacturer"),
            capabilities=data.get("capabilities", []),
            extra=data.get("extra", {}),
        )

    def merge_with(self, other: "UnifiedSpeaker") -> "UnifiedSpeaker":
        """
        Merge another speaker's information into this one.

        Used during deduplication to combine info from multiple sources.
        Prefers HA information when available.

        Args:
            other: Another UnifiedSpeaker representing the same device

        Returns:
            New UnifiedSpeaker with merged information
        """
        # Combine found_by sources
        combined_found_by = self.found_by | other.found_by

        # Prefer HA entity_id if available
        entity_id = self.entity_id or other.entity_id

        # Prefer HA area/floor info
        area_id = self.area_id or other.area_id
        area_name = self.area_name or other.area_name
        floor_id = self.floor_id or other.floor_id
        floor_name = self.floor_name or other.floor_name

        # Control method: prefer HA if we have an entity
        if entity_id:
            control = ControlMethod.HA_SERVICE
        else:
            control = self.preferred_control

        # Prefer non-None values for identifiers
        ip_address = self.ip_address or other.ip_address
        mac_address = self.mac_address or other.mac_address
        uuid = self.uuid or other.uuid

        # Prefer the name from HA (usually friendlier)
        name = self.name if self.has_ha_entity else (other.name if other.has_ha_entity else self.name)

        # Merge extra data
        merged_extra = {**self.extra, **other.extra}

        # Combine capabilities
        combined_caps = list(set(self.capabilities + other.capabilities))

        return UnifiedSpeaker(
            canonical_id=self.canonical_id,  # Keep original canonical_id
            name=name,
            ip_address=ip_address,
            mac_address=mac_address,
            uuid=uuid,
            entity_id=entity_id,
            area_id=area_id,
            area_name=area_name,
            floor_id=floor_id,
            floor_name=floor_name,
            found_by=combined_found_by,
            preferred_control=control,
            protocol=self.protocol or other.protocol,
            model=self.model or other.model,
            manufacturer=self.manufacturer or other.manufacturer,
            capabilities=combined_caps,
            extra=merged_extra,
        )
