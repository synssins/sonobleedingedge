"""
Streaming Engine.

Manages audio streaming sessions to network speakers.
Delegates protocol-specific operations to plugins.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class StreamState(str, Enum):
    """Streaming session states."""
    IDLE = "idle"
    CONNECTING = "connecting"
    BUFFERING = "buffering"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StreamSession:
    """
    Represents an active streaming session.

    A session streams audio to one or more speakers.
    """
    id: str
    theme_id: str
    stream_url: str
    speakers: list[str]  # Speaker IDs receiving this stream
    state: StreamState = StreamState.IDLE
    volume: float = 1.0
    muted: bool = False
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    error_message: Optional[str] = None

    # Internal state
    _speaker_states: dict[str, StreamState] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "theme_id": self.theme_id,
            "stream_url": self.stream_url,
            "speakers": self.speakers,
            "state": self.state.value,
            "volume": self.volume,
            "muted": self.muted,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "error_message": self.error_message,
            "speaker_states": {k: v.value for k, v in self._speaker_states.items()},
        }

    def get_speaker_state(self, speaker_id: str) -> StreamState:
        """Get state for a specific speaker in this session."""
        return self._speaker_states.get(speaker_id, StreamState.IDLE)

    def set_speaker_state(self, speaker_id: str, state: StreamState) -> None:
        """Set state for a specific speaker."""
        self._speaker_states[speaker_id] = state
        self._update_aggregate_state()

    def _update_aggregate_state(self) -> None:
        """Update overall session state based on speaker states."""
        if not self._speaker_states:
            return

        states = list(self._speaker_states.values())

        # If any speaker has error, session has error
        if StreamState.ERROR in states:
            self.state = StreamState.ERROR
        # If all speakers are playing, session is playing
        elif all(s == StreamState.PLAYING for s in states):
            self.state = StreamState.PLAYING
        # If any speaker is connecting/buffering, session is connecting
        elif StreamState.CONNECTING in states or StreamState.BUFFERING in states:
            self.state = StreamState.CONNECTING
        # If all speakers are stopped, session is stopped
        elif all(s == StreamState.STOPPED for s in states):
            self.state = StreamState.STOPPED
        else:
            self.state = StreamState.IDLE


class StreamingEngine:
    """
    Manages audio streaming to network speakers.

    The streaming approach:
    1. Sonorium hosts HTTP audio stream endpoints
    2. Network speakers connect to these endpoints
    3. Audio is mixed and served in real-time

    This engine is protocol-agnostic - it delegates actual speaker
    control to plugins via the PluginManager.
    """

    def __init__(self, stream_base_url: Optional[str] = None, port: int = 8099):
        """
        Initialize streaming engine.

        Args:
            stream_base_url: Base URL for streams (auto-detected if None)
            port: HTTP server port
        """
        self.port = port
        self._base_url = stream_base_url
        self._sessions: dict[str, StreamSession] = {}
        self._lock = asyncio.Lock()
        self._on_state_change: list[Callable[[StreamSession], None]] = []

        # Will be set when plugin manager is available
        self._plugin_manager = None

    @property
    def base_url(self) -> str:
        """Get the base URL for streaming."""
        if self._base_url:
            return self._base_url

        # Auto-detect local IP
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"

        return f"http://{ip}:{self.port}"

    def set_base_url(self, url: str) -> None:
        """Set the base URL for streaming."""
        self._base_url = url.rstrip("/")
        logger.info(f"Stream base URL set to: {self._base_url}")

    def set_plugin_manager(self, manager) -> None:
        """Set the plugin manager for speaker control."""
        self._plugin_manager = manager

    def get_stream_url(self, session_id: str) -> str:
        """Get the HTTP stream URL for a session."""
        return f"{self.base_url}/stream/{session_id}"

    def get_theme_stream_url(self, theme_id: str) -> str:
        """Get the HTTP stream URL for a theme (direct streaming)."""
        return f"{self.base_url}/stream/theme/{theme_id}"

    def get_channel_stream_url(self, channel_id: str) -> str:
        """Get the HTTP stream URL for a channel."""
        return f"{self.base_url}/stream/channel/{channel_id}"

    # ─────────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────────

    async def create_session(
        self,
        session_id: str,
        theme_id: str,
        speaker_ids: list[str],
        volume: float = 1.0
    ) -> StreamSession:
        """
        Create a new streaming session.

        Args:
            session_id: Unique session identifier
            theme_id: Theme to stream
            speaker_ids: List of speaker IDs to stream to
            volume: Initial volume (0.0-1.0)

        Returns:
            The created StreamSession
        """
        stream_url = self.get_theme_stream_url(theme_id)

        session = StreamSession(
            id=session_id,
            theme_id=theme_id,
            stream_url=stream_url,
            speakers=speaker_ids.copy(),
            volume=volume,
        )

        # Initialize speaker states
        for speaker_id in speaker_ids:
            session._speaker_states[speaker_id] = StreamState.IDLE

        async with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created streaming session {session_id} for theme {theme_id}")
        return session

    async def start_session(self, session_id: str) -> bool:
        """
        Start streaming for a session.

        Args:
            session_id: Session to start

        Returns:
            True if streaming started successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False

        if not self._plugin_manager:
            logger.error("Plugin manager not set - cannot start streaming")
            session.state = StreamState.ERROR
            session.error_message = "Plugin manager not configured"
            return False

        session.state = StreamState.CONNECTING
        session.started_at = time.time()
        self._notify_state_change(session)

        # Start streaming to each speaker
        success_count = 0
        for speaker_id in session.speakers:
            session.set_speaker_state(speaker_id, StreamState.CONNECTING)

            try:
                success = await self._plugin_manager.play_url(
                    speaker_id,
                    session.stream_url,
                    volume=session.volume if not session.muted else 0.0
                )

                if success:
                    session.set_speaker_state(speaker_id, StreamState.PLAYING)
                    success_count += 1
                    logger.info(f"Started streaming to speaker {speaker_id}")
                else:
                    session.set_speaker_state(speaker_id, StreamState.ERROR)
                    logger.warning(f"Failed to start streaming to speaker {speaker_id}")

            except Exception as e:
                session.set_speaker_state(speaker_id, StreamState.ERROR)
                logger.error(f"Error starting stream to {speaker_id}: {e}")

        if success_count > 0:
            logger.info(f"Session {session_id} started on {success_count}/{len(session.speakers)} speakers")
        else:
            session.state = StreamState.ERROR
            session.error_message = "Failed to start on any speaker"

        self._notify_state_change(session)
        return success_count > 0

    async def stop_session(self, session_id: str) -> bool:
        """
        Stop a streaming session.

        Args:
            session_id: Session to stop

        Returns:
            True if stopped successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return True  # Already stopped

        if not self._plugin_manager:
            logger.warning("Plugin manager not set - marking session as stopped")
            session.state = StreamState.STOPPED
            return True

        # Stop streaming to each speaker
        for speaker_id in session.speakers:
            try:
                await self._plugin_manager.stop(speaker_id)
                session.set_speaker_state(speaker_id, StreamState.STOPPED)
            except Exception as e:
                logger.error(f"Error stopping stream to {speaker_id}: {e}")

        session.state = StreamState.STOPPED
        self._notify_state_change(session)

        logger.info(f"Stopped streaming session {session_id}")
        return True

    async def remove_session(self, session_id: str) -> bool:
        """
        Remove a session completely.

        Args:
            session_id: Session to remove

        Returns:
            True if removed
        """
        await self.stop_session(session_id)

        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug(f"Removed session {session_id}")
                return True

        return False

    async def stop_all(self) -> int:
        """
        Stop all streaming sessions.

        Returns:
            Number of sessions stopped
        """
        session_ids = list(self._sessions.keys())
        count = 0

        for session_id in session_ids:
            if await self.stop_session(session_id):
                count += 1

        logger.info(f"Stopped {count} streaming sessions")
        return count

    # ─────────────────────────────────────────────────────────────────────
    # Speaker Management
    # ─────────────────────────────────────────────────────────────────────

    async def add_speaker_to_session(self, session_id: str, speaker_id: str) -> bool:
        """
        Add a speaker to an existing session.

        Args:
            session_id: Session to modify
            speaker_id: Speaker to add

        Returns:
            True if speaker added and started
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if speaker_id in session.speakers:
            return True  # Already in session

        session.speakers.append(speaker_id)
        session._speaker_states[speaker_id] = StreamState.CONNECTING

        # If session is playing, start streaming to new speaker
        if session.state == StreamState.PLAYING and self._plugin_manager:
            try:
                success = await self._plugin_manager.play_url(
                    speaker_id,
                    session.stream_url,
                    volume=session.volume if not session.muted else 0.0
                )

                if success:
                    session.set_speaker_state(speaker_id, StreamState.PLAYING)
                else:
                    session.set_speaker_state(speaker_id, StreamState.ERROR)

            except Exception as e:
                session.set_speaker_state(speaker_id, StreamState.ERROR)
                logger.error(f"Error adding speaker {speaker_id}: {e}")

        self._notify_state_change(session)
        return True

    async def remove_speaker_from_session(self, session_id: str, speaker_id: str) -> bool:
        """
        Remove a speaker from a session.

        Args:
            session_id: Session to modify
            speaker_id: Speaker to remove

        Returns:
            True if speaker removed
        """
        session = self._sessions.get(session_id)
        if not session or speaker_id not in session.speakers:
            return False

        # Stop streaming to this speaker
        if self._plugin_manager:
            try:
                await self._plugin_manager.stop(speaker_id)
            except Exception as e:
                logger.error(f"Error stopping speaker {speaker_id}: {e}")

        session.speakers.remove(speaker_id)
        session._speaker_states.pop(speaker_id, None)

        self._notify_state_change(session)
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Volume Control
    # ─────────────────────────────────────────────────────────────────────

    async def set_session_volume(self, session_id: str, volume: float) -> bool:
        """
        Set volume for all speakers in a session.

        Args:
            session_id: Session to modify
            volume: Volume level (0.0-1.0)

        Returns:
            True if volume set
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        volume = max(0.0, min(1.0, volume))
        session.volume = volume

        if not session.muted and self._plugin_manager:
            for speaker_id in session.speakers:
                try:
                    await self._plugin_manager.set_volume(speaker_id, volume)
                except Exception as e:
                    logger.error(f"Error setting volume on {speaker_id}: {e}")

        self._notify_state_change(session)
        return True

    async def set_speaker_volume(self, speaker_id: str, volume: float) -> bool:
        """
        Set volume for a specific speaker.

        Args:
            speaker_id: Speaker to modify
            volume: Volume level (0.0-1.0)

        Returns:
            True if volume set
        """
        if not self._plugin_manager:
            return False

        volume = max(0.0, min(1.0, volume))

        try:
            return await self._plugin_manager.set_volume(speaker_id, volume)
        except Exception as e:
            logger.error(f"Error setting volume on {speaker_id}: {e}")
            return False

    async def mute_session(self, session_id: str, muted: bool = True) -> bool:
        """
        Mute or unmute a session.

        Args:
            session_id: Session to mute/unmute
            muted: True to mute, False to unmute

        Returns:
            True if mute state changed
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.muted = muted

        if self._plugin_manager:
            target_volume = 0.0 if muted else session.volume
            for speaker_id in session.speakers:
                try:
                    await self._plugin_manager.set_volume(speaker_id, target_volume)
                except Exception:
                    pass

        self._notify_state_change(session)
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Get a streaming session by ID."""
        return self._sessions.get(session_id)

    def get_sessions(self) -> list[StreamSession]:
        """Get all streaming sessions."""
        return list(self._sessions.values())

    def get_active_sessions(self) -> list[StreamSession]:
        """Get all currently playing sessions."""
        return [s for s in self._sessions.values() if s.state == StreamState.PLAYING]

    def get_sessions_for_speaker(self, speaker_id: str) -> list[StreamSession]:
        """Get all sessions that include a specific speaker."""
        return [s for s in self._sessions.values() if speaker_id in s.speakers]

    def get_session_for_theme(self, theme_id: str) -> Optional[StreamSession]:
        """Get active session for a theme (if any)."""
        for session in self._sessions.values():
            if session.theme_id == theme_id and session.state == StreamState.PLAYING:
                return session
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────────────

    def on_state_change(self, callback: Callable[[StreamSession], None]) -> Callable:
        """
        Subscribe to session state changes.

        Args:
            callback: Function called with StreamSession when state changes

        Returns:
            Unsubscribe function
        """
        self._on_state_change.append(callback)

        def unsubscribe():
            if callback in self._on_state_change:
                self._on_state_change.remove(callback)

        return unsubscribe

    def _notify_state_change(self, session: StreamSession) -> None:
        """Notify all listeners of a state change."""
        for callback in self._on_state_change:
            try:
                callback(session)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")


# Global streaming engine instance
_streaming_engine: Optional[StreamingEngine] = None


def get_streaming_engine() -> StreamingEngine:
    """Get the global streaming engine instance."""
    global _streaming_engine
    if _streaming_engine is None:
        _streaming_engine = StreamingEngine()
    return _streaming_engine


def init_streaming_engine(
    stream_base_url: Optional[str] = None,
    port: int = 8099,
    plugin_manager=None
) -> StreamingEngine:
    """
    Initialize the global streaming engine.

    Args:
        stream_base_url: Base URL for streams
        port: HTTP server port
        plugin_manager: PluginManager instance for speaker control

    Returns:
        Initialized StreamingEngine
    """
    global _streaming_engine
    _streaming_engine = StreamingEngine(stream_base_url, port)

    if plugin_manager:
        _streaming_engine.set_plugin_manager(plugin_manager)

    return _streaming_engine
