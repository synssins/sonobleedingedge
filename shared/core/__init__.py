"""
Sonorium core modules.

State management, streaming, MQTT bridge, and core functionality.
"""

from .state import (
    SonoriumState,
    StateManager,
    get_state_manager,
    init_state_manager,
)

from .mqtt import (
    MQTTBridge,
    init_mqtt_bridge,
    stop_mqtt_bridge,
    get_mqtt_bridge,
)

from .streaming import (
    StreamState,
    StreamSession,
    StreamingEngine,
    get_streaming_engine,
    init_streaming_engine,
)

from .mixer import (
    TrackState,
    ActiveTrack,
    MixerSession,
    AudioMixer,
    get_audio_mixer,
    init_audio_mixer,
)

from .themes import (
    ThemeManager,
    get_theme_manager,
    init_theme_manager,
)

__all__ = [
    # State
    "SonoriumState",
    "StateManager",
    "get_state_manager",
    "init_state_manager",
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
