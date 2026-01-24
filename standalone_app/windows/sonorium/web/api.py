"""
Sonorium REST API

Provides endpoints for the web UI to manage sessions, speaker groups,
theme cycling, and retrieve speaker hierarchy.

CORE CODE: This module is shared across all platforms.
Uses dependency injection for platform-specific components.
"""

from __future__ import annotations

import asyncio
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File
from pydantic import BaseModel, Field

from ..core.state import SpeakerSelection, CycleConfig, NameSource, StateStore
from ..obs import logger
from ..version import get_version


# --- Request/Response Models ---

class SpeakerSelectionModel(BaseModel):
    """Speaker selection for creating/updating sessions or groups."""
    include_floors: list[str] = Field(default_factory=list)
    include_areas: list[str] = Field(default_factory=list)
    include_speakers: list[str] = Field(default_factory=list)
    exclude_areas: list[str] = Field(default_factory=list)
    exclude_speakers: list[str] = Field(default_factory=list)

    def to_selection(self) -> SpeakerSelection:
        return SpeakerSelection(
            include_floors=self.include_floors,
            include_areas=self.include_areas,
            include_speakers=self.include_speakers,
            exclude_areas=self.exclude_areas,
            exclude_speakers=self.exclude_speakers,
        )


class CycleConfigModel(BaseModel):
    """Theme cycling configuration."""
    enabled: bool = False
    interval_minutes: int = Field(default=60, ge=1, le=1440)  # 1 min to 24 hours
    randomize: bool = False
    theme_ids: list[str] = Field(default_factory=list)  # Empty = all themes

    def to_config(self) -> CycleConfig:
        return CycleConfig(
            enabled=self.enabled,
            interval_minutes=self.interval_minutes,
            randomize=self.randomize,
            theme_ids=self.theme_ids,
        )


class CycleConfigResponse(BaseModel):
    """Theme cycling configuration response."""
    enabled: bool
    interval_minutes: int
    randomize: bool
    theme_ids: list[str]


class CycleStatusResponse(BaseModel):
    """Current cycling status for a session."""
    enabled: bool
    interval_minutes: int
    randomize: bool
    theme_ids: list[str]
    next_change: Optional[str] = None  # ISO timestamp
    seconds_until_change: Optional[int] = None
    themes_in_rotation: int = 0


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    theme_id: Optional[str] = None
    preset_id: Optional[str] = None
    speaker_group_id: Optional[str] = None
    adhoc_selection: Optional[SpeakerSelectionModel] = None
    custom_name: Optional[str] = None
    volume: Optional[int] = Field(default=None, ge=0, le=100)
    cycle_config: Optional[CycleConfigModel] = None


class UpdateSessionRequest(BaseModel):
    """Request to update an existing session."""
    theme_id: Optional[str] = None
    preset_id: Optional[str] = None
    speaker_group_id: Optional[str] = None
    adhoc_selection: Optional[SpeakerSelectionModel] = None
    custom_name: Optional[str] = None
    volume: Optional[int] = Field(default=None, ge=0, le=100)
    cycle_config: Optional[CycleConfigModel] = None


class UpdateCycleRequest(BaseModel):
    """Request to update cycling configuration."""
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    randomize: Optional[bool] = None
    theme_ids: Optional[list[str]] = None


class SessionResponse(BaseModel):
    """Session details response."""
    id: str
    name: str
    name_source: str
    theme_id: Optional[str]
    preset_id: Optional[str] = None
    speaker_group_id: Optional[str]
    adhoc_selection: Optional[dict]
    volume: int
    is_playing: bool
    speakers: list[str]  # Resolved speaker list
    speaker_summary: str  # Human-readable summary
    channel_id: Optional[int] = None  # Assigned channel (if playing)
    cycle_config: CycleConfigResponse
    created_at: str
    last_played_at: Optional[str]


class CreateGroupRequest(BaseModel):
    """Request to create a new speaker group."""
    name: str
    icon: str = "mdi:speaker-group"
    include_floors: list[str] = Field(default_factory=list)
    include_areas: list[str] = Field(default_factory=list)
    include_speakers: list[str] = Field(default_factory=list)
    exclude_areas: list[str] = Field(default_factory=list)
    exclude_speakers: list[str] = Field(default_factory=list)


class UpdateGroupRequest(BaseModel):
    """Request to update an existing speaker group."""
    name: Optional[str] = None
    icon: Optional[str] = None
    include_floors: Optional[list[str]] = None
    include_areas: Optional[list[str]] = None
    include_speakers: Optional[list[str]] = None
    exclude_areas: Optional[list[str]] = None
    exclude_speakers: Optional[list[str]] = None


class GroupResponse(BaseModel):
    """Speaker group details response."""
    id: str
    name: str
    icon: str
    include_floors: list[str]
    include_areas: list[str]
    include_speakers: list[str]
    exclude_areas: list[str]
    exclude_speakers: list[str]
    speakers: list[str]  # Resolved speaker list
    speaker_count: int
    summary: str  # Human-readable summary
    created_at: str
    updated_at: str


class VolumeRequest(BaseModel):
    """Request to set volume."""
    volume: int = Field(ge=0, le=100)


class SettingsResponse(BaseModel):
    """Settings response."""
    default_volume: int
    crossfade_duration: float
    max_groups: int
    entity_prefix: str
    show_in_sidebar: bool
    auto_create_quick_play: bool
    master_gain: int
    default_cycle_interval: int
    default_cycle_randomize: bool


class UpdateSettingsRequest(BaseModel):
    """Request to update settings."""
    default_volume: Optional[int] = Field(default=None, ge=0, le=100)
    crossfade_duration: Optional[float] = Field(default=None, ge=0, le=10.0)
    max_groups: Optional[int] = Field(default=None, ge=1, le=50)
    entity_prefix: Optional[str] = None
    show_in_sidebar: Optional[bool] = None
    auto_create_quick_play: Optional[bool] = None
    master_gain: Optional[int] = Field(default=None, ge=0, le=100)
    default_cycle_interval: Optional[int] = Field(default=None, ge=1, le=1440)
    default_cycle_randomize: Optional[bool] = None


class SpeakerSettingsResponse(BaseModel):
    """Speaker settings response with hierarchy."""
    enabled_speakers: list[str]  # Empty = all enabled
    hierarchy: Optional[dict] = None  # Full speaker hierarchy


class UpdateSpeakerSettingsRequest(BaseModel):
    """Request to update enabled speakers."""
    enabled_speakers: list[str]


class SingleSpeakerRequest(BaseModel):
    """Request to enable/disable a single speaker."""
    entity_id: str


class PluginResponse(BaseModel):
    """Plugin details response."""
    id: str
    name: str
    version: str
    description: str
    author: str
    category: str = ""
    enabled: bool
    builtin: bool = False
    settings: dict
    ui_schema: dict
    settings_schema: dict
    has_api_routes: bool = False
    has_ha_entities: bool = False
    plugin_type: Optional[str] = None
    speakers: Optional[list] = None
    capabilities: Optional[dict] = None


class PluginActionRequest(BaseModel):
    """Request to execute a plugin action."""
    action: str
    data: dict = Field(default_factory=dict)


class PluginSettingsRequest(BaseModel):
    """Request to update plugin settings."""
    settings: dict


class ChannelResponse(BaseModel):
    """Channel status response."""
    id: int
    name: str
    state: str
    current_theme: Optional[str]
    current_theme_name: Optional[str]
    client_count: int
    stream_path: str


class StatusResponse(BaseModel):
    """System status response."""
    version: str
    state: str
    platform: str
    session_count: int
    playing_count: int
    speaker_count: int


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# --- Helper Functions ---

def _session_to_response(session, session_manager) -> SessionResponse:
    """Convert a Session to SessionResponse."""
    cycle_config = session.cycle_config or CycleConfig()
    return SessionResponse(
        id=session.id,
        name=session.name,
        name_source=session.name_source.value,
        theme_id=session.theme_id,
        preset_id=getattr(session, 'preset_id', None),
        speaker_group_id=session.speaker_group_id,
        adhoc_selection=asdict(session.adhoc_selection) if session.adhoc_selection else None,
        volume=session.volume,
        is_playing=session.is_playing,
        speakers=session_manager.get_resolved_speakers(session) if session_manager else [],
        speaker_summary=session_manager.get_speaker_summary(session) if session_manager else "",
        channel_id=session_manager.get_session_channel(session.id) if session_manager else None,
        cycle_config=CycleConfigResponse(
            enabled=cycle_config.enabled,
            interval_minutes=cycle_config.interval_minutes,
            randomize=cycle_config.randomize,
            theme_ids=cycle_config.theme_ids,
        ),
        created_at=session.created_at,
        last_played_at=session.last_played_at,
    )


# --- API Router Factory ---

def create_api_router(
    state_store: StateStore,
    session_manager=None,
    group_manager=None,
    speaker_registry=None,
    theme_manager=None,
    channel_manager=None,
    cycle_manager=None,
    plugin_manager=None,
    mqtt_manager=None,
    platform: str = "standalone",
) -> APIRouter:
    """
    Create the API router with all endpoints.

    Args:
        state_store: StateStore instance (required)
        session_manager: Optional SessionManager instance
        group_manager: Optional GroupManager instance
        speaker_registry: Optional speaker registry (HA registry or network discovery)
        theme_manager: Optional theme manager for theme endpoints
        channel_manager: Optional ChannelManager for channel-based streaming
        cycle_manager: Optional CycleManager for theme cycling
        plugin_manager: Optional PluginManager for plugin endpoints
        mqtt_manager: Optional MQTT manager for HA entity updates
        platform: Platform identifier (ha_addon, docker, standalone)

    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/api", tags=["api"])

    # --- Status/Heartbeat Endpoints ---

    @router.get("/status")
    async def get_status() -> StatusResponse:
        """Get system status."""
        sessions = list(state_store.sessions.values())
        playing = [s for s in sessions if s.is_playing]

        speaker_count = 0
        if speaker_registry:
            try:
                speakers = speaker_registry.get_all_speakers() if hasattr(speaker_registry, 'get_all_speakers') else []
                speaker_count = len(speakers) if speakers else 0
            except Exception:
                pass

        return StatusResponse(
            version=get_version(),
            state="playing" if playing else "idle",
            platform=platform,
            session_count=len(sessions),
            playing_count=len(playing),
            speaker_count=speaker_count,
        )

    @router.post("/heartbeat")
    async def heartbeat() -> dict:
        """Browser heartbeat endpoint for connection tracking."""
        return {"status": "ok"}

    # --- Session Endpoints ---

    @router.get("/sessions")
    async def list_sessions() -> list[SessionResponse]:
        """List all sessions."""
        sessions = list(state_store.sessions.values())
        return [_session_to_response(s, session_manager) for s in sessions]

    @router.post("/sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(request: CreateSessionRequest) -> SessionResponse:
        """Create a new session."""
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager not available")
        try:
            session = session_manager.create(
                theme_id=request.theme_id,
                preset_id=request.preset_id,
                speaker_group_id=request.speaker_group_id,
                adhoc_selection=request.adhoc_selection.to_selection() if request.adhoc_selection else None,
                custom_name=request.custom_name,
                volume=request.volume,
                cycle_config=request.cycle_config.to_config() if request.cycle_config else None,
            )
            return _session_to_response(session, session_manager)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str) -> SessionResponse:
        """Get a session by ID."""
        session = state_store.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return _session_to_response(session, session_manager)

    @router.put("/sessions/{session_id}")
    async def update_session(session_id: str, request: UpdateSessionRequest) -> SessionResponse:
        """Update an existing session."""
        if not session_manager:
            raise HTTPException(status_code=503, detail="Session manager not available")

        old_session = state_store.sessions.get(session_id)
        old_name = old_session.name if old_session else None

        session, added_speakers, removed_speakers = session_manager.update(
            session_id=session_id,
            theme_id=request.theme_id,
            preset_id=request.preset_id,
            speaker_group_id=request.speaker_group_id,
            adhoc_selection=request.adhoc_selection.to_selection() if request.adhoc_selection else None,
            custom_name=request.custom_name,
            volume=request.volume,
            cycle_config=request.cycle_config.to_config() if request.cycle_config else None,
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Apply live speaker changes if session is playing
        if added_speakers or removed_speakers:
            await session_manager.apply_speaker_changes(session, added_speakers, removed_speakers)

        # Refresh MQTT discovery if session name changed
        if mqtt_manager and old_name and session.name != old_name:
            try:
                await mqtt_manager.refresh_session_discovery(session)
            except Exception as e:
                logger.warning(f"Failed to refresh MQTT discovery for renamed session: {e}")

        return _session_to_response(session, session_manager)

    @router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_session(session_id: str):
        """Delete a session."""
        if not session_manager:
            # Direct deletion from state store
            if session_id not in state_store.sessions:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            del state_store.sessions[session_id]
            state_store.save()
        elif not session_manager.delete(session_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    @router.post("/sessions/{session_id}/play")
    async def play_session(session_id: str) -> dict:
        """Start playback for a session."""
        session = state_store.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        if not session.theme_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No theme selected")

        if session_manager:
            speakers = session_manager.get_resolved_speakers(session)
            if not speakers:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No speakers selected")

        # Mark as playing immediately (optimistic update)
        session.is_playing = True
        session.mark_played()
        state_store.save()

        # Fire the play command in the background if session_manager available
        if session_manager:
            asyncio.create_task(session_manager.play(session_id))

        return {
            "status": "playing",
            "channel_id": session_manager.get_session_channel(session_id) if session_manager else None,
            "cycling": session.cycle_config.enabled if session.cycle_config else False,
        }

    @router.post("/sessions/{session_id}/stop")
    async def stop_session(session_id: str) -> dict:
        """Stop playback for a session."""
        session = state_store.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        if session_manager:
            success = await session_manager.stop(session_id)
            if not success:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        else:
            session.is_playing = False
            state_store.save()

        return {"status": "stopped"}

    @router.post("/sessions/{session_id}/volume")
    async def set_session_volume(session_id: str, request: VolumeRequest) -> dict:
        """Set volume for a session."""
        session = state_store.sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        session.volume = request.volume
        state_store.save()

        if session_manager:
            await session_manager.set_volume(session_id, request.volume)

        return {"volume": request.volume}

    @router.post("/sessions/stop-all")
    async def stop_all_sessions() -> dict:
        """Stop all playing sessions."""
        count = 0
        if session_manager:
            count = await session_manager.stop_all()
        else:
            for session in state_store.sessions.values():
                if session.is_playing:
                    session.is_playing = False
                    count += 1
            state_store.save()
        return {"stopped": count}

    # --- Speaker Group Endpoints ---

    @router.get("/groups")
    async def list_groups() -> list[GroupResponse]:
        """List all speaker groups."""
        groups = list(state_store.speaker_groups.values())
        return [
            GroupResponse(
                id=g.id,
                name=g.name,
                icon=g.icon,
                include_floors=g.include_floors,
                include_areas=g.include_areas,
                include_speakers=g.include_speakers,
                exclude_areas=g.exclude_areas,
                exclude_speakers=g.exclude_speakers,
                speakers=group_manager.resolve(g) if group_manager else [],
                speaker_count=group_manager.get_speaker_count(g) if group_manager else 0,
                summary=group_manager.get_summary(g) if group_manager else "",
                created_at=g.created_at,
                updated_at=g.updated_at,
            )
            for g in groups
        ]

    @router.post("/groups", status_code=status.HTTP_201_CREATED)
    async def create_group(request: CreateGroupRequest) -> GroupResponse:
        """Create a new speaker group."""
        if not group_manager:
            raise HTTPException(status_code=503, detail="Group manager not available")
        try:
            group = group_manager.create(
                name=request.name,
                icon=request.icon,
                include_floors=request.include_floors,
                include_areas=request.include_areas,
                include_speakers=request.include_speakers,
                exclude_areas=request.exclude_areas,
                exclude_speakers=request.exclude_speakers,
            )
            return GroupResponse(
                id=group.id,
                name=group.name,
                icon=group.icon,
                include_floors=group.include_floors,
                include_areas=group.include_areas,
                include_speakers=group.include_speakers,
                exclude_areas=group.exclude_areas,
                exclude_speakers=group.exclude_speakers,
                speakers=group_manager.resolve(group),
                speaker_count=group_manager.get_speaker_count(group),
                summary=group_manager.get_summary(group),
                created_at=group.created_at,
                updated_at=group.updated_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    @router.get("/groups/{group_id}")
    async def get_group(group_id: str) -> GroupResponse:
        """Get a speaker group by ID."""
        group = state_store.speaker_groups.get(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return GroupResponse(
            id=group.id,
            name=group.name,
            icon=group.icon,
            include_floors=group.include_floors,
            include_areas=group.include_areas,
            include_speakers=group.include_speakers,
            exclude_areas=group.exclude_areas,
            exclude_speakers=group.exclude_speakers,
            speakers=group_manager.resolve(group) if group_manager else [],
            speaker_count=group_manager.get_speaker_count(group) if group_manager else 0,
            summary=group_manager.get_summary(group) if group_manager else "",
            created_at=group.created_at,
            updated_at=group.updated_at,
        )

    @router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_group(group_id: str):
        """Delete a speaker group."""
        if group_id not in state_store.speaker_groups:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

        # Check if any sessions use this group
        session_ids = [s.id for s in state_store.sessions.values() if s.speaker_group_id == group_id]
        if session_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Group is used by {len(session_ids)} session(s). Delete or update those sessions first."
            )

        if group_manager:
            group_manager.delete(group_id)
        else:
            del state_store.speaker_groups[group_id]
            state_store.save()

    # --- Speaker Endpoints ---

    @router.get("/speakers")
    async def list_speakers() -> list[dict]:
        """List all available speakers (flat list)."""
        if not speaker_registry:
            return []
        try:
            if hasattr(speaker_registry, 'hierarchy'):
                hierarchy = speaker_registry.hierarchy
                speakers = hierarchy.get_all_speakers()
                return [s.to_dict() for s in speakers]
            elif hasattr(speaker_registry, 'get_all_speakers'):
                speakers = speaker_registry.get_all_speakers()
                return [s.to_dict() if hasattr(s, 'to_dict') else s for s in speakers]
        except Exception as e:
            logger.error(f"Failed to list speakers: {e}")
        return []

    @router.get("/speakers/hierarchy")
    async def get_speaker_hierarchy() -> dict:
        """Get full floor/area/speaker hierarchy."""
        if not speaker_registry:
            return {"floors": [], "unassigned_areas": [], "unassigned_speakers": []}
        try:
            if hasattr(speaker_registry, 'hierarchy'):
                hierarchy = speaker_registry.hierarchy
                return hierarchy.to_dict()
            elif hasattr(speaker_registry, 'get_hierarchy_dict'):
                return speaker_registry.get_hierarchy_dict()
        except Exception as e:
            logger.error(f"Failed to get speaker hierarchy: {e}")
        return {"floors": [], "unassigned_areas": [], "unassigned_speakers": []}

    @router.post("/speakers/refresh")
    async def refresh_speakers() -> dict:
        """Refresh speaker hierarchy from discovery source."""
        if not speaker_registry:
            return {"status": "error", "message": "No speaker registry available"}
        try:
            if hasattr(speaker_registry, 'refresh'):
                hierarchy = speaker_registry.refresh()
                return {
                    "status": "ok",
                    "floors": len(hierarchy.floors) if hasattr(hierarchy, 'floors') else 0,
                    "total_speakers": len(hierarchy.get_all_speakers()) if hasattr(hierarchy, 'get_all_speakers') else 0,
                }
        except Exception as e:
            logger.error(f"Failed to refresh speakers: {e}")
            return {"status": "error", "message": str(e)}
        return {"status": "ok"}

    # --- Settings Endpoints ---

    @router.get("/settings")
    async def get_settings() -> SettingsResponse:
        """Get current settings."""
        settings = state_store.settings
        return SettingsResponse(
            default_volume=settings.default_volume,
            crossfade_duration=settings.crossfade_duration,
            max_groups=settings.max_groups,
            entity_prefix=settings.entity_prefix,
            show_in_sidebar=settings.show_in_sidebar,
            auto_create_quick_play=settings.auto_create_quick_play,
            master_gain=settings.master_gain,
            default_cycle_interval=settings.default_cycle_interval,
            default_cycle_randomize=settings.default_cycle_randomize,
        )

    @router.put("/settings")
    async def update_settings(request: UpdateSettingsRequest) -> SettingsResponse:
        """Update settings."""
        settings = state_store.settings

        if request.default_volume is not None:
            settings.default_volume = request.default_volume
        if request.crossfade_duration is not None:
            settings.crossfade_duration = request.crossfade_duration
        if request.max_groups is not None:
            settings.max_groups = request.max_groups
        if request.entity_prefix is not None:
            settings.entity_prefix = request.entity_prefix
        if request.show_in_sidebar is not None:
            settings.show_in_sidebar = request.show_in_sidebar
        if request.auto_create_quick_play is not None:
            settings.auto_create_quick_play = request.auto_create_quick_play
        if request.master_gain is not None:
            settings.master_gain = request.master_gain
        if request.default_cycle_interval is not None:
            settings.default_cycle_interval = request.default_cycle_interval
        if request.default_cycle_randomize is not None:
            settings.default_cycle_randomize = request.default_cycle_randomize

        state_store.save()

        return SettingsResponse(
            default_volume=settings.default_volume,
            crossfade_duration=settings.crossfade_duration,
            max_groups=settings.max_groups,
            entity_prefix=settings.entity_prefix,
            show_in_sidebar=settings.show_in_sidebar,
            auto_create_quick_play=settings.auto_create_quick_play,
            master_gain=settings.master_gain,
            default_cycle_interval=settings.default_cycle_interval,
            default_cycle_randomize=settings.default_cycle_randomize,
        )

    # --- Speaker Settings Endpoints ---

    @router.get("/settings/speakers")
    async def get_speaker_settings() -> SpeakerSettingsResponse:
        """Get enabled speakers and full hierarchy."""
        settings = state_store.settings
        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    @router.put("/settings/speakers")
    async def update_speaker_settings(request: UpdateSpeakerSettingsRequest) -> SpeakerSettingsResponse:
        """Update enabled speakers list."""
        settings = state_store.settings
        settings.enabled_speakers = request.enabled_speakers
        state_store.save()

        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    @router.post("/settings/speakers/enable")
    async def enable_speaker(request: SingleSpeakerRequest) -> SpeakerSettingsResponse:
        """Enable a single speaker."""
        settings = state_store.settings
        entity_id = request.entity_id

        if not settings.enabled_speakers:
            pass  # Empty = all enabled, nothing to do
        elif settings.enabled_speakers == ["__none__"]:
            settings.enabled_speakers = [entity_id]
            state_store.save()
        else:
            if entity_id not in settings.enabled_speakers:
                settings.enabled_speakers.append(entity_id)
                state_store.save()

        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    @router.post("/settings/speakers/disable")
    async def disable_speaker(request: SingleSpeakerRequest) -> SpeakerSettingsResponse:
        """Disable a single speaker and stop any active streams to it."""
        settings = state_store.settings
        entity_id = request.entity_id

        if not settings.enabled_speakers:
            # Get all speakers and add all except the one being disabled
            if speaker_registry and hasattr(speaker_registry, 'get_all_speaker_ids'):
                all_speakers = speaker_registry.get_all_speaker_ids()
                settings.enabled_speakers = [s for s in all_speakers if s != entity_id]
            else:
                raise HTTPException(status_code=400, detail="Cannot disable speaker: speaker list not available")
        else:
            if entity_id in settings.enabled_speakers:
                settings.enabled_speakers.remove(entity_id)

        # Stop streaming to this speaker if it's in any active session
        if session_manager and hasattr(session_manager, 'media_controller') and session_manager.media_controller:
            for session in state_store.sessions.values():
                if session.is_playing:
                    speakers = session_manager.get_resolved_speakers(session)
                    if entity_id in speakers:
                        logger.info(f"Stopping stream to disabled speaker: {entity_id}")
                        try:
                            await session_manager.media_controller.stop_multi([entity_id])
                        except Exception as e:
                            logger.warning(f"Failed to stop speaker {entity_id}: {e}")

        if not settings.enabled_speakers:
            settings.enabled_speakers = ["__none__"]

        state_store.save()

        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    @router.post("/settings/speakers/enable-all")
    async def enable_all_speakers() -> SpeakerSettingsResponse:
        """Enable all speakers (clear the enabled list)."""
        settings = state_store.settings
        settings.enabled_speakers = []  # Empty = all enabled
        state_store.save()

        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    @router.post("/settings/speakers/disable-all")
    async def disable_all_speakers() -> SpeakerSettingsResponse:
        """Disable all speakers and stop all active streams."""
        settings = state_store.settings

        # Stop all active streams
        if session_manager and hasattr(session_manager, 'media_controller') and session_manager.media_controller:
            for session in state_store.sessions.values():
                if session.is_playing:
                    speakers = session_manager.get_resolved_speakers(session)
                    if speakers:
                        logger.info(f"Stopping streams for disable-all: {speakers}")
                        try:
                            await session_manager.media_controller.stop_multi(speakers)
                        except Exception as e:
                            logger.warning(f"Failed to stop speakers: {e}")

        settings.enabled_speakers = ["__none__"]
        state_store.save()

        hierarchy = None
        if speaker_registry and hasattr(speaker_registry, 'get_hierarchy_dict'):
            hierarchy = speaker_registry.get_hierarchy_dict()
        return SpeakerSettingsResponse(
            enabled_speakers=settings.enabled_speakers,
            hierarchy=hierarchy,
        )

    # --- Plugin Endpoints ---

    @router.get("/plugins")
    async def list_plugins():
        """List all available plugins."""
        if not plugin_manager:
            return []
        return plugin_manager.list_plugins()

    @router.get("/plugins/{plugin_id}")
    async def get_plugin(plugin_id: str):
        """Get details for a specific plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        plugin = plugin_manager.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")

        return plugin.to_dict()

    @router.put("/plugins/{plugin_id}/enable")
    async def enable_plugin(plugin_id: str):
        """Enable a plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        success = await plugin_manager.enable_plugin(plugin_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to enable plugin: {plugin_id}")

        return {"status": "ok", "plugin_id": plugin_id, "enabled": True}

    @router.put("/plugins/{plugin_id}/disable")
    async def disable_plugin(plugin_id: str):
        """Disable a plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        success = await plugin_manager.disable_plugin(plugin_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to disable plugin: {plugin_id}")

        return {"status": "ok", "plugin_id": plugin_id, "enabled": False}

    @router.put("/plugins/{plugin_id}/settings")
    async def update_plugin_settings(plugin_id: str, request: PluginSettingsRequest):
        """Update settings for a plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        success = plugin_manager.update_plugin_settings(plugin_id, request.settings)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to update plugin settings: {plugin_id}")

        return {"status": "ok", "plugin_id": plugin_id, "settings": request.settings}

    @router.post("/plugins/{plugin_id}/action")
    async def execute_plugin_action(plugin_id: str, request: PluginActionRequest):
        """Execute an action on a plugin."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        result = await plugin_manager.call_action(plugin_id, request.action, request.data)
        return result

    @router.post("/plugins/reload")
    async def reload_plugins():
        """Reload all plugins."""
        if not plugin_manager:
            raise HTTPException(status_code=503, detail="Plugin system not available")

        await plugin_manager.reload_plugins()
        return {"status": "ok", "message": "Plugins reloaded", "count": len(plugin_manager.plugins)}

    # --- Channel Endpoints ---

    @router.get("/channels")
    async def list_channels() -> list[ChannelResponse]:
        """List all channels."""
        if not channel_manager:
            return []
        return [
            ChannelResponse(**ch)
            for ch in channel_manager.list_channels()
        ]

    @router.get("/channels/{channel_id}")
    async def get_channel(channel_id: int) -> ChannelResponse:
        """Get a specific channel."""
        if not channel_manager:
            raise HTTPException(status_code=503, detail="Channel system not initialized")
        channel = channel_manager.get_channel(channel_id)
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
        return ChannelResponse(**channel.to_dict())

    return router
