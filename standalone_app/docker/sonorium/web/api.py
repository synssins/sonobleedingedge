"""
Sonorium REST API.

All application functionality is exposed through this API.
MQTT, Web UI, and external integrations all use these endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..core.state import get_state_manager, StateManager
from .app import get_version
from ..models import (
    Speaker,
    Theme,
    Session,
    Channel,
    Settings,
    SessionState,
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api", tags=["Sonorium API"])


# ─────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────

class SpeakerResponse(BaseModel):
    """Speaker data in API response."""
    id: str
    name: str
    protocol: str
    host: str
    port: Optional[int] = None
    enabled: bool
    state: str
    volume: float
    muted: bool
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    ha_entity_id: Optional[str] = None
    ha_area: Optional[str] = None

    @classmethod
    def from_speaker(cls, speaker: Speaker) -> "SpeakerResponse":
        return cls(
            id=speaker.id,
            name=speaker.name,
            protocol=speaker.protocol.value,
            host=speaker.host,
            port=speaker.port,
            enabled=speaker.enabled,
            state=speaker.state.value,
            volume=speaker.volume,
            muted=speaker.muted,
            model=speaker.model,
            manufacturer=speaker.manufacturer,
            ha_entity_id=speaker.ha_entity_id,
            ha_area=speaker.ha_area,
        )


class SpeakerVolumeRequest(BaseModel):
    """Request to set speaker volume."""
    volume: float = Field(..., ge=0.0, le=1.0)


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    theme_id: str
    speaker_ids: list[str]
    channel_id: Optional[str] = None
    volume: float = Field(default=1.0, ge=0.0, le=1.0)


class SessionUpdateRequest(BaseModel):
    """Request to update a session."""
    volume: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    muted: Optional[bool] = None
    add_speakers: Optional[list[str]] = None
    remove_speakers: Optional[list[str]] = None


class SessionResponse(BaseModel):
    """Session data in API response."""
    id: str
    theme_id: str
    channel_id: Optional[str]
    speaker_ids: list[str]
    state: str
    volume: float
    muted: bool
    duration: Optional[float]

    @classmethod
    def from_session(cls, session: Session) -> "SessionResponse":
        return cls(
            id=session.id,
            theme_id=session.theme_id,
            channel_id=session.channel_id,
            speaker_ids=session.get_speaker_ids(),
            state=session.state.value,
            volume=session.volume,
            muted=session.muted,
            duration=session.duration,
        )


class ThemeResponse(BaseModel):
    """Theme data in API response."""
    id: str
    name: str
    description: str
    author: str
    track_count: int
    tags: list[str]

    @classmethod
    def from_theme(cls, theme: Theme) -> "ThemeResponse":
        return cls(
            id=theme.id,
            name=theme.name,
            description=theme.description,
            author=theme.author,
            track_count=len(theme.tracks),
            tags=theme.tags,
        )


class ChannelCreateRequest(BaseModel):
    """Request to create a channel."""
    name: str
    speaker_ids: list[str] = []


class ChannelUpdateRequest(BaseModel):
    """Request to update a channel."""
    name: Optional[str] = None
    theme_id: Optional[str] = None
    volume: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    muted: Optional[bool] = None
    add_speakers: Optional[list[str]] = None
    remove_speakers: Optional[list[str]] = None


class ChannelResponse(BaseModel):
    """Channel data in API response."""
    id: str
    name: str
    speaker_ids: list[str]
    theme_id: Optional[str]
    session_id: Optional[str]
    volume: float
    muted: bool
    is_playing: bool

    @classmethod
    def from_channel(cls, channel: Channel) -> "ChannelResponse":
        return cls(
            id=channel.id,
            name=channel.name,
            speaker_ids=channel.speakers,
            theme_id=channel.theme_id,
            session_id=channel.session_id,
            volume=channel.volume,
            muted=channel.muted,
            is_playing=channel.is_playing,
        )


class StatusResponse(BaseModel):
    """System status response."""
    version: str
    state: str
    speaker_count: int
    enabled_speaker_count: int
    theme_count: int
    active_session_count: int


class SettingsUpdateRequest(BaseModel):
    """Request to update settings."""
    master_volume: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    log_level: Optional[str] = None


class CommandRequest(BaseModel):
    """Generic command request."""
    action: str
    params: dict = {}


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    success: bool = True


# ─────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────

def get_manager() -> StateManager:
    """Dependency to get state manager."""
    return get_state_manager()


# ─────────────────────────────────────────────────────────────────────
# Speaker Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/speakers", response_model=list[SpeakerResponse])
async def list_speakers(
    enabled_only: bool = Query(False, description="Return only enabled speakers"),
    manager: StateManager = Depends(get_manager)
):
    """List all discovered speakers."""
    if enabled_only:
        speakers = manager.get_enabled_speakers()
    else:
        speakers = list(manager.state.speakers.values())

    return [SpeakerResponse.from_speaker(s) for s in speakers]


@router.get("/speakers/enabled", response_model=list[SpeakerResponse])
async def list_enabled_speakers(manager: StateManager = Depends(get_manager)):
    """List enabled speakers only."""
    return [SpeakerResponse.from_speaker(s) for s in manager.get_enabled_speakers()]


@router.get("/speakers/{speaker_id}", response_model=SpeakerResponse)
async def get_speaker(speaker_id: str, manager: StateManager = Depends(get_manager)):
    """Get a specific speaker."""
    speaker = manager.state.speakers.get(speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found")
    return SpeakerResponse.from_speaker(speaker)


@router.post("/speakers/{speaker_id}/enable", response_model=MessageResponse)
async def enable_speaker(speaker_id: str, manager: StateManager = Depends(get_manager)):
    """Enable a speaker."""
    if speaker_id not in manager.state.speakers:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found")

    changed = manager.enable_speaker(speaker_id)
    return MessageResponse(
        message=f"Speaker {speaker_id} enabled" if changed else f"Speaker {speaker_id} already enabled",
        success=True
    )


@router.post("/speakers/{speaker_id}/disable", response_model=MessageResponse)
async def disable_speaker(speaker_id: str, manager: StateManager = Depends(get_manager)):
    """
    Disable a speaker.

    This also stops any active streams to this speaker and removes it
    from any active sessions.
    """
    if speaker_id not in manager.state.speakers:
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found")

    # Stop any active sessions for this speaker
    for session in manager.get_sessions_for_speaker(speaker_id):
        session.remove_speaker(speaker_id)
        if not session.speakers:
            # No speakers left, stop session
            session.mark_stopped()

    changed = manager.disable_speaker(speaker_id)
    return MessageResponse(
        message=f"Speaker {speaker_id} disabled" if changed else f"Speaker {speaker_id} already disabled",
        success=True
    )


@router.post("/speakers/enable-all", response_model=MessageResponse)
async def enable_all_speakers(manager: StateManager = Depends(get_manager)):
    """Enable all speakers."""
    count = manager.enable_all_speakers()
    return MessageResponse(message=f"Enabled {count} speakers")


@router.post("/speakers/disable-all", response_model=MessageResponse)
async def disable_all_speakers(manager: StateManager = Depends(get_manager)):
    """
    Disable all speakers.

    This stops all active sessions and streams.
    """
    # Stop all active sessions
    for session in manager.get_active_sessions():
        session.mark_stopped()

    count = manager.disable_all_speakers()
    return MessageResponse(message=f"Disabled {count} speakers")


@router.post("/speakers/{speaker_id}/volume", response_model=MessageResponse)
async def set_speaker_volume(
    speaker_id: str,
    request: SpeakerVolumeRequest,
    manager: StateManager = Depends(get_manager)
):
    """Set speaker volume."""
    if not manager.set_speaker_volume(speaker_id, request.volume):
        raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found")
    return MessageResponse(message=f"Set volume to {request.volume}")


@router.post("/speakers/discover", response_model=MessageResponse)
async def discover_speakers(manager: StateManager = Depends(get_manager)):
    """Trigger speaker discovery."""
    # TODO: Trigger actual discovery via plugin system
    return MessageResponse(message="Speaker discovery triggered")


# ─────────────────────────────────────────────────────────────────────
# Session Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    active_only: bool = Query(True, description="Return only active sessions"),
    manager: StateManager = Depends(get_manager)
):
    """List sessions."""
    if active_only:
        sessions = manager.get_active_sessions()
    else:
        sessions = list(manager.state.sessions.values())
    return [SessionResponse.from_session(s) for s in sessions]


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    manager: StateManager = Depends(get_manager)
):
    """Create a new session (start playing theme to speakers)."""
    # Validate theme exists
    theme = manager.get_theme(request.theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail=f"Theme {request.theme_id} not found")

    # Validate speakers exist and are enabled
    for speaker_id in request.speaker_ids:
        if speaker_id not in manager.state.speakers:
            raise HTTPException(status_code=404, detail=f"Speaker {speaker_id} not found")
        if not manager.is_speaker_enabled(speaker_id):
            raise HTTPException(status_code=400, detail=f"Speaker {speaker_id} is not enabled")

    # Create session
    session = Session.create(
        theme_id=request.theme_id,
        speaker_ids=request.speaker_ids,
        channel_id=request.channel_id,
    )
    session.volume = request.volume

    manager.add_session(session)

    # TODO: Actually start streaming via streaming engine

    session.mark_started()
    logger.info(f"Created session {session.id} for theme {request.theme_id}")

    return SessionResponse.from_session(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, manager: StateManager = Depends(get_manager)):
    """Get a specific session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionResponse.from_session(session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    manager: StateManager = Depends(get_manager)
):
    """Update a session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if request.volume is not None:
        session.volume = request.volume

    if request.muted is not None:
        session.muted = request.muted

    if request.add_speakers:
        for speaker_id in request.add_speakers:
            if not manager.is_speaker_enabled(speaker_id):
                raise HTTPException(status_code=400, detail=f"Speaker {speaker_id} is not enabled")
            session.add_speaker(speaker_id)

    if request.remove_speakers:
        for speaker_id in request.remove_speakers:
            session.remove_speaker(speaker_id)

    return SessionResponse.from_session(session)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def stop_session(session_id: str, manager: StateManager = Depends(get_manager)):
    """Stop a session."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # TODO: Actually stop streaming via streaming engine

    session.mark_stopped()
    logger.info(f"Stopped session {session_id}")

    return MessageResponse(message=f"Session {session_id} stopped")


# ─────────────────────────────────────────────────────────────────────
# Theme Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/themes", response_model=list[ThemeResponse])
async def list_themes(manager: StateManager = Depends(get_manager)):
    """List available themes."""
    return [ThemeResponse.from_theme(t) for t in manager.state.themes.values()]


@router.get("/themes/{theme_id}", response_model=ThemeResponse)
async def get_theme(theme_id: str, manager: StateManager = Depends(get_manager)):
    """Get a specific theme."""
    theme = manager.get_theme(theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")
    return ThemeResponse.from_theme(theme)


@router.post("/themes/{theme_id}/play", response_model=SessionResponse)
async def play_theme(
    theme_id: str,
    speaker_ids: list[str] = Query(..., description="Speakers to play to"),
    manager: StateManager = Depends(get_manager)
):
    """Play a theme to specified speakers (creates a session)."""
    request = SessionCreateRequest(theme_id=theme_id, speaker_ids=speaker_ids)
    return await create_session(request, manager)


@router.post("/themes/scan", response_model=MessageResponse)
async def scan_themes(manager: StateManager = Depends(get_manager)):
    """Rescan theme directories."""
    # TODO: Implement theme scanning
    return MessageResponse(message="Theme scan triggered")


# ─────────────────────────────────────────────────────────────────────
# Channel Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/channels", response_model=list[ChannelResponse])
async def list_channels(manager: StateManager = Depends(get_manager)):
    """List all channels."""
    return [ChannelResponse.from_channel(c) for c in manager.state.channels.values()]


@router.post("/channels", response_model=ChannelResponse)
async def create_channel(
    request: ChannelCreateRequest,
    manager: StateManager = Depends(get_manager)
):
    """Create a new channel."""
    channel = Channel.create(name=request.name, speaker_ids=request.speaker_ids)
    manager.add_channel(channel)
    return ChannelResponse.from_channel(channel)


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: str, manager: StateManager = Depends(get_manager)):
    """Get a specific channel."""
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return ChannelResponse.from_channel(channel)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: str,
    request: ChannelUpdateRequest,
    manager: StateManager = Depends(get_manager)
):
    """Update a channel."""
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if request.name is not None:
        channel.name = request.name

    if request.theme_id is not None:
        channel.theme_id = request.theme_id

    if request.volume is not None:
        channel.volume = request.volume

    if request.muted is not None:
        channel.muted = request.muted

    if request.add_speakers:
        for speaker_id in request.add_speakers:
            channel.add_speaker(speaker_id)

    if request.remove_speakers:
        for speaker_id in request.remove_speakers:
            channel.remove_speaker(speaker_id)

    manager.add_channel(channel)  # Triggers save and notify
    return ChannelResponse.from_channel(channel)


@router.delete("/channels/{channel_id}", response_model=MessageResponse)
async def delete_channel(channel_id: str, manager: StateManager = Depends(get_manager)):
    """Delete a channel."""
    if not manager.remove_channel(channel_id):
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    return MessageResponse(message=f"Channel {channel_id} deleted")


@router.post("/channels/{channel_id}/play", response_model=SessionResponse)
async def play_channel(
    channel_id: str,
    theme_id: str = Query(..., description="Theme to play"),
    manager: StateManager = Depends(get_manager)
):
    """Play a theme on a channel."""
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if not channel.speakers:
        raise HTTPException(status_code=400, detail="Channel has no speakers assigned")

    # Filter to enabled speakers only
    enabled_speakers = [s for s in channel.speakers if manager.is_speaker_enabled(s)]
    if not enabled_speakers:
        raise HTTPException(status_code=400, detail="No enabled speakers in channel")

    request = SessionCreateRequest(
        theme_id=theme_id,
        speaker_ids=enabled_speakers,
        channel_id=channel_id
    )
    session = await create_session(request, manager)

    # Update channel state
    channel.theme_id = theme_id
    channel.session_id = session.id
    manager.add_channel(channel)

    return session


@router.post("/channels/{channel_id}/stop", response_model=MessageResponse)
async def stop_channel(channel_id: str, manager: StateManager = Depends(get_manager)):
    """Stop playback on a channel."""
    channel = manager.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")

    if channel.session_id:
        await stop_session(channel.session_id, manager)
        channel.session_id = None
        # Keep theme_id so user's selection persists after stopping
        manager.add_channel(channel)

    return MessageResponse(message=f"Channel {channel_id} stopped")


# ─────────────────────────────────────────────────────────────────────
# System Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status(manager: StateManager = Depends(get_manager)):
    """Get system status."""
    active_sessions = manager.get_active_sessions()

    return StatusResponse(
        version=get_version(),
        state="playing" if active_sessions else "idle",
        speaker_count=len(manager.state.speakers),
        enabled_speaker_count=len(manager.get_enabled_speakers()),
        theme_count=len(manager.state.themes),
        active_session_count=len(active_sessions),
    )


@router.get("/settings")
async def get_settings(manager: StateManager = Depends(get_manager)):
    """Get current settings."""
    return manager.get_settings().to_dict()


@router.patch("/settings", response_model=MessageResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    manager: StateManager = Depends(get_manager)
):
    """Update settings."""
    updates = {}
    if request.master_volume is not None:
        updates["master_volume"] = request.master_volume
    if request.log_level is not None:
        from ..models import LogLevel
        try:
            updates["log_level"] = LogLevel(request.log_level)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid log level: {request.log_level}")

    if updates:
        manager.update_settings(**updates)

    return MessageResponse(message="Settings updated")


@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: str = Query("info", description="Minimum log level")
):
    """Get recent logs."""
    # TODO: Implement log collection
    return {"logs": [], "message": "Log collection not yet implemented"}


@router.post("/command", response_model=MessageResponse)
async def execute_command(
    request: CommandRequest,
    manager: StateManager = Depends(get_manager)
):
    """Execute a generic command."""
    action = request.action.lower()

    if action == "discover_speakers":
        return await discover_speakers(manager)
    elif action == "scan_themes":
        return await scan_themes(manager)
    elif action == "stop_all":
        for session in manager.get_active_sessions():
            session.mark_stopped()
        return MessageResponse(message="All sessions stopped")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
