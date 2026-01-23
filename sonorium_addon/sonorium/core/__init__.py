"""
Sonorium Core Module (HA Addon)

Contains channel system, core data models, and HA-specific managers.
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

# Core - State management (shared across all platforms)
from sonorium.core.state import (
    NameSource,
    CycleConfig,
    SonoriumSettings,
    SpeakerSelection,
    SpeakerGroup,
    Session,
    SonoriumState,
    StateStore,
)

# Core - Theme cycling (shared across all platforms)
from sonorium.core.cycle_manager import CycleManager

# Core - Theme metadata (shared across all platforms)
from sonorium.core.theme_metadata import ThemeMetadataManager

# Core - Logging (shared across all platforms)
from sonorium.core.log_collector import LogCollector, LogCategory, LogLevel

# HA Addon - Specific managers (not shared)
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
    # State management
    "NameSource",
    "CycleConfig",
    "SonoriumSettings",
    "SpeakerSelection",
    "SpeakerGroup",
    "Session",
    "SonoriumState",
    "StateStore",
    # Theme cycling
    "CycleManager",
    # Theme metadata
    "ThemeMetadataManager",
    # Logging
    "LogCollector",
    "LogCategory",
    "LogLevel",
    # HA-specific managers
    "SessionManager",
    "GroupManager",
]
