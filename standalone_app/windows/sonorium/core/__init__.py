"""
Sonorium core modules.

State management, streaming, MQTT bridge, and core functionality.

CORE CODE: This module is shared across all platforms.
"""

# State management - StateStore is the primary class
from .state import (
    StateStore,
    SonoriumState,
    SonoriumSettings,
    Session,
    SpeakerGroup,
    SpeakerSelection,
    CycleConfig,
    NameSource,
)

# MQTT bridge
from .mqtt import (
    MQTTBridge,
    init_mqtt_bridge,
    stop_mqtt_bridge,
    get_mqtt_bridge,
)

# Streaming engine
from .streaming import (
    StreamState,
    StreamSession,
    StreamingEngine,
    get_streaming_engine,
    init_streaming_engine,
)

# Audio mixer
from .mixer import (
    TrackState,
    ActiveTrack,
    MixerSession,
    AudioMixer,
    get_audio_mixer,
    init_audio_mixer,
)

# Theme management
from .themes import (
    ThemeManager,
    get_theme_manager,
    init_theme_manager,
)

# Session and Group managers
from .session_manager import SessionManager
from .group_manager import GroupManager

# Cycle manager
from .cycle_manager import CycleManager

# Theme metadata
from .theme_metadata import (
    ThemeMetadata,
    ThemeMetadataManager,
    TrackSettings,
)

# Log collector
from .log_collector import (
    LogCollector,
    LogEntry,
    LogLevel as LogCollectorLevel,
    LogCategory,
    get_log_collector,
    log,
    log_info,
    log_error,
    log_warning,
    log_debug,
)

# Utilities
from .utils import (
    IndexList,
    sanitize,
    safe_filename,
    get_local_ip,
    get_host_network_ip,
    get_target_subnet,
    is_docker_network,
)

# Track/Recording engine (audio streaming)
from .track import (
    ExclusionGroupCoordinator,
    PlaybackMode,
    TrackMetadata,
    TrackInstance,
    TrackStream,
    CrossfadeTrackStream,
    SparsePlaybackStream,
    PresenceMixingStream,
    SAMPLE_RATE,
    CROSSFADE_SAMPLES,
    TRACK_FADE_SAMPLES,
)

# Theme streaming
from .theme_stream import (
    ThemeDefinition,
    ThemeStream,
)

# Backward compatibility
from .recording import (
    RecordingMetadata,
    RecordingThemeInstance,
    RecordingThemeStream,
    CrossfadeRecordingStream,
)

# Speaker coordination
from .speaker_coordinator import (
    SpeakerCoordinator,
    get_speaker_coordinator,
    init_speaker_coordinator,
)

__all__ = [
    # State
    "StateStore",
    "SonoriumState",
    "SonoriumSettings",
    "Session",
    "SpeakerGroup",
    "SpeakerSelection",
    "CycleConfig",
    "NameSource",
    # MQTT
    "MQTTBridge",
    "init_mqtt_bridge",
    "stop_mqtt_bridge",
    "get_mqtt_bridge",
    # Streaming
    "StreamState",
    "StreamSession",
    "StreamingEngine",
    "get_streaming_engine",
    "init_streaming_engine",
    # Mixer
    "TrackState",
    "ActiveTrack",
    "MixerSession",
    "AudioMixer",
    "get_audio_mixer",
    "init_audio_mixer",
    # Themes
    "ThemeManager",
    "get_theme_manager",
    "init_theme_manager",
    # Session/Group managers
    "SessionManager",
    "GroupManager",
    # Cycle manager
    "CycleManager",
    # Theme metadata
    "ThemeMetadata",
    "ThemeMetadataManager",
    "TrackSettings",
    # Log collector
    "LogCollector",
    "LogEntry",
    "LogCollectorLevel",
    "LogCategory",
    "get_log_collector",
    "log",
    "log_info",
    "log_error",
    "log_warning",
    "log_debug",
    # Utilities
    "IndexList",
    "sanitize",
    "safe_filename",
    "get_local_ip",
    "get_host_network_ip",
    "get_target_subnet",
    "is_docker_network",
    # Track/Recording engine
    "ExclusionGroupCoordinator",
    "PlaybackMode",
    "TrackMetadata",
    "TrackInstance",
    "TrackStream",
    "CrossfadeTrackStream",
    "SparsePlaybackStream",
    "PresenceMixingStream",
    "SAMPLE_RATE",
    "CROSSFADE_SAMPLES",
    "TRACK_FADE_SAMPLES",
    # Theme streaming
    "ThemeDefinition",
    "ThemeStream",
    # Backward compatibility
    "RecordingMetadata",
    "RecordingThemeInstance",
    "RecordingThemeStream",
    "CrossfadeRecordingStream",
    # Speaker coordination
    "SpeakerCoordinator",
    "get_speaker_coordinator",
    "init_speaker_coordinator",
]
