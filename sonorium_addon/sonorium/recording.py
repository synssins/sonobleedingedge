"""
Backward compatibility module - re-exports from track.py.

DEPRECATED: Import from sonorium.track instead.

This module maintains backward compatibility during the transition from
'recording' terminology to 'track' terminology. All classes and constants
are re-exported from track.py with both old and new names.
"""

# Re-export everything from track.py
from sonorium.track import (
    # Constants
    LOG_THRESHOLD,
    SHORT_FILE_THRESHOLD_SECONDS,
    SPARSE_MIN_INTERVAL,
    SPARSE_MAX_INTERVAL,
    SPARSE_INTERVAL_VARIANCE,
    LOOP_CROSSFADE_DURATION,
    TRACK_FADE_DURATION,
    SAMPLE_RATE,
    CROSSFADE_SAMPLES,
    TRACK_FADE_SAMPLES,
    # Classes
    ExclusionGroupCoordinator,
    PlaybackMode,
    # New names
    TrackMetadata,
    TrackInstance,
    TrackStream,
    CrossfadeTrackStream,
    SparsePlaybackStream,
    PresenceMixingStream,
)

# Backward compatibility aliases (deprecated)
RecordingMetadata = TrackMetadata
RecordingThemeInstance = TrackInstance
RecordingThemeStream = TrackStream
CrossfadeRecordingStream = CrossfadeTrackStream

__all__ = [
    # Constants
    'LOG_THRESHOLD',
    'SHORT_FILE_THRESHOLD_SECONDS',
    'SPARSE_MIN_INTERVAL',
    'SPARSE_MAX_INTERVAL',
    'SPARSE_INTERVAL_VARIANCE',
    'LOOP_CROSSFADE_DURATION',
    'TRACK_FADE_DURATION',
    'SAMPLE_RATE',
    'CROSSFADE_SAMPLES',
    'TRACK_FADE_SAMPLES',
    # Classes
    'ExclusionGroupCoordinator',
    'PlaybackMode',
    # New names (preferred)
    'TrackMetadata',
    'TrackInstance',
    'TrackStream',
    'CrossfadeTrackStream',
    'SparsePlaybackStream',
    'PresenceMixingStream',
    # Deprecated aliases
    'RecordingMetadata',
    'RecordingThemeInstance',
    'RecordingThemeStream',
    'CrossfadeRecordingStream',
]
