"""
Speaker data models.

Defines the Speaker class and related types for representing
network speakers discovered via various protocols.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class SpeakerProtocol(str, Enum):
    """Supported speaker protocols."""
    SONOS = "sonos"
    CHROMECAST = "chromecast"
    AIRPLAY = "airplay"
    DLNA = "dlna"
    LINKPLAY = "linkplay"
    HEOS = "heos"
    UNKNOWN = "unknown"


class SpeakerState(str, Enum):
    """Speaker connection/playback state."""
    UNKNOWN = "unknown"
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"
    ERROR = "error"


class DiscoverySource(str, Enum):
    """How the speaker was discovered."""
    DIRECT = "direct"           # Direct network discovery (mDNS, SSDP)
    HOME_ASSISTANT = "ha"       # Via Home Assistant registry
    MANUAL = "manual"           # Manually configured


@dataclass
class Speaker:
    """
    Represents a network speaker.

    Speakers are identified by a unique ID (typically derived from
    their hardware address or protocol-specific identifier).
    """

    id: str                                     # Unique identifier
    name: str                                   # Display name
    protocol: SpeakerProtocol                   # Protocol used to control
    host: str                                   # IP address or hostname
    port: Optional[int] = None                  # Port (protocol-specific)

    # State
    enabled: bool = False                       # Whether user has enabled this speaker
    state: SpeakerState = SpeakerState.IDLE     # Current playback state
    volume: float = 0.5                         # Volume level (0.0 - 1.0)
    muted: bool = False                         # Whether muted

    # Discovery metadata
    discovery_sources: list[DiscoverySource] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    model: Optional[str] = None                 # Device model (if known)
    manufacturer: Optional[str] = None          # Device manufacturer (if known)

    # HA-specific (populated when discovered via HA)
    ha_entity_id: Optional[str] = None          # e.g., "media_player.living_room"
    ha_area: Optional[str] = None               # HA area name
    ha_floor: Optional[str] = None              # HA floor name

    # Capabilities
    supports_volume: bool = True
    supports_pause: bool = False
    supports_seek: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "protocol": self.protocol.value,
            "host": self.host,
            "port": self.port,
            "enabled": self.enabled,
            "state": self.state.value,
            "volume": self.volume,
            "muted": self.muted,
            "discovery_sources": [s.value for s in self.discovery_sources],
            "last_seen": self.last_seen,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "ha_entity_id": self.ha_entity_id,
            "ha_area": self.ha_area,
            "ha_floor": self.ha_floor,
            "supports_volume": self.supports_volume,
            "supports_pause": self.supports_pause,
            "supports_seek": self.supports_seek,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Speaker":
        """Create Speaker from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            protocol=SpeakerProtocol(data.get("protocol", "unknown")),
            host=data["host"],
            port=data.get("port"),
            enabled=data.get("enabled", False),
            state=SpeakerState(data.get("state", "idle")),
            volume=data.get("volume", 0.5),
            muted=data.get("muted", False),
            discovery_sources=[DiscoverySource(s) for s in data.get("discovery_sources", [])],
            last_seen=data.get("last_seen", time.time()),
            model=data.get("model"),
            manufacturer=data.get("manufacturer"),
            ha_entity_id=data.get("ha_entity_id"),
            ha_area=data.get("ha_area"),
            ha_floor=data.get("ha_floor"),
            supports_volume=data.get("supports_volume", True),
            supports_pause=data.get("supports_pause", False),
            supports_seek=data.get("supports_seek", False),
        )

    def merge_with(self, other: "Speaker") -> "Speaker":
        """
        Merge with another speaker (e.g., same speaker found by different sources).

        Combines discovery sources and prefers more complete information.
        """
        # Combine discovery sources
        sources = list(set(self.discovery_sources + other.discovery_sources))

        # Prefer HA data if available (more reliable names/areas)
        name = other.name if other.ha_entity_id else self.name
        ha_entity_id = self.ha_entity_id or other.ha_entity_id
        ha_area = self.ha_area or other.ha_area
        ha_floor = self.ha_floor or other.ha_floor

        return Speaker(
            id=self.id,
            name=name,
            protocol=self.protocol,
            host=self.host,
            port=self.port,
            enabled=self.enabled or other.enabled,
            state=self.state if self.state != SpeakerState.UNKNOWN else other.state,
            volume=self.volume,
            muted=self.muted,
            discovery_sources=sources,
            last_seen=max(self.last_seen, other.last_seen),
            model=self.model or other.model,
            manufacturer=self.manufacturer or other.manufacturer,
            ha_entity_id=ha_entity_id,
            ha_area=ha_area,
            ha_floor=ha_floor,
            supports_volume=self.supports_volume or other.supports_volume,
            supports_pause=self.supports_pause or other.supports_pause,
            supports_seek=self.supports_seek or other.supports_seek,
        )


def generate_speaker_id(protocol: SpeakerProtocol, host: str, unique_id: Optional[str] = None) -> str:
    """
    Generate a consistent speaker ID.

    Uses unique_id if available (e.g., MAC address), otherwise falls back to host.
    """
    if unique_id:
        return f"{protocol.value}_{unique_id}".replace(":", "_").replace("-", "_")
    return f"{protocol.value}_{host}".replace(".", "_").replace(":", "_")
