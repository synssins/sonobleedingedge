"""
Session Manager

Handles CRUD operations for playback sessions, including:
- Creating sessions with auto-naming
- Updating session configuration
- Play/pause/stop control with channel-based streaming
- Volume management
- Seamless theme transitions via channel crossfading
- Theme cycling integration

CORE CODE: This module is shared across all platforms.
The speaker_registry and media_controller are optional and can be provided
by platform-specific implementations (HA addon, standalone, etc.).
"""

from __future__ import annotations

import uuid
from typing import Optional, TYPE_CHECKING, Protocol, Any

from .state import (
    Session,
    SpeakerSelection,
    SpeakerGroup,
    CycleConfig,
    NameSource,
    StateStore,
)
from ..obs import logger

if TYPE_CHECKING:
    from .cycle_manager import CycleManager
    from .theme_metadata import ThemeMetadataManager
    from .utils import IndexList


class SpeakerRegistry(Protocol):
    """Protocol for speaker registry implementations."""

    def get_floor_name(self, floor_id: str) -> str:
        ...

    def get_area_name(self, area_id: str) -> str:
        ...

    def get_speaker_name(self, speaker_id: str) -> str:
        ...

    def resolve_selection(
        self,
        include_floors: list[str] = None,
        include_areas: list[str] = None,
        include_speakers: list[str] = None,
        exclude_areas: list[str] = None,
        exclude_speakers: list[str] = None,
    ) -> list[str]:
        ...


class MediaController(Protocol):
    """Protocol for media controller implementations."""

    async def play_media_multi(self, speakers: list[str], url: str) -> dict[str, bool]:
        ...

    async def stop_multi(self, speakers: list[str]) -> dict[str, bool]:
        ...

    async def pause_multi(self, speakers: list[str]) -> dict[str, bool]:
        ...

    async def set_volume_multi(self, speakers: list[str], volume: float) -> dict[str, bool]:
        ...


class ChannelManager(Protocol):
    """Protocol for channel manager implementations."""

    def get_channel(self, channel_id: int) -> Any:
        ...

    def get_available_channel(self) -> Any:
        ...


class SessionManager:
    """
    Manages playback sessions.

    Each session represents one theme playing to one set of speakers.
    Multiple sessions can run simultaneously on different channels.

    The speaker_registry and media_controller are optional - when not provided,
    speaker resolution returns empty lists and playback commands are no-ops.
    """

    def __init__(
        self,
        state_store: StateStore,
        speaker_registry: Optional[SpeakerRegistry] = None,
        media_controller: Optional[MediaController] = None,
        stream_base_url: str = None,
        channel_manager: Optional[ChannelManager] = None,
        cycle_manager: Optional[CycleManager] = None,
        themes: Optional[IndexList] = None,
        theme_metadata_manager: Optional[ThemeMetadataManager] = None,
    ):
        self.state = state_store
        self.registry = speaker_registry
        self.media_controller = media_controller
        self.stream_base_url = stream_base_url or "http://localhost:8008"
        self.channel_manager = channel_manager
        self.cycle_manager = cycle_manager
        self.themes = themes
        self.theme_metadata_manager = theme_metadata_manager

        # Track which session is using which channel: session_id -> channel_id
        self._session_channels: dict[str, int] = {}

    def set_speaker_registry(self, registry: SpeakerRegistry):
        """Set the speaker registry (for deferred initialization)."""
        self.registry = registry

    def set_media_controller(self, controller: MediaController):
        """Set the media controller (for deferred initialization)."""
        self.media_controller = controller

    def set_stream_base_url(self, url: str):
        """Set the stream base URL."""
        self.stream_base_url = url.rstrip("/")

    def set_channel_manager(self, manager: ChannelManager):
        """Set the channel manager (for deferred initialization)."""
        self.channel_manager = manager

    def set_cycle_manager(self, cycle_manager: CycleManager):
        """Set the cycle manager (for deferred initialization)."""
        self.cycle_manager = cycle_manager

    def set_themes(self, themes: IndexList):
        """Update themes reference (called after theme refresh)."""
        self.themes = themes
        logger.info(f"  SessionManager: Updated themes reference ({len(themes)} themes)")

    def set_theme_metadata_manager(self, manager: ThemeMetadataManager):
        """Set the theme metadata manager (for deferred initialization)."""
        self.theme_metadata_manager = manager

    def get_theme(self, theme_id: str) -> Optional[Any]:
        """Get a theme by ID."""
        if not self.themes:
            return None

        # Direct lookup
        theme = self.themes.id.get(theme_id)
        if theme:
            return theme

        return None

    def get_stream_url(self, session: Session) -> str:
        """
        Get the stream URL for a session.

        Uses channel-based URL if channel is assigned, otherwise falls back to theme URL.
        """
        channel_id = self._session_channels.get(session.id)
        if channel_id:
            return f"{self.stream_base_url}/stream/channel{channel_id}"
        # Fallback to theme-based URL (legacy)
        return f"{self.stream_base_url}/stream/{session.theme_id}"

    def _assign_channel(self, session: Session) -> Optional[Any]:
        """
        Assign an available channel to a session.

        Returns the assigned channel, or None if no channels available.
        """
        if not self.channel_manager:
            return None

        # Check if session already has a channel
        existing_id = self._session_channels.get(session.id)
        if existing_id:
            return self.channel_manager.get_channel(existing_id)

        # Get an available channel
        channel = self.channel_manager.get_available_channel()
        if channel:
            self._session_channels[session.id] = channel.id
            logger.info(f"  Assigned channel {channel.id} to session {session.id}")

        return channel

    def _release_channel(self, session_id: str):
        """Release a channel from a session."""
        channel_id = self._session_channels.pop(session_id, None)
        if channel_id and self.channel_manager:
            channel = self.channel_manager.get_channel(channel_id)
            if channel:
                channel.stop()
                logger.info(f"  Released channel {channel_id} from session {session_id}")

    def get_session_channel(self, session_id: str) -> Optional[int]:
        """Get the channel ID assigned to a session."""
        return self._session_channels.get(session_id)

    # --- Auto-naming ---

    def generate_session_name(
        self,
        selection: SpeakerSelection = None,
        group: SpeakerGroup = None,
    ) -> tuple[str, NameSource]:
        """
        Generate a session name based on speaker selection.

        Returns:
            Tuple of (name, source)
        """
        # If using a saved group, use its name
        if group:
            return (group.name, NameSource.AUTO_GROUP)

        if not selection or not self.registry:
            return ("New Session", NameSource.CUSTOM)

        # Single floor selected (with possible exclusions)
        if (len(selection.include_floors) == 1 and
            not selection.include_areas and
            not selection.include_speakers):
            floor_name = self.registry.get_floor_name(selection.include_floors[0])
            return (floor_name, NameSource.AUTO_FLOOR)

        # Single area selected
        if (len(selection.include_areas) == 1 and
            not selection.include_floors and
            not selection.include_speakers):
            area_name = self.registry.get_area_name(selection.include_areas[0])
            return (area_name, NameSource.AUTO_AREA)

        # Multiple areas (no floors)
        if selection.include_areas and not selection.include_floors:
            area_names = [self.registry.get_area_name(a) for a in selection.include_areas]
            if len(area_names) == 2:
                return (f"{area_names[0]} & {area_names[1]}", NameSource.AUTO_AREA)
            elif len(area_names) > 2:
                return (f"{area_names[0]} + {len(area_names) - 1} more", NameSource.AUTO_AREA)

        # Single speaker selected
        if (len(selection.include_speakers) == 1 and
            not selection.include_floors and
            not selection.include_areas):
            speaker_name = self.registry.get_speaker_name(selection.include_speakers[0])
            return (speaker_name, NameSource.AUTO_AREA)

        # Fallback: count resolved speakers
        resolved = self.registry.resolve_selection(
            include_floors=selection.include_floors,
            include_areas=selection.include_areas,
            include_speakers=selection.include_speakers,
            exclude_areas=selection.exclude_areas,
            exclude_speakers=selection.exclude_speakers,
        )
        return (f"{len(resolved)} Speakers", NameSource.AUTO_AREA)

    # --- CRUD Operations ---

    def _get_next_channel_number(self) -> int:
        """Get the next available channel number (1-based)."""
        used_numbers = set()
        for session in self.state.sessions.values():
            if session.name.startswith("Channel "):
                try:
                    num = int(session.name[8:])
                    used_numbers.add(num)
                except ValueError:
                    pass

        channel_num = 1
        while channel_num in used_numbers:
            channel_num += 1

        return channel_num

    def create(
        self,
        theme_id: str = None,
        preset_id: str = None,
        speaker_group_id: str = None,
        adhoc_selection: SpeakerSelection = None,
        custom_name: str = None,
        volume: int = None,
        cycle_config: CycleConfig = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            theme_id: Theme to play (optional, can set later)
            preset_id: Theme preset to apply (optional)
            speaker_group_id: Saved speaker group to use
            adhoc_selection: Ad-hoc speaker selection (if not using group)
            custom_name: Custom name (overrides auto-naming)
            volume: Initial volume (uses default if not specified)
            cycle_config: Theme cycling configuration (optional)

        Returns:
            Created session

        Raises:
            ValueError: If max sessions exceeded
        """
        max_sessions = 20
        if len(self.state.sessions) >= max_sessions:
            raise ValueError(f"Maximum of {max_sessions} sessions allowed")

        session_id = str(uuid.uuid4())[:8]

        if custom_name:
            name = custom_name
            name_source = NameSource.CUSTOM
        else:
            channel_num = self._get_next_channel_number()
            name = f"Channel {channel_num}"
            name_source = NameSource.CUSTOM

        if volume is None:
            volume = self.state.settings.default_volume

        if cycle_config is None:
            cycle_config = CycleConfig(
                enabled=False,
                interval_minutes=self.state.settings.default_cycle_interval,
                randomize=self.state.settings.default_cycle_randomize,
            )

        session = Session(
            id=session_id,
            name=name,
            name_source=name_source,
            theme_id=theme_id,
            preset_id=preset_id,
            speaker_group_id=speaker_group_id,
            adhoc_selection=adhoc_selection,
            volume=volume,
            is_playing=False,
            cycle_config=cycle_config,
        )

        self.state.sessions[session_id] = session
        self.state.save()

        logger.info(f"  Created session '{session.name}' ({session_id})")
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.state.sessions.get(session_id)

    def list(self) -> list[Session]:
        """List all sessions, sorted by creation time."""
        sessions = list(self.state.sessions.values())
        sessions.sort(key=lambda s: s.created_at)
        return sessions

    def update(
        self,
        session_id: str,
        theme_id: str = None,
        preset_id: str = None,
        speaker_group_id: str = None,
        adhoc_selection: SpeakerSelection = None,
        custom_name: str = None,
        volume: int = None,
        cycle_config: CycleConfig = None,
    ) -> tuple[Optional[Session], set, set]:
        """
        Update an existing session.

        Returns:
            Tuple of (session, added_speakers, removed_speakers)
        """
        session = self.state.sessions.get(session_id)
        if not session:
            logger.warning(f"  Session {session_id} not found")
            return None, set(), set()

        theme_changed = theme_id is not None and theme_id != session.theme_id
        old_speakers = set(self.get_resolved_speakers(session)) if session.is_playing else set()
        speakers_changing = speaker_group_id is not None or adhoc_selection is not None

        if theme_id is not None:
            session.theme_id = theme_id

        if preset_id is not None:
            session.preset_id = preset_id

        if speaker_group_id is not None:
            session.speaker_group_id = speaker_group_id
            session.adhoc_selection = None

        if adhoc_selection is not None:
            session.adhoc_selection = adhoc_selection
            session.speaker_group_id = None

        if custom_name is not None:
            session.name = custom_name
            session.name_source = NameSource.CUSTOM

        if volume is not None:
            session.volume = max(0, min(100, volume))

        if cycle_config is not None:
            session.cycle_config = cycle_config

        if custom_name is None and session.name_source != NameSource.CUSTOM:
            group = None
            if session.speaker_group_id:
                group = self.state.speaker_groups.get(session.speaker_group_id)
            session.name, session.name_source = self.generate_session_name(
                session.adhoc_selection, group
            )

        self.state.save()

        if session.is_playing and theme_changed and session.theme_id:
            self._trigger_theme_crossfade(session)
            if self.cycle_manager:
                self.cycle_manager.reset_cycle(session_id)

        added_speakers = set()
        removed_speakers = set()
        if session.is_playing and speakers_changing:
            new_speakers = set(self.get_resolved_speakers(session))
            added_speakers = new_speakers - old_speakers
            removed_speakers = old_speakers - new_speakers

        logger.info(f"  Updated session '{session.name}'")
        return session, added_speakers, removed_speakers

    def _trigger_theme_crossfade(self, session: Session):
        """Trigger a theme crossfade on the session's channel."""
        channel_id = self._session_channels.get(session.id)
        if not channel_id or not self.channel_manager:
            return

        channel = self.channel_manager.get_channel(channel_id)
        if not channel:
            return

        theme = self.get_theme(session.theme_id)
        if not theme:
            return

        logger.info(f"  Triggering crossfade to '{theme.name}' on channel {channel_id}")
        channel.set_theme(theme)

    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id not in self.state.sessions:
            logger.warning(f"  Session {session_id} not found")
            return False

        self._release_channel(session_id)
        session = self.state.sessions.pop(session_id)
        self.state.save()

        logger.info(f"  Deleted session '{session.name}'")
        return True

    # --- Speaker Resolution ---

    def get_resolved_speakers(self, session: Session) -> list[str]:
        """Get the list of speaker entity_ids for a session."""
        if not self.registry:
            return []

        if session.speaker_group_id:
            group = self.state.speaker_groups.get(session.speaker_group_id)
            if group:
                return self.registry.resolve_selection(
                    include_floors=group.include_floors,
                    include_areas=group.include_areas,
                    include_speakers=group.include_speakers,
                    exclude_areas=group.exclude_areas,
                    exclude_speakers=group.exclude_speakers,
                )

        if session.adhoc_selection:
            sel = session.adhoc_selection
            return self.registry.resolve_selection(
                include_floors=sel.include_floors,
                include_areas=sel.include_areas,
                include_speakers=sel.include_speakers,
                exclude_areas=sel.exclude_areas,
                exclude_speakers=sel.exclude_speakers,
            )

        return []

    def get_speaker_summary(self, session: Session) -> str:
        """Get human-readable speaker summary for a session."""
        speakers = self.get_resolved_speakers(session)

        if not speakers:
            return "No speakers"

        if len(speakers) == 1 and self.registry:
            return self.registry.get_speaker_name(speakers[0])

        excluded_count = 0
        if session.speaker_group_id:
            group = self.state.speaker_groups.get(session.speaker_group_id)
            if group:
                excluded_count = len(group.exclude_areas) + len(group.exclude_speakers)
        elif session.adhoc_selection:
            sel = session.adhoc_selection
            excluded_count = len(sel.exclude_areas) + len(sel.exclude_speakers)

        if excluded_count > 0:
            return f"{len(speakers)} speakers ({excluded_count} excluded)"

        return f"{len(speakers)} speakers"

    # --- Playback Control ---

    async def play(self, session_id: str) -> bool:
        """Start playback for a session."""
        session = self.state.sessions.get(session_id)
        if not session:
            logger.warning(f"  Session {session_id} not found")
            return False

        if not session.theme_id:
            logger.warning(f"  Session has no theme selected")
            return False

        speakers = self.get_resolved_speakers(session)
        if not speakers:
            logger.warning(f"  Session has no speakers")
            return False

        if not self.media_controller:
            logger.warning(f"  No media controller available")
            return False

        channel = self._assign_channel(session)
        if channel:
            theme = self.get_theme(session.theme_id)
            if theme:
                channel.set_theme(theme)
                logger.info(f"  Channel {channel.id}: theme '{theme.name}'")

        stream_url = self.get_stream_url(session)
        logger.info(f"  Stream URL: {stream_url}")

        session.is_playing = True
        session.mark_played()
        self.state.save()

        if session.cycle_config.enabled and self.cycle_manager:
            self.cycle_manager.reset_cycle(session_id)
            logger.info(f"  Cycle enabled: every {session.cycle_config.interval_minutes}m")

        import asyncio
        asyncio.create_task(self._play_on_speakers(session, speakers, stream_url))

        return True

    async def _play_on_speakers(self, session: Session, speakers: list[str], stream_url: str):
        """Background task to play media on speakers."""
        try:
            results = await self.media_controller.play_media_multi(speakers, stream_url)
            volume_level = session.volume / 100.0
            await self.media_controller.set_volume_multi(speakers, volume_level)
            success_count = sum(1 for v in results.values() if v)
            logger.info(f"  Started playback on {success_count}/{len(speakers)} speakers")
        except Exception as e:
            logger.error(f"  Error starting playback: {e}")

    async def pause(self, session_id: str) -> bool:
        """Pause playback for a session."""
        session = self.state.sessions.get(session_id)
        if not session:
            logger.warning(f"  Session {session_id} not found")
            return False

        speakers = self.get_resolved_speakers(session)

        if self.media_controller and speakers:
            await self.media_controller.pause_multi(speakers)

        session.is_playing = False
        self.state.save()

        logger.info(f"  Paused session '{session.name}'")
        return True

    async def stop(self, session_id: str) -> bool:
        """Stop playback for a session."""
        session = self.state.sessions.get(session_id)
        if not session:
            logger.warning(f"  Session {session_id} not found")
            return False

        speakers = self.get_resolved_speakers(session)

        if self.media_controller and speakers:
            await self.media_controller.stop_multi(speakers)

        self._release_channel(session_id)

        session.is_playing = False
        self.state.save()

        logger.info(f"  Stopped session '{session.name}'")
        return True

    async def set_volume(self, session_id: str, volume: int) -> bool:
        """Set volume for a session."""
        session = self.state.sessions.get(session_id)
        if not session:
            logger.warning(f"  Session {session_id} not found")
            return False

        session.volume = max(0, min(100, volume))
        self.state.save()

        if session.is_playing and self.media_controller:
            speakers = self.get_resolved_speakers(session)
            if speakers:
                volume_level = session.volume / 100.0
                await self.media_controller.set_volume_multi(speakers, volume_level)

        logger.info(f"  Set volume to {session.volume}%")
        return True

    async def stop_all(self) -> int:
        """Stop all playing sessions."""
        count = 0
        for session in self.state.sessions.values():
            if session.is_playing:
                await self.stop(session.id)
                count += 1
        return count
