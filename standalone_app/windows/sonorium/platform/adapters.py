"""
Platform Adapter Implementations

Provides concrete implementations of PathProvider and ConfigProvider
that wrap the existing platform-specific classes.

These adapters allow the existing code to work unchanged while
providing a unified interface for plugins.

CORE CODE: This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING


class PackagePathsAdapter:
    """
    Adapter that wraps PackagePaths to implement PathProvider protocol.

    PackagePaths already handles platform detection internally, so this
    adapter simply delegates to the existing implementation.
    """

    def __init__(self, paths):
        """
        Initialize with a paths object.

        Args:
            paths: A paths object with data, audio, plugins, logs, package properties
        """
        self._paths = paths

    @property
    def data(self) -> Path:
        return self._paths.data

    @property
    def audio(self) -> Path:
        return self._paths.audio

    @property
    def plugins(self) -> Path:
        return self._paths.plugins

    @property
    def logs(self) -> Path:
        return self._paths.logs

    @property
    def package(self) -> Path:
        return self._paths.package

    @property
    def platform(self) -> str:
        return getattr(self._paths, 'platform', 'standalone')


class StandaloneConfigAdapter:
    """
    Adapter that wraps standalone AppConfig to implement ConfigProvider.

    Used in Windows standalone and Docker deployments where config
    is stored in a JSON file.
    """

    def __init__(self, config: Any):
        """
        Initialize with a config object.

        Args:
            config: AppConfig type object with attribute-based access
        """
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._config, key, default)

    def set(self, key: str, value: Any) -> None:
        if hasattr(self._config, key):
            setattr(self._config, key, value)
            if hasattr(self._config, 'save'):
                self._config.save()

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        settings = getattr(self._config, 'plugin_settings', {})
        return settings.get(plugin_id, {})

    def set_plugin_settings(self, plugin_id: str, settings: dict[str, Any]) -> None:
        if not hasattr(self._config, 'plugin_settings'):
            self._config.plugin_settings = {}
        self._config.plugin_settings[plugin_id] = settings
        if hasattr(self._config, 'save'):
            self._config.save()

    @property
    def stream_url(self) -> str:
        # Build stream URL from port
        from ..core.utils import get_local_ip
        ip = get_local_ip()
        port = self.stream_port
        return f"http://{ip}:{port}"

    @property
    def stream_port(self) -> int:
        return getattr(self._config, 'server_port', 8008)

    @property
    def audio_path(self) -> Path:
        path_str = getattr(self._config, 'audio_path', '')
        if path_str:
            return Path(path_str)
        return Path.home() / '.sonorium' / 'themes'

    @property
    def max_channels(self) -> int:
        return getattr(self._config, 'max_channels', 4)


class HAAddonConfigAdapter:
    """
    Adapter that wraps HA addon Settings to implement ConfigProvider.

    Used in Home Assistant addon deployments where config comes from
    options.json and environment variables via pydantic-settings.
    """

    def __init__(self, settings: Any):
        """
        Initialize with a settings object.

        Args:
            settings: Settings type from settings.py (pydantic-settings based)
        """
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._settings, key, default)

    def set(self, key: str, value: Any) -> None:
        # HA addon settings are mostly read-only (from options.json)
        # This is a no-op for most settings
        if hasattr(self._settings, key):
            setattr(self._settings, key, value)

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        # HA addon stores plugin settings differently
        # Check if there's a plugin_settings attribute
        settings = getattr(self._settings, 'plugin_settings', {})
        if isinstance(settings, dict):
            return settings.get(plugin_id, {})
        return {}

    def set_plugin_settings(self, plugin_id: str, settings: dict[str, Any]) -> None:
        # HA addon plugin settings need to be persisted differently
        # This may need to write to a JSON file in /config/sonorium/
        import json

        # Get data directory
        data_dir = Path('/config/sonorium')
        settings_file = data_dir / 'plugin_settings.json'

        try:
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}

            all_settings[plugin_id] = settings

            data_dir.mkdir(parents=True, exist_ok=True)
            with open(settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)
        except Exception as e:
            from ..obs import logger
            logger.error(f"Failed to save plugin settings: {e}")

    @property
    def stream_url(self) -> str:
        return getattr(self._settings, 'stream_url', 'http://127.0.0.1:8008')

    @property
    def stream_port(self) -> int:
        return getattr(self._settings, 'stream_port', 8008)

    @property
    def audio_path(self) -> Path:
        path_str = getattr(self._settings, 'path_audio', '')
        if path_str:
            return Path(path_str)
        return Path('/config/sonorium/themes')

    @property
    def max_channels(self) -> int:
        return getattr(self._settings, 'max_channels', 6)


def create_standalone_runtime(paths, config):
    """
    Create and initialize RuntimeContext for standalone/Docker deployment.

    Args:
        paths: PackagePaths or similar object
        config: AppConfig or similar object

    Returns:
        The initialized RuntimeContext singleton
    """
    from . import RuntimeContext

    path_adapter = PackagePathsAdapter(paths)
    config_adapter = StandaloneConfigAdapter(config)

    return RuntimeContext.initialize(path_adapter, config_adapter)


def create_ha_addon_runtime(paths, settings):
    """
    Create and initialize RuntimeContext for HA addon deployment.

    Args:
        paths: PackagePaths or similar object
        settings: Settings object from settings.py

    Returns:
        The initialized RuntimeContext singleton
    """
    from . import RuntimeContext

    path_adapter = PackagePathsAdapter(paths)
    config_adapter = HAAddonConfigAdapter(settings)

    return RuntimeContext.initialize(path_adapter, config_adapter)


__all__ = [
    "PackagePathsAdapter",
    "StandaloneConfigAdapter",
    "HAAddonConfigAdapter",
    "create_standalone_runtime",
    "create_ha_addon_runtime",
]
