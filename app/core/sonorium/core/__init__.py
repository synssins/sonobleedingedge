"""
Sonorium Shared Core Module

Platform-agnostic core functionality shared between all deployment targets.
"""

from sonorium.core.speaker_model import (
    DiscoverySource,
    ControlMethod,
    UnifiedSpeaker,
)
from sonorium.core.speaker_dedup import SpeakerDeduplicator

__all__ = [
    "DiscoverySource",
    "ControlMethod",
    "UnifiedSpeaker",
    "SpeakerDeduplicator",
]
