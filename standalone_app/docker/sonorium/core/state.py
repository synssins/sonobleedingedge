"""
State management - Single source of truth.

All application state flows through this module. Components read state
from here and dispatch changes through the StateManager.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
import json
import asyncio
import logging
from contextlib import contextmanager

from ..models import (
    Speaker,
    Theme,
    Session,
    Channel,
    Settings,
)

logger = logging.getLogger(__name__)


# Type for state change callbacks
StateChangeCallback = Callable[["SonoriumState", str], None]


@dataclass
class SonoriumState:
    """
    Complete application state.

    This is the single source of truth for all Sonorium state.
    """

    # Discovered speakers
    speakers: dict[str, Speaker] = field(default_factory=dict)

    # Available themes
    themes: dict[str, Theme] = field(default_factory=dict)

    # Active sessions
    sessions: dict[str, Session] = field(default_factory=dict)

    # Channels/zones
    channels: dict[str, Channel] = field(default_factory=dict)

    # Settings
    settings: Settings = field(default_factory=Settings)

    # Enabled speaker IDs (convenience set for fast lookup)
    _enabled_speakers: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        """Serialize state to dictionary."""
        return {
            "speakers": {k: v.to_dict() for k, v in self.speakers.items()},
            "themes": {k: v.to_dict() for k, v in self.themes.items()},
            "sessions": {k: v.to_dict() for k, v in self.sessions.items()},
            "channels": {k: v.to_dict() for k, v in self.channels.items()},
            "settings": self.settings.to_dict(),
            "enabled_speakers": list(self._enabled_speakers),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SonoriumState":
        """Deserialize state from dictionary."""
        state = cls()

        # Load speakers
        for speaker_id, speaker_data in data.get("speakers", {}).items():
            state.speakers[speaker_id] = Speaker.from_dict(speaker_data)

        # Load themes
        for theme_id, theme_data in data.get("themes", {}).items():
            state.themes[theme_id] = Theme.from_dict(theme_data)

        # Load sessions (only active ones)
        for session_id, session_data in data.get("sessions", {}).items():
            session = Session.from_dict(session_data)
            if session.is_active:
                state.sessions[session_id] = session

        # Load channels
        for channel_id, channel_data in data.get("channels", {}).items():
            state.channels[channel_id] = Channel.from_dict(channel_data)

        # Load settings
        state.settings = Settings.from_dict(data.get("settings", {}))

        # Load enabled speakers
        state._enabled_speakers = set(data.get("enabled_speakers", []))

        # Sync enabled state to speaker objects
        for speaker_id in state._enabled_speakers:
            if speaker_id in state.speakers:
                state.speakers[speaker_id].enabled = True

        return state


class StateManager:
    """
    Manages application state with persistence and change notifications.

    Usage:
        manager = StateManager(config_path="/path/to/config.json")
        await manager.load()

        # Read state
        speakers = manager.state.speakers

        # Modify state (notifies listeners)
        manager.enable_speaker("speaker_1")

        # Subscribe to changes
        manager.on_change(lambda state, key: print(f"Changed: {key}"))
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._state = SonoriumState()
        self._config_path = config_path
        self._callbacks: list[StateChangeCallback] = []
        self._lock = asyncio.Lock()
        self._dirty = False
        self._save_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> SonoriumState:
        """Get current state (read-only access)."""
        return self._state

    # ─────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────

    async def load(self) -> None:
        """Load state from disk."""
        if self._config_path and self._config_path.exists():
            try:
                async with self._lock:
                    data = json.loads(self._config_path.read_text(encoding="utf-8"))
                    self._state = SonoriumState.from_dict(data)
                logger.info(f"Loaded state from {self._config_path}")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                self._state = SonoriumState()
        else:
            logger.info("No existing state file, starting fresh")
            self._state = SonoriumState()

    async def save(self) -> None:
        """Save state to disk."""
        if not self._config_path:
            return

        try:
            async with self._lock:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                self._config_path.write_text(
                    json.dumps(self._state.to_dict(), indent=2),
                    encoding="utf-8"
                )
                self._dirty = False
            logger.debug(f"Saved state to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _mark_dirty(self) -> None:
        """Mark state as needing save, schedule debounced save."""
        self._dirty = True
        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self) -> None:
        """Save after a short delay (debounce rapid changes)."""
        await asyncio.sleep(1.0)
        if self._dirty:
            await self.save()

    # ─────────────────────────────────────────────────────────────
    # Change notifications
    # ─────────────────────────────────────────────────────────────

    def on_change(self, callback: StateChangeCallback) -> Callable[[], None]:
        """
        Subscribe to state changes.

        Returns a function to unsubscribe.
        """
        self._callbacks.append(callback)

        def unsubscribe():
            self._callbacks.remove(callback)

        return unsubscribe

    def _notify(self, key: str) -> None:
        """Notify listeners of state change."""
        for callback in self._callbacks:
            try:
                callback(self._state, key)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    # ─────────────────────────────────────────────────────────────
    # Speaker operations
    # ─────────────────────────────────────────────────────────────

    def add_speaker(self, speaker: Speaker) -> None:
        """Add or update a speaker."""
        existing = self._state.speakers.get(speaker.id)
        if existing:
            # Merge with existing (preserve enabled state, combine sources)
            speaker = existing.merge_with(speaker)
            speaker.enabled = speaker.id in self._state._enabled_speakers

        self._state.speakers[speaker.id] = speaker
        self._mark_dirty()
        self._notify("speakers")

    def remove_speaker(self, speaker_id: str) -> bool:
        """Remove a speaker. Returns True if removed."""
        if speaker_id in self._state.speakers:
            del self._state.speakers[speaker_id]
            self._state._enabled_speakers.discard(speaker_id)
            self._mark_dirty()
            self._notify("speakers")
            return True
        return False

    def enable_speaker(self, speaker_id: str) -> bool:
        """Enable a speaker. Returns True if state changed."""
        if speaker_id in self._state.speakers:
            if speaker_id not in self._state._enabled_speakers:
                self._state._enabled_speakers.add(speaker_id)
                self._state.speakers[speaker_id].enabled = True
                self._mark_dirty()
                self._notify("speakers")
                return True
        return False

    def disable_speaker(self, speaker_id: str) -> bool:
        """Disable a speaker. Returns True if state changed."""
        if speaker_id in self._state._enabled_speakers:
            self._state._enabled_speakers.discard(speaker_id)
            if speaker_id in self._state.speakers:
                self._state.speakers[speaker_id].enabled = False
            self._mark_dirty()
            self._notify("speakers")
            return True
        return False

    def enable_all_speakers(self) -> int:
        """Enable all speakers. Returns count of newly enabled."""
        count = 0
        for speaker_id in self._state.speakers:
            if speaker_id not in self._state._enabled_speakers:
                self._state._enabled_speakers.add(speaker_id)
                self._state.speakers[speaker_id].enabled = True
                count += 1
        if count > 0:
            self._mark_dirty()
            self._notify("speakers")
        return count

    def disable_all_speakers(self) -> int:
        """Disable all speakers. Returns count of newly disabled."""
        count = len(self._state._enabled_speakers)
        for speaker_id in self._state._enabled_speakers:
            if speaker_id in self._state.speakers:
                self._state.speakers[speaker_id].enabled = False
        self._state._enabled_speakers.clear()
        if count > 0:
            self._mark_dirty()
            self._notify("speakers")
        return count

    def get_enabled_speakers(self) -> list[Speaker]:
        """Get list of enabled speakers."""
        return [
            self._state.speakers[sid]
            for sid in self._state._enabled_speakers
            if sid in self._state.speakers
        ]

    def is_speaker_enabled(self, speaker_id: str) -> bool:
        """Check if speaker is enabled."""
        return speaker_id in self._state._enabled_speakers

    def set_speaker_volume(self, speaker_id: str, volume: float) -> bool:
        """Set speaker volume. Returns True if found."""
        if speaker_id in self._state.speakers:
            self._state.speakers[speaker_id].volume = max(0.0, min(1.0, volume))
            self._mark_dirty()
            self._notify("speakers")
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Theme operations
    # ─────────────────────────────────────────────────────────────

    def add_theme(self, theme: Theme) -> None:
        """Add or update a theme."""
        self._state.themes[theme.id] = theme
        self._notify("themes")

    def remove_theme(self, theme_id: str) -> bool:
        """Remove a theme. Returns True if removed."""
        if theme_id in self._state.themes:
            del self._state.themes[theme_id]
            self._notify("themes")
            return True
        return False

    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """Get theme by ID."""
        return self._state.themes.get(theme_id)

    # ─────────────────────────────────────────────────────────────
    # Session operations
    # ─────────────────────────────────────────────────────────────

    def add_session(self, session: Session) -> None:
        """Add a new session."""
        self._state.sessions[session.id] = session
        self._mark_dirty()
        self._notify("sessions")

    def remove_session(self, session_id: str) -> bool:
        """Remove a session. Returns True if removed."""
        if session_id in self._state.sessions:
            del self._state.sessions[session_id]
            self._mark_dirty()
            self._notify("sessions")
            return True
        return False

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._state.sessions.get(session_id)

    def get_active_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return [s for s in self._state.sessions.values() if s.is_active]

    def get_sessions_for_speaker(self, speaker_id: str) -> list[Session]:
        """Get sessions that include a specific speaker."""
        return [
            s for s in self._state.sessions.values()
            if speaker_id in s.get_speaker_ids() and s.is_active
        ]

    # ─────────────────────────────────────────────────────────────
    # Channel operations
    # ─────────────────────────────────────────────────────────────

    def add_channel(self, channel: Channel) -> None:
        """Add or update a channel."""
        self._state.channels[channel.id] = channel
        self._mark_dirty()
        self._notify("channels")

    def remove_channel(self, channel_id: str) -> bool:
        """Remove a channel. Returns True if removed."""
        if channel_id in self._state.channels:
            del self._state.channels[channel_id]
            self._mark_dirty()
            self._notify("channels")
            return True
        return False

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Get channel by ID."""
        return self._state.channels.get(channel_id)

    # ─────────────────────────────────────────────────────────────
    # Settings operations
    # ─────────────────────────────────────────────────────────────

    def update_settings(self, **kwargs) -> None:
        """Update settings."""
        for key, value in kwargs.items():
            if hasattr(self._state.settings, key):
                setattr(self._state.settings, key, value)
        self._mark_dirty()
        self._notify("settings")

    def get_settings(self) -> Settings:
        """Get current settings."""
        return self._state.settings


# Global state manager instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        raise RuntimeError("State manager not initialized. Call init_state_manager() first.")
    return _state_manager


async def init_state_manager(config_path: Optional[Path] = None) -> StateManager:
    """Initialize the global state manager."""
    global _state_manager
    _state_manager = StateManager(config_path)
    await _state_manager.load()
    return _state_manager
