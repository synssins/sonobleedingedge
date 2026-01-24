"""
Theme data models.

Defines Theme, Track, and related types for ambient soundscape management.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from pathlib import Path


class PlaybackMode(str, Enum):
    """How tracks are played."""
    LOOP = "loop"               # Continuous loop
    PRESENCE = "presence"       # Plays based on presence probability
    RANDOM = "random"           # Random selection from pool
    SEQUENTIAL = "sequential"   # Play in order
    SPARSE = "sparse"           # Occasional playback with gaps
    AUTO = "auto"               # Automatically determined from file length


@dataclass
class ThemeAttribution:
    """Attribution and license information for a theme."""
    source: str                             # Source name (e.g., "Ambient-Mixer.com")
    source_url: Optional[str] = None        # URL to original source
    license: Optional[str] = None           # License name
    license_url: Optional[str] = None       # URL to license
    imported_date: Optional[str] = None     # ISO date when imported
    imported_by: Optional[str] = None       # Plugin/tool that imported it

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "license": self.license,
            "license_url": self.license_url,
            "imported_date": self.imported_date,
            "imported_by": self.imported_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThemeAttribution":
        return cls(
            source=data.get("source", ""),
            source_url=data.get("source_url"),
            license=data.get("license"),
            license_url=data.get("license_url"),
            imported_date=data.get("imported_date"),
            imported_by=data.get("imported_by"),
        )


@dataclass
class ThemePreset:
    """A saved configuration of track settings within a theme."""
    id: str                                 # Preset identifier (e.g., "mild_storm")
    name: str                               # Display name (e.g., "Mild Storm")
    is_default: bool = False                # Is this the default preset
    track_overrides: dict[str, dict] = field(default_factory=dict)  # track_id -> settings

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default,
            "tracks": self.track_overrides,
        }

    @classmethod
    def from_dict(cls, preset_id: str, data: dict) -> "ThemePreset":
        return cls(
            id=preset_id,
            name=data.get("name", preset_id),
            is_default=data.get("is_default", False),
            track_overrides=data.get("tracks", {}),
        )


@dataclass
class Track:
    """
    A single audio track within a theme.

    Tracks can be audio files or URLs to streaming sources.
    """

    id: str                             # Unique identifier within theme
    name: str                           # Display name
    source: str                         # File path or URL

    # Playback settings
    volume: float = 1.0                 # Track volume (0.0 - 1.0)
    presence: float = 1.0               # Probability of playing (0.0 - 1.0)
    playback_mode: PlaybackMode = PlaybackMode.LOOP
    seamless_loop: bool = False         # Enable gapless looping
    exclusive: bool = False             # Only one exclusive track plays at a time
    muted: bool = False                 # Whether track is muted

    # For SPARSE mode
    min_interval: float = 60.0          # Minimum seconds between plays
    max_interval: float = 300.0         # Maximum seconds between plays

    # Mixing
    fade_in: float = 2.0                # Fade in duration (seconds)
    fade_out: float = 2.0               # Fade out duration (seconds)
    pan: float = 0.0                    # Stereo pan (-1.0 left to 1.0 right)

    # Exclusion groups (only one track in group plays at a time)
    exclusion_group: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "volume": self.volume,
            "presence": self.presence,
            "playback_mode": self.playback_mode.value,
            "seamless_loop": self.seamless_loop,
            "exclusive": self.exclusive,
            "muted": self.muted,
            "min_interval": self.min_interval,
            "max_interval": self.max_interval,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "pan": self.pan,
            "exclusion_group": self.exclusion_group,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        """Create Track from dictionary."""
        mode_str = data.get("playback_mode", "loop")
        try:
            playback_mode = PlaybackMode(mode_str)
        except ValueError:
            playback_mode = PlaybackMode.LOOP

        return cls(
            id=data["id"],
            name=data["name"],
            source=data["source"],
            volume=data.get("volume", 1.0),
            presence=data.get("presence", 1.0),
            playback_mode=playback_mode,
            seamless_loop=data.get("seamless_loop", False),
            exclusive=data.get("exclusive", False),
            muted=data.get("muted", False),
            min_interval=data.get("min_interval", 60.0),
            max_interval=data.get("max_interval", 300.0),
            fade_in=data.get("fade_in", 2.0),
            fade_out=data.get("fade_out", 2.0),
            pan=data.get("pan", 0.0),
            exclusion_group=data.get("exclusion_group"),
        )


@dataclass
class Theme:
    """
    An ambient soundscape theme.

    A theme consists of multiple tracks that are mixed together
    to create an immersive audio environment.
    """

    id: str                             # Unique identifier
    name: str                           # Display name
    description: str = ""               # Theme description
    author: str = ""                    # Theme author
    version: str = "1.0"                # Theme version
    icon: str = ""                      # Emoji or icon path

    # Tracks
    tracks: list[Track] = field(default_factory=list)

    # Theme-level settings
    master_volume: float = 1.0          # Theme master volume
    crossfade_duration: float = 3.0     # Crossfade between themes

    # Organization
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_favorite: bool = False

    # Presets
    presets: list[ThemePreset] = field(default_factory=list)

    # Attribution
    attribution: Optional[ThemeAttribution] = None

    # Metadata
    path: Optional[str] = None          # Path to theme directory
    preview_url: Optional[str] = None   # Preview audio URL
    short_file_threshold: float = 15.0  # Files shorter than this are not looped

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Build tracks dict in metadata.json format
        tracks_dict = {}
        for track in self.tracks:
            tracks_dict[track.id] = {
                "presence": track.presence,
                "muted": track.muted,
                "volume": track.volume,
                "playback_mode": track.playback_mode.value,
                "seamless_loop": track.seamless_loop,
                "exclusive": track.exclusive,
            }

        # Build presets dict
        presets_dict = {}
        for preset in self.presets:
            presets_dict[preset.id] = {
                "name": preset.name,
                "is_default": preset.is_default,
                "tracks": preset.track_overrides,
            }

        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "is_favorite": self.is_favorite,
            "categories": self.categories,
            "short_file_threshold": self.short_file_threshold,
            "tracks": tracks_dict,
            "presets": presets_dict,
        }

        if self.attribution:
            result["attribution"] = self.attribution.to_dict()

        return result

    def to_api_dict(self) -> dict:
        """Convert to API response format (expanded tracks)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "icon": self.icon,
            "tracks": [t.to_dict() for t in self.tracks],
            "master_volume": self.master_volume,
            "categories": self.categories,
            "tags": self.tags,
            "is_favorite": self.is_favorite,
            "presets": [p.to_dict() for p in self.presets],
            "attribution": self.attribution.to_dict() if self.attribution else None,
            "path": self.path,
            "preview_url": self.preview_url,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        """Create Theme from dictionary (API format with track list)."""
        # Parse tracks
        tracks = []
        tracks_data = data.get("tracks", [])
        if isinstance(tracks_data, list):
            tracks = [Track.from_dict(t) for t in tracks_data]

        # Parse presets
        presets = []
        presets_data = data.get("presets", [])
        if isinstance(presets_data, list):
            for p in presets_data:
                presets.append(ThemePreset.from_dict(p.get("id", ""), p))
        elif isinstance(presets_data, dict):
            for preset_id, preset_info in presets_data.items():
                presets.append(ThemePreset.from_dict(preset_id, preset_info))

        # Parse attribution
        attribution = None
        if "attribution" in data and data["attribution"]:
            attribution = ThemeAttribution.from_dict(data["attribution"])

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0"),
            icon=data.get("icon", ""),
            tracks=tracks,
            master_volume=data.get("master_volume", 1.0),
            crossfade_duration=data.get("crossfade_duration", 3.0),
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            is_favorite=data.get("is_favorite", False),
            presets=presets,
            attribution=attribution,
            path=data.get("path"),
            preview_url=data.get("preview_url"),
            short_file_threshold=data.get("short_file_threshold", 15.0),
        )

    @classmethod
    def from_yaml_file(cls, path: Path) -> "Theme":
        """Load theme from YAML file."""
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        theme_dir = path.parent
        theme_id = theme_dir.name

        # Convert relative paths to absolute
        tracks = []
        for track_data in data.get("tracks", []):
            source = track_data.get("source", "")
            if not source.startswith(("http://", "https://")):
                # Relative path - resolve against theme directory
                track_data["source"] = str(theme_dir / source)
            tracks.append(Track.from_dict(track_data))

        return cls(
            id=theme_id,
            name=data.get("name", theme_id),
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0"),
            icon=data.get("icon", ""),
            tracks=tracks,
            master_volume=data.get("master_volume", 1.0),
            crossfade_duration=data.get("crossfade_duration", 3.0),
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            is_favorite=data.get("is_favorite", False),
            path=str(theme_dir),
            preview_url=data.get("preview_url"),
        )

    def get_default_preset(self) -> Optional[ThemePreset]:
        """Get the default preset if one exists."""
        for preset in self.presets:
            if preset.is_default:
                return preset
        return self.presets[0] if self.presets else None
