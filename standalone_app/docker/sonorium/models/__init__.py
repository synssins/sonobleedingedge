"""
Sonorium data models.

This module contains all data models used throughout the application.
"""

from .speaker import (
    Speaker,
    SpeakerProtocol,
    SpeakerState,
    DiscoverySource,
    generate_speaker_id,
)

from .theme import (
    Theme,
    Track,
    PlaybackMode,
    ThemeAttribution,
    ThemePreset,
)

from .session import (
    Session,
    SessionState,
    SessionSpeaker,
)

from .settings import (
    Settings,
    MQTTSettings,
    DiscoverySettings,
    AudioSettings,
    WebSettings,
    LogLevel,
)

from .channel import (
    Channel,
)

# Unified speaker model (for deduplication across multiple sources)
from .speaker_model import (
    UnifiedSpeaker,
    DiscoverySource as UnifiedDiscoverySource,
    ControlMethod,
)

from .speaker_dedup import (
    SpeakerDeduplicator,
)

__all__ = [
    # Speaker (simple model)
    "Speaker",
    "SpeakerProtocol",
    "SpeakerState",
    "DiscoverySource",
    "generate_speaker_id",
    # Unified Speaker (deduplication model)
    "UnifiedSpeaker",
    "UnifiedDiscoverySource",
    "ControlMethod",
    "SpeakerDeduplicator",
    # Theme
    "Theme",
    "Track",
    "PlaybackMode",
    "ThemeAttribution",
    "ThemePreset",
    # Session
    "Session",
    "SessionState",
    "SessionSpeaker",
    # Settings
    "Settings",
    "MQTTSettings",
    "DiscoverySettings",
    "AudioSettings",
    "WebSettings",
    "LogLevel",
    # Channel
    "Channel",
]
