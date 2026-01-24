"""
Sonorium core modules.

State management, streaming, MQTT bridge, and core functionality.
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
]
