"""
Sonorium Core Module

Platform-agnostic core functionality shared between all deployment targets.
Contains channel system, state management, and core managers.
"""

# Core - Channel system
from sonorium.core.channel import (
    Channel,
    ChannelState,
    ChannelStream,
    ChannelManager,
    DEFAULT_OUTPUT_GAIN,
)

# Core - State management
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

# Core - Speaker management
from sonorium.core.speaker_manager import SpeakerManager

# Core - Theme cycling
from sonorium.core.cycle_manager import CycleManager

# Core - Theme metadata
from sonorium.core.theme_metadata import ThemeMetadataManager

# Core - Logging
from sonorium.core.log_collector import LogCollector, LogCategory, LogLevel

__all__ = [
    # Channel system
    "Channel",
    "ChannelState",
    "ChannelStream",
    "ChannelManager",
    "DEFAULT_OUTPUT_GAIN",
    # State management
    "NameSource",
    "CycleConfig",
    "SonoriumSettings",
    "SpeakerSelection",
    "SpeakerGroup",
    "Session",
    "SonoriumState",
    "StateStore",
    # Speaker management
    "SpeakerManager",
    # Theme cycling
    "CycleManager",
    # Theme metadata
    "ThemeMetadataManager",
    # Logging
    "LogCollector",
    "LogCategory",
    "LogLevel",
]
