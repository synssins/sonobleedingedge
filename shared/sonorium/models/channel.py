"""
Channel data models.

Channels represent audio zones - logical groupings of speakers
that receive the same audio content.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class Channel:
    """
    An audio channel/zone.

    Channels group speakers together and manage playback for a zone.
    """

    id: str                             # Unique channel ID
    name: str                           # Display name
    speakers: list[str] = field(default_factory=list)  # Speaker IDs

    # Playback
    theme_id: Optional[str] = None      # Currently playing theme
    session_id: Optional[str] = None    # Active session ID

    # Volume
    volume: float = 1.0                 # Channel volume (0.0 - 1.0)
    muted: bool = False

    # Configuration
    auto_play: bool = False             # Auto-play on startup
    default_theme: Optional[str] = None # Default theme for auto-play

    @classmethod
    def create(cls, name: str, speaker_ids: Optional[list[str]] = None) -> "Channel":
        """Create a new channel."""
        return cls(
            id=f"channel_{uuid.uuid4().hex[:6]}",
            name=name,
            speakers=speaker_ids or [],
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "speakers": self.speakers,
            "theme_id": self.theme_id,
            "session_id": self.session_id,
            "volume": self.volume,
            "muted": self.muted,
            "auto_play": self.auto_play,
            "default_theme": self.default_theme,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Channel":
        """Create Channel from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            speakers=data.get("speakers", []),
            theme_id=data.get("theme_id"),
            session_id=data.get("session_id"),
            volume=data.get("volume", 1.0),
            muted=data.get("muted", False),
            auto_play=data.get("auto_play", False),
            default_theme=data.get("default_theme"),
        )

    def add_speaker(self, speaker_id: str) -> bool:
        """Add a speaker to the channel. Returns True if added."""
        if speaker_id not in self.speakers:
            self.speakers.append(speaker_id)
            return True
        return False

    def remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker from the channel. Returns True if removed."""
        if speaker_id in self.speakers:
            self.speakers.remove(speaker_id)
            return True
        return False

    def has_speaker(self, speaker_id: str) -> bool:
        """Check if speaker is assigned to this channel."""
        return speaker_id in self.speakers

    @property
    def is_playing(self) -> bool:
        """Whether channel has an active session."""
        return self.session_id is not None

    @property
    def speaker_count(self) -> int:
        """Number of speakers in this channel."""
        return len(self.speakers)
