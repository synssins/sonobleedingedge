"""
Audio Mixer.

Handles mixing multiple audio tracks according to theme settings.
Generates the combined audio stream that is served to speakers.
"""

import asyncio
import logging
import random
import time
import threading
import io
from dataclasses import dataclass, field
from typing import Optional, Iterator, Callable, BinaryIO
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class TrackState(str, Enum):
    """Track playback states."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    WAITING = "waiting"  # Waiting for next play (sparse mode)


@dataclass
class ActiveTrack:
    """
    Represents an active track being mixed.

    Contains the track settings and current playback state.
    """
    id: str
    name: str
    file_path: Path
    volume: float = 1.0
    presence: float = 1.0
    playback_mode: str = "loop"  # loop, presence, sparse, random
    seamless_loop: bool = False
    exclusive: bool = False
    muted: bool = False

    # Runtime state
    state: TrackState = TrackState.STOPPED
    position: float = 0.0  # Current position in seconds
    duration: float = 0.0  # Total duration in seconds
    next_play_time: float = 0.0  # For sparse mode

    # Audio data (loaded on demand)
    _audio_data: Optional[bytes] = field(default=None, repr=False)
    _sample_rate: int = 44100
    _channels: int = 2

    def should_play_now(self) -> bool:
        """Determine if this track should be playing based on mode and presence."""
        if self.muted:
            return False

        if self.playback_mode == "loop":
            return True

        elif self.playback_mode == "presence":
            # Play based on presence probability each check
            return random.random() < self.presence

        elif self.playback_mode == "sparse":
            # Play occasionally, with gaps
            current_time = time.time()
            if current_time >= self.next_play_time:
                if random.random() < self.presence:
                    return True
            return self.state == TrackState.PLAYING

        elif self.playback_mode == "random":
            return random.random() < (self.presence * 0.1)  # Less frequent

        return False

    def schedule_next_play(self) -> None:
        """Schedule the next play time for sparse mode."""
        if self.playback_mode == "sparse":
            # Gap between plays: 10-60 seconds, scaled by presence
            min_gap = 10 * (1 - self.presence + 0.1)
            max_gap = 60 * (1 - self.presence + 0.1)
            gap = random.uniform(min_gap, max_gap)
            self.next_play_time = time.time() + self.duration + gap


@dataclass
class MixerSession:
    """
    Represents an active mixing session.

    A session mixes multiple tracks according to theme settings.
    """
    id: str
    theme_id: str
    tracks: dict[str, ActiveTrack] = field(default_factory=dict)
    master_volume: float = 1.0
    muted: bool = False
    playing: bool = False
    created_at: float = field(default_factory=time.time)

    # Mixing parameters
    sample_rate: int = 44100
    channels: int = 2
    bits_per_sample: int = 16

    # Internal state
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "theme_id": self.theme_id,
            "tracks": {tid: {"name": t.name, "state": t.state.value, "volume": t.volume}
                       for tid, t in self.tracks.items()},
            "master_volume": self.master_volume,
            "muted": self.muted,
            "playing": self.playing,
            "created_at": self.created_at,
        }


class AudioMixer:
    """
    Mixes multiple audio tracks into a single stream.

    The mixer:
    1. Loads audio files from themes
    2. Applies track settings (volume, presence, playback mode)
    3. Mixes tracks in real-time
    4. Outputs a continuous audio stream

    The output can be served via HTTP to network speakers.
    """

    def __init__(self, themes_dir: Optional[Path] = None):
        """
        Initialize the audio mixer.

        Args:
            themes_dir: Directory containing theme folders
        """
        self.themes_dir = themes_dir
        self._sessions: dict[str, MixerSession] = {}
        self._lock = threading.Lock()

        # Audio format settings
        self.sample_rate = 44100
        self.channels = 2
        self.bits_per_sample = 16

    # ─────────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        theme_id: str,
        theme_path: Path,
        track_settings: dict
    ) -> MixerSession:
        """
        Create a new mixing session for a theme.

        Args:
            session_id: Unique session identifier
            theme_id: Theme identifier
            theme_path: Path to theme folder containing audio files
            track_settings: Dict of track_name -> settings

        Returns:
            The created MixerSession
        """
        session = MixerSession(
            id=session_id,
            theme_id=theme_id,
            sample_rate=self.sample_rate,
            channels=self.channels,
            bits_per_sample=self.bits_per_sample,
        )

        # Load tracks
        for track_name, settings in track_settings.items():
            # Find audio file
            audio_path = theme_path / track_name
            if not audio_path.exists():
                # Try without extension or with different extensions
                for ext in [".mp3", ".wav", ".ogg", ".flac"]:
                    test_path = theme_path / f"{track_name}{ext}"
                    if test_path.exists():
                        audio_path = test_path
                        break

            if not audio_path.exists():
                logger.warning(f"Audio file not found: {track_name} in {theme_path}")
                continue

            track = ActiveTrack(
                id=track_name,
                name=settings.get("name", track_name),
                file_path=audio_path,
                volume=settings.get("volume", 1.0),
                presence=settings.get("presence", 1.0),
                playback_mode=settings.get("playback_mode", "loop"),
                seamless_loop=settings.get("seamless_loop", False),
                exclusive=settings.get("exclusive", False),
                muted=settings.get("muted", False),
            )

            session.tracks[track_name] = track

        with self._lock:
            self._sessions[session_id] = session

        logger.info(f"Created mixer session {session_id} with {len(session.tracks)} tracks")
        return session

    def get_session(self, session_id: str) -> Optional[MixerSession]:
        """Get a mixing session by ID."""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> bool:
        """Remove and stop a mixing session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session._stop_event.set()
                session.playing = False
                del self._sessions[session_id]
                logger.info(f"Removed mixer session {session_id}")
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Playback Control
    # ─────────────────────────────────────────────────────────────────────

    def start_session(self, session_id: str) -> bool:
        """Start mixing for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session._stop_event.clear()
        session.playing = True

        for track in session.tracks.values():
            track.state = TrackState.PLAYING

        logger.info(f"Started mixer session {session_id}")
        return True

    def stop_session(self, session_id: str) -> bool:
        """Stop mixing for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return True

        session._stop_event.set()
        session.playing = False

        for track in session.tracks.values():
            track.state = TrackState.STOPPED

        logger.info(f"Stopped mixer session {session_id}")
        return True

    def set_session_volume(self, session_id: str, volume: float) -> bool:
        """Set master volume for a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.master_volume = max(0.0, min(1.0, volume))
        return True

    def mute_session(self, session_id: str, muted: bool = True) -> bool:
        """Mute or unmute a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.muted = muted
        return True

    def set_track_volume(self, session_id: str, track_id: str, volume: float) -> bool:
        """Set volume for a specific track."""
        session = self._sessions.get(session_id)
        if not session or track_id not in session.tracks:
            return False

        session.tracks[track_id].volume = max(0.0, min(1.0, volume))
        return True

    def mute_track(self, session_id: str, track_id: str, muted: bool = True) -> bool:
        """Mute or unmute a specific track."""
        session = self._sessions.get(session_id)
        if not session or track_id not in session.tracks:
            return False

        session.tracks[track_id].muted = muted
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Audio Stream Generation
    # ─────────────────────────────────────────────────────────────────────

    def get_audio_stream(self, session_id: str) -> Iterator[bytes]:
        """
        Generator that yields mixed audio chunks for streaming.

        This is the main output method - yields continuous audio
        that can be served via HTTP.

        Args:
            session_id: Session to stream

        Yields:
            Audio data chunks (PCM or encoded)
        """
        session = self._sessions.get(session_id)
        if not session:
            return

        # Start session if not already playing
        if not session.playing:
            self.start_session(session_id)

        # Chunk size for output (about 0.1 seconds of audio)
        chunk_samples = int(session.sample_rate * 0.1)
        bytes_per_sample = session.bits_per_sample // 8 * session.channels
        chunk_size = chunk_samples * bytes_per_sample

        while not session._stop_event.is_set():
            try:
                # Mix audio chunk
                chunk = self._mix_chunk(session, chunk_samples)

                if chunk:
                    yield chunk
                else:
                    # No audio - yield silence
                    yield self._generate_silence(chunk_size)

                # Small delay to control output rate
                time.sleep(0.08)  # Slightly less than chunk duration

            except Exception as e:
                logger.error(f"Error generating audio chunk: {e}")
                yield self._generate_silence(chunk_size)

    def _mix_chunk(self, session: MixerSession, samples: int) -> Optional[bytes]:
        """
        Mix a chunk of audio from all active tracks.

        Args:
            session: Mixing session
            samples: Number of samples to generate

        Returns:
            Mixed audio bytes or None
        """
        # This is a simplified implementation
        # A production version would use proper audio libraries
        # like pydub, sounddevice, or miniaudio

        if session.muted:
            return None

        # For now, return None - actual mixing requires audio libraries
        # This will be implemented when audio processing is added
        return None

    def _generate_silence(self, size: int) -> bytes:
        """Generate silent audio data."""
        return b'\x00' * size

    # ─────────────────────────────────────────────────────────────────────
    # HTTP Stream Helpers
    # ─────────────────────────────────────────────────────────────────────

    def get_stream_content_type(self) -> str:
        """Get the content type for the audio stream."""
        return "audio/wav"  # Or audio/mpeg for MP3

    def get_stream_headers(self, session_id: str) -> dict:
        """
        Get HTTP headers for streaming.

        Returns headers suitable for continuous audio streaming.
        """
        return {
            "Content-Type": self.get_stream_content_type(),
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }


# Global mixer instance
_audio_mixer: Optional[AudioMixer] = None


def get_audio_mixer() -> AudioMixer:
    """Get the global audio mixer instance."""
    global _audio_mixer
    if _audio_mixer is None:
        _audio_mixer = AudioMixer()
    return _audio_mixer


def init_audio_mixer(themes_dir: Optional[Path] = None) -> AudioMixer:
    """
    Initialize the global audio mixer.

    Args:
        themes_dir: Directory containing themes

    Returns:
        Initialized AudioMixer
    """
    global _audio_mixer
    _audio_mixer = AudioMixer(themes_dir)
    return _audio_mixer
