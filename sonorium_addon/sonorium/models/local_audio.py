"""
Local audio device models.

Represents local audio output devices (sound cards, USB speakers, etc.)
that can be used alongside network speakers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LocalDeviceState(str, Enum):
    """Local device state."""
    AVAILABLE = "available"
    PLAYING = "playing"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class LocalAudioDevice:
    """
    A local audio output device.

    These are physical audio devices connected to the system (sound cards,
    USB audio devices, HDMI audio, etc.).
    """

    id: str                             # Unique identifier (system-specific)
    name: str                           # Display name
    system_name: str                    # System/driver name

    # State
    enabled: bool = False               # Whether user has enabled this device
    state: LocalDeviceState = LocalDeviceState.AVAILABLE
    volume: float = 0.5                 # Volume level (0.0 - 1.0)
    muted: bool = False

    # Device info
    channels: int = 2                   # Number of audio channels
    sample_rate: int = 44100            # Sample rate
    is_default: bool = False            # Whether this is the system default

    # Platform-specific
    driver: Optional[str] = None        # Audio driver (e.g., "WASAPI", "ALSA", "CoreAudio")
    device_index: Optional[int] = None  # Index for PyAudio/sounddevice

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "system_name": self.system_name,
            "enabled": self.enabled,
            "state": self.state.value,
            "volume": self.volume,
            "muted": self.muted,
            "channels": self.channels,
            "sample_rate": self.sample_rate,
            "is_default": self.is_default,
            "driver": self.driver,
            "device_index": self.device_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LocalAudioDevice":
        """Create LocalAudioDevice from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            system_name=data["system_name"],
            enabled=data.get("enabled", False),
            state=LocalDeviceState(data.get("state", "available")),
            volume=data.get("volume", 0.5),
            muted=data.get("muted", False),
            channels=data.get("channels", 2),
            sample_rate=data.get("sample_rate", 44100),
            is_default=data.get("is_default", False),
            driver=data.get("driver"),
            device_index=data.get("device_index"),
        )


def generate_local_device_id(system_name: str, device_index: Optional[int] = None) -> str:
    """Generate a consistent local device ID."""
    base = system_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
    if device_index is not None:
        return f"local_{base}_{device_index}"
    return f"local_{base}"
