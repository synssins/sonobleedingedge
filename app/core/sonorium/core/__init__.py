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

__all__ = [
    # Channel system
    "Channel",
    "ChannelState",
    "ChannelStream",
    "ChannelManager",
    "DEFAULT_OUTPUT_GAIN",
    # Speaker management
    "SpeakerManager",
]
