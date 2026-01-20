"""
Sonorium Core Module

Contains channel system and core data models.
"""

# Core - Channel system (shared across all platforms)
from sonorium.core.channel import (
    Channel,
    ChannelState,
    ChannelStream,
    ChannelManager,
    DEFAULT_OUTPUT_GAIN,
)

# Core - Speaker management (shared across all platforms)
from sonorium.core.speaker_manager import SpeakerManager

# HA Addon - State management and managers
from sonorium.core.state import (
    NameSource,
    SonoriumSettings,
    SpeakerSelection,
    SpeakerGroup,
    Session,
    SonoriumState,
    StateStore,
)

from sonorium.core.session_manager import SessionManager
from sonorium.core.group_manager import GroupManager

__all__ = [
    # Channel system
    "Channel",
    "ChannelState",
    "ChannelStream",
    "ChannelManager",
    "DEFAULT_OUTPUT_GAIN",
    # Speaker management
    "SpeakerManager",
    # Data models
    "NameSource",
    "SonoriumSettings",
    "SpeakerSelection",
    "SpeakerGroup",
    "Session",
    "SonoriumState",
    "StateStore",
    # Managers
    "SessionManager",
    "GroupManager",
]
