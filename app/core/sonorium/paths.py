"""
Sonorium Paths - Platform-aware path management.

Provides consistent path resolution across all deployment targets:
- Standalone (Windows/Mac/Linux)
- Docker container
- Home Assistant addon
"""

from __future__ import annotations

import os
import sys
from functools import cached_property
from pathlib import Path


def _detect_platform() -> str:
    """Detect the current deployment platform."""
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "ha_addon"
    if os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
        return "docker"
    return "standalone"


class PackagePaths:
    """
    Manages paths for the Sonorium package.

    Provides platform-aware path resolution for:
    - Package directory (where code lives)
    - Data directory (configuration, state)
    - Audio directory (themes)
    - Plugins directory (user plugins)
    - Logs directory
    """

    def __init__(self, name: str = "sonorium"):
        self._name = name
        self._platform = _detect_platform()

    @cached_property
    def name_ns(self) -> str:
        """Package namespace name."""
        return self._name

    @cached_property
    def platform(self) -> str:
        """Current deployment platform."""
        return self._platform

    @cached_property
    def package(self) -> Path:
        """Path to the package directory (where this file lives)."""
        return Path(__file__).parent

    @cached_property
    def data(self) -> Path:
        """
        Path to the data directory.

        Platform-specific:
        - HA addon: /config/sonorium
        - Docker: /data or SONORIUM_DATA_DIR
        - Standalone Windows: %APPDATA%/Sonorium
        - Standalone Mac: ~/Library/Application Support/Sonorium
        - Standalone Linux: ~/.sonorium
        """
        if self._platform == "ha_addon":
            data_path = Path("/config/sonorium")
            data_path.mkdir(parents=True, exist_ok=True)
            return data_path

        if self._platform == "docker":
            data_dir = os.environ.get("SONORIUM_DATA_DIR", "/data")
            data_path = Path(data_dir)
            data_path.mkdir(parents=True, exist_ok=True)
            return data_path

        # Standalone - platform-specific user directory
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA", "")
            if appdata:
                data_path = Path(appdata) / "Sonorium"
            else:
                data_path = Path.home() / "Sonorium"
        elif sys.platform == "darwin":
            data_path = Path.home() / "Library" / "Application Support" / "Sonorium"
        else:
            # Linux/other
            data_path = Path.home() / ".sonorium"

        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    @cached_property
    def audio(self) -> Path:
        """Path to audio/themes directory."""
        # For standalone running from source, check for bundled themes
        if self._platform == "standalone":
            # Check if running from app/core/sonorium/
            bundled = self.package.parent.parent / "themes"
            if bundled.exists():
                return bundled

        audio_path = self.data / "audio"
        audio_path.mkdir(parents=True, exist_ok=True)
        return audio_path

    @cached_property
    def plugins(self) -> Path:
        """Path to user plugins directory."""
        plugins_path = self.data / "plugins"
        plugins_path.mkdir(parents=True, exist_ok=True)
        return plugins_path

    @cached_property
    def logs(self) -> Path:
        """Path to logs directory."""
        if self._platform == "standalone":
            # Standalone: logs in app/logs/ (relative to package)
            if getattr(sys, 'frozen', False):
                log_dir = Path(sys.executable).parent.parent / 'logs'
            else:
                log_dir = self.package.parent.parent / 'logs'
        else:
            # Docker/HA: logs in data directory
            log_dir = self.data / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    @cached_property
    def config(self) -> Path:
        """Path to configuration directory."""
        if self._platform == "standalone":
            return self.data
        return self.data

    @cached_property
    def state_file(self) -> Path:
        """Path to state.json file."""
        return self.data / "state.json"

    @cached_property
    def config_file(self) -> Path:
        """Path to config.json file."""
        return self.data / "config.json"

    # Convenience properties for sample files (used in tests/examples)
    @cached_property
    def example_700KB(self) -> Path:
        """Path to example MP3 file."""
        return self.audio / 'file_example_MP3_700KB.mp3'

    @cached_property
    def gambling(self) -> Path:
        """Path to sample audio file."""
        return self.audio / 'A Good Bass for Gambling.mp3'


# Singleton instance
paths = PackagePaths()
