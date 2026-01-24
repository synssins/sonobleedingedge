"""
Theme Management.

Handles loading, importing, exporting, and managing soundscape themes.
"""

import asyncio
import json
import logging
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone

from ..models.theme import Theme, Track, PlaybackMode, ThemePreset, ThemeAttribution

logger = logging.getLogger(__name__)

# Supported audio formats
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}


class ThemeManager:
    """
    Manages soundscape themes.

    Responsibilities:
    - Scan and load themes from disk
    - Import themes from ZIP files
    - Export themes to ZIP files
    - Manage theme presets
    - Theme CRUD operations
    """

    def __init__(self, themes_dir: Optional[Path] = None):
        """
        Initialize the theme manager.

        Args:
            themes_dir: Directory containing theme folders
        """
        self.themes_dir = themes_dir
        self._themes: dict[str, Theme] = {}
        self._theme_paths: dict[str, Path] = {}  # theme_id -> folder path

    @property
    def themes_directory(self) -> Optional[Path]:
        """Get the themes directory."""
        return self.themes_dir

    def set_themes_directory(self, path: Path) -> None:
        """Set the themes directory."""
        self.themes_dir = Path(path)
        if not self.themes_dir.exists():
            self.themes_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────
    # Theme Loading
    # ─────────────────────────────────────────────────────────────────────

    async def scan_themes(self, path: Optional[Path] = None) -> list[Theme]:
        """
        Scan a directory for themes.

        Args:
            path: Directory to scan (uses themes_dir if not specified)

        Returns:
            List of discovered themes
        """
        scan_path = Path(path) if path else self.themes_dir
        if not scan_path or not scan_path.exists():
            logger.warning(f"Themes directory not found: {scan_path}")
            return []

        themes = []
        for folder in scan_path.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                theme = await self._load_theme_from_folder(folder)
                if theme:
                    themes.append(theme)
                    self._themes[theme.id] = theme
                    self._theme_paths[theme.id] = folder

        logger.info(f"Scanned {len(themes)} themes from {scan_path}")
        return themes

    async def _load_theme_from_folder(self, folder: Path) -> Optional[Theme]:
        """
        Load a theme from a folder.

        Args:
            folder: Theme folder path

        Returns:
            Loaded Theme or None if invalid
        """
        metadata_file = folder / "metadata.json"

        if metadata_file.exists():
            # Load from metadata
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return self._parse_theme_metadata(data, folder)
            except Exception as e:
                logger.error(f"Error loading theme metadata from {folder}: {e}")
                return None
        else:
            # Create theme from audio files
            return self._create_theme_from_files(folder)

    def _parse_theme_metadata(self, data: dict, folder: Path) -> Theme:
        """
        Parse theme from metadata.json.

        Args:
            data: Parsed JSON data
            folder: Theme folder path

        Returns:
            Parsed Theme object
        """
        theme_id = data.get("id", str(uuid4()))

        # Parse tracks
        tracks = []
        tracks_data = data.get("tracks", {})

        for track_name, settings in tracks_data.items():
            # Find audio file
            audio_file = self._find_audio_file(folder, track_name)
            if not audio_file:
                continue

            # Parse playback mode
            mode_str = settings.get("playback_mode", "loop")
            try:
                playback_mode = PlaybackMode(mode_str)
            except ValueError:
                playback_mode = PlaybackMode.LOOP if mode_str == "auto" else PlaybackMode.LOOP

            track = Track(
                id=track_name,
                name=settings.get("name", track_name),
                source=str(audio_file),
                volume=settings.get("volume", 1.0),
                presence=settings.get("presence", 1.0),
                playback_mode=playback_mode,
                seamless_loop=settings.get("seamless_loop", False),
                exclusive=settings.get("exclusive", False),
                muted=settings.get("muted", False),
            )
            tracks.append(track)

        # Parse presets
        presets = []
        presets_data = data.get("presets", {})

        for preset_id, preset_info in presets_data.items():
            preset_tracks = {}
            for track_name, track_settings in preset_info.get("tracks", {}).items():
                preset_tracks[track_name] = track_settings

            preset = ThemePreset(
                id=preset_id,
                name=preset_info.get("name", preset_id),
                is_default=preset_info.get("is_default", False),
                track_overrides=preset_tracks,
            )
            presets.append(preset)

        # Parse attribution
        attribution = None
        attr_data = data.get("attribution")
        if attr_data:
            attribution = ThemeAttribution(
                source=attr_data.get("source", ""),
                source_url=attr_data.get("source_url"),
                license=attr_data.get("license"),
                license_url=attr_data.get("license_url"),
                imported_date=attr_data.get("imported_date"),
                imported_by=attr_data.get("imported_by"),
            )

        return Theme(
            id=theme_id,
            name=data.get("name", folder.name),
            description=data.get("description", ""),
            icon=data.get("icon", ""),
            is_favorite=data.get("is_favorite", False),
            categories=data.get("categories", []),
            tracks=tracks,
            presets=presets,
            attribution=attribution,
        )

    def _find_audio_file(self, folder: Path, track_name: str) -> Optional[Path]:
        """Find audio file for a track name."""
        # Direct match
        audio_path = folder / track_name
        if audio_path.exists():
            return audio_path

        # Try with extensions
        for ext in AUDIO_EXTENSIONS:
            test_path = folder / f"{track_name}{ext}"
            if test_path.exists():
                return test_path

        # Try matching by stem
        stem = Path(track_name).stem
        for file in folder.iterdir():
            if file.suffix.lower() in AUDIO_EXTENSIONS and file.stem == stem:
                return file

        return None

    def _create_theme_from_files(self, folder: Path) -> Theme:
        """
        Create a basic theme from audio files in a folder.

        Args:
            folder: Folder containing audio files

        Returns:
            Created Theme
        """
        tracks = []

        for file in folder.iterdir():
            if file.suffix.lower() in AUDIO_EXTENSIONS:
                track = Track(
                    id=file.name,
                    name=file.stem.replace("_", " ").title(),
                    source=str(file),
                    volume=1.0,
                    playback_mode=PlaybackMode.LOOP,
                )
                tracks.append(track)

        return Theme(
            id=str(uuid4()),
            name=folder.name.replace("_", " ").title(),
            tracks=tracks,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Theme Operations
    # ─────────────────────────────────────────────────────────────────────

    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """Get a theme by ID."""
        return self._themes.get(theme_id)

    def get_themes(self) -> list[Theme]:
        """Get all loaded themes."""
        return list(self._themes.values())

    def get_themes_by_category(self, category: str) -> list[Theme]:
        """Get themes in a specific category."""
        return [t for t in self._themes.values() if category in t.categories]

    def get_favorite_themes(self) -> list[Theme]:
        """Get favorite themes."""
        return [t for t in self._themes.values() if t.is_favorite]

    def get_theme_path(self, theme_id: str) -> Optional[Path]:
        """Get the folder path for a theme."""
        return self._theme_paths.get(theme_id)

    def set_favorite(self, theme_id: str, is_favorite: bool) -> bool:
        """Set favorite status for a theme."""
        theme = self._themes.get(theme_id)
        if not theme:
            return False

        theme.is_favorite = is_favorite
        self._save_theme_metadata(theme_id)
        return True

    def _save_theme_metadata(self, theme_id: str) -> bool:
        """Save theme metadata to disk."""
        theme = self._themes.get(theme_id)
        folder = self._theme_paths.get(theme_id)

        if not theme or not folder:
            return False

        try:
            metadata_file = folder / "metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(theme.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving theme metadata: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    # Import/Export
    # ─────────────────────────────────────────────────────────────────────

    async def import_theme(self, zip_path: Path) -> Optional[Theme]:
        """
        Import a theme from a ZIP file.

        Args:
            zip_path: Path to ZIP file

        Returns:
            Imported Theme or None if failed
        """
        if not zip_path.exists():
            logger.error(f"ZIP file not found: {zip_path}")
            return None

        if not self.themes_dir:
            logger.error("Themes directory not set")
            return None

        try:
            # Generate folder name from ZIP
            folder_name = zip_path.stem
            target_folder = self.themes_dir / folder_name

            # Handle existing folder
            counter = 1
            while target_folder.exists():
                target_folder = self.themes_dir / f"{folder_name}_{counter}"
                counter += 1

            # Extract ZIP
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_folder)

            # Load the theme
            theme = await self._load_theme_from_folder(target_folder)
            if theme:
                self._themes[theme.id] = theme
                self._theme_paths[theme.id] = target_folder
                logger.info(f"Imported theme: {theme.name}")
                return theme

        except Exception as e:
            logger.error(f"Error importing theme from {zip_path}: {e}")

        return None

    async def export_theme(self, theme_id: str, output_path: Path) -> Optional[Path]:
        """
        Export a theme to a ZIP file.

        Args:
            theme_id: Theme to export
            output_path: Output ZIP file path

        Returns:
            Path to created ZIP file or None
        """
        theme = self._themes.get(theme_id)
        folder = self._theme_paths.get(theme_id)

        if not theme or not folder:
            logger.error(f"Theme not found: {theme_id}")
            return None

        try:
            # Ensure metadata is saved
            self._save_theme_metadata(theme_id)

            # Create ZIP
            output_path = Path(output_path)
            if not output_path.suffix:
                output_path = output_path.with_suffix(".zip")

            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in folder.rglob("*"):
                    if file.is_file():
                        arcname = file.relative_to(folder)
                        zf.write(file, arcname)

            logger.info(f"Exported theme {theme_id} to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error exporting theme: {e}")
            return None

    async def delete_theme(self, theme_id: str, delete_files: bool = False) -> bool:
        """
        Delete a theme.

        Args:
            theme_id: Theme to delete
            delete_files: Also delete files from disk

        Returns:
            True if deleted
        """
        theme = self._themes.get(theme_id)
        folder = self._theme_paths.get(theme_id)

        if not theme:
            return False

        # Remove from memory
        del self._themes[theme_id]
        if theme_id in self._theme_paths:
            del self._theme_paths[theme_id]

        # Delete files if requested
        if delete_files and folder and folder.exists():
            try:
                shutil.rmtree(folder)
                logger.info(f"Deleted theme folder: {folder}")
            except Exception as e:
                logger.error(f"Error deleting theme folder: {e}")
                return False

        logger.info(f"Deleted theme: {theme_id}")
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Preset Management
    # ─────────────────────────────────────────────────────────────────────

    def apply_preset(self, theme_id: str, preset_id: str) -> bool:
        """
        Apply a preset to a theme.

        This modifies the track settings according to the preset.

        Args:
            theme_id: Theme ID
            preset_id: Preset ID to apply

        Returns:
            True if preset applied
        """
        theme = self._themes.get(theme_id)
        if not theme:
            return False

        # Find preset
        preset = None
        for p in theme.presets:
            if p.id == preset_id:
                preset = p
                break

        if not preset:
            logger.warning(f"Preset not found: {preset_id}")
            return False

        # Apply overrides to tracks
        for track in theme.tracks:
            if track.id in preset.track_overrides:
                overrides = preset.track_overrides[track.id]

                if "volume" in overrides:
                    track.volume = overrides["volume"]
                if "presence" in overrides:
                    track.presence = overrides["presence"]
                if "muted" in overrides:
                    track.muted = overrides["muted"]
                if "playback_mode" in overrides:
                    try:
                        track.playback_mode = PlaybackMode(overrides["playback_mode"])
                    except ValueError:
                        pass
                if "seamless_loop" in overrides:
                    track.seamless_loop = overrides["seamless_loop"]
                if "exclusive" in overrides:
                    track.exclusive = overrides["exclusive"]

        logger.info(f"Applied preset {preset_id} to theme {theme_id}")
        return True

    def save_preset(
        self,
        theme_id: str,
        preset_name: str,
        preset_id: Optional[str] = None,
        is_default: bool = False
    ) -> Optional[ThemePreset]:
        """
        Save current track settings as a preset.

        Args:
            theme_id: Theme ID
            preset_name: Name for the preset
            preset_id: ID for preset (generated if None)
            is_default: Make this the default preset

        Returns:
            Created ThemePreset or None
        """
        theme = self._themes.get(theme_id)
        if not theme:
            return None

        preset_id = preset_id or preset_name.lower().replace(" ", "_")

        # Capture current track settings
        track_overrides = {}
        for track in theme.tracks:
            track_overrides[track.id] = {
                "volume": track.volume,
                "presence": track.presence,
                "muted": track.muted,
                "playback_mode": track.playback_mode.value,
                "seamless_loop": track.seamless_loop,
                "exclusive": track.exclusive,
            }

        # Update existing or create new
        existing = None
        for i, p in enumerate(theme.presets):
            if p.id == preset_id:
                existing = i
                break

        preset = ThemePreset(
            id=preset_id,
            name=preset_name,
            is_default=is_default,
            track_overrides=track_overrides,
        )

        if existing is not None:
            theme.presets[existing] = preset
        else:
            theme.presets.append(preset)

        # Clear other defaults if this is default
        if is_default:
            for p in theme.presets:
                if p.id != preset_id:
                    p.is_default = False

        # Save metadata
        self._save_theme_metadata(theme_id)

        logger.info(f"Saved preset {preset_name} for theme {theme_id}")
        return preset

    def delete_preset(self, theme_id: str, preset_id: str) -> bool:
        """Delete a preset from a theme."""
        theme = self._themes.get(theme_id)
        if not theme:
            return False

        for i, p in enumerate(theme.presets):
            if p.id == preset_id:
                theme.presets.pop(i)
                self._save_theme_metadata(theme_id)
                return True

        return False


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def init_theme_manager(themes_dir: Optional[Path] = None) -> ThemeManager:
    """
    Initialize the global theme manager.

    Args:
        themes_dir: Directory containing themes

    Returns:
        Initialized ThemeManager
    """
    global _theme_manager
    _theme_manager = ThemeManager(themes_dir)
    return _theme_manager
