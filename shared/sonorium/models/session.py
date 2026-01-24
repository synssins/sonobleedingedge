"""
Session data models.

A Session represents an active playback instance - a theme playing
to one or more speakers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time
import uuid


class SessionState(str, Enum):
    """Session playback state."""
    STARTING = "starting"       # Session is being set up
    PLAYING = "playing"         # Actively playing
    PAUSED = "paused"           # Paused (if supported)
    STOPPING = "stopping"       # Session is being torn down
    STOPPED = "stopped"         # Session has ended
    ERROR = "error"             # Error occurred


@dataclass
class SessionSpeaker:
    """
    A speaker assigned to a session with session-specific settings.
    """
    speaker_id: str             # Reference to Speaker.id
    volume: float = 1.0         # Speaker volume for this session (0.0 - 1.0)
    muted: bool = False         # Whether muted in this session
    state: SessionState = SessionState.STARTING

    def to_dict(self) -> dict:
        return {
            "speaker_id": self.speaker_id,
            "volume": self.volume,
            "muted": self.muted,
            "state": self.state.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionSpeaker":
        return cls(
            speaker_id=data["speaker_id"],
            volume=data.get("volume", 1.0),
            muted=data.get("muted", False),
            state=SessionState(data.get("state", "starting")),
        )


@dataclass
class Session:
    """
    An active playback session.

    Represents a theme playing to one or more speakers.
    """

    id: str                                     # Unique session ID
    theme_id: str                               # Theme being played
    channel_id: Optional[str] = None            # Channel this session belongs to

    # Speakers
    speakers: list[SessionSpeaker] = field(default_factory=list)

    # Playback state
    state: SessionState = SessionState.STARTING
    volume: float = 1.0                         # Master volume for session
    muted: bool = False

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None

    # Error tracking
    error_message: Optional[str] = None

    @classmethod
    def create(cls, theme_id: str, speaker_ids: list[str], channel_id: Optional[str] = None) -> "Session":
        """Create a new session."""
        return cls(
            id=str(uuid.uuid4())[:8],
            theme_id=theme_id,
            channel_id=channel_id,
            speakers=[SessionSpeaker(speaker_id=sid) for sid in speaker_ids],
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "theme_id": self.theme_id,
            "channel_id": self.channel_id,
            "speakers": [s.to_dict() for s in self.speakers],
            "state": self.state.value,
            "volume": self.volume,
            "muted": self.muted,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create Session from dictionary."""
        return cls(
            id=data["id"],
            theme_id=data["theme_id"],
            channel_id=data.get("channel_id"),
            speakers=[SessionSpeaker.from_dict(s) for s in data.get("speakers", [])],
            state=SessionState(data.get("state", "starting")),
            volume=data.get("volume", 1.0),
            muted=data.get("muted", False),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            stopped_at=data.get("stopped_at"),
            error_message=data.get("error_message"),
        )

    def get_speaker_ids(self) -> list[str]:
        """Get list of speaker IDs in this session."""
        return [s.speaker_id for s in self.speakers]

    def add_speaker(self, speaker_id: str, volume: float = 1.0) -> None:
        """Add a speaker to the session."""
        if speaker_id not in self.get_speaker_ids():
            self.speakers.append(SessionSpeaker(speaker_id=speaker_id, volume=volume))

    def remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker from the session. Returns True if removed."""
        for i, speaker in enumerate(self.speakers):
            if speaker.speaker_id == speaker_id:
                del self.speakers[i]
                return True
        return False

    def set_speaker_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume for a specific speaker. Returns True if found."""
        for speaker in self.speakers:
            if speaker.speaker_id == speaker_id:
                speaker.volume = max(0.0, min(1.0, volume))
                return True
        return False

    def mark_started(self) -> None:
        """Mark session as started."""
        self.state = SessionState.PLAYING
        self.started_at = time.time()
        for speaker in self.speakers:
            speaker.state = SessionState.PLAYING

    def mark_stopped(self) -> None:
        """Mark session as stopped."""
        self.state = SessionState.STOPPED
        self.stopped_at = time.time()
        for speaker in self.speakers:
            speaker.state = SessionState.STOPPED

    def mark_error(self, message: str) -> None:
        """Mark session as errored."""
        self.state = SessionState.ERROR
        self.error_message = message

    @property
    def is_active(self) -> bool:
        """Whether session is currently active (not stopped or errored)."""
        return self.state in (SessionState.STARTING, SessionState.PLAYING, SessionState.PAUSED)

    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds, or None if not started."""
        if self.started_at is None:
            return None
        end_time = self.stopped_at or time.time()
        return end_time - self.started_at
