"""
Platform Adapter Implementations

Provides concrete implementations of PathProvider and ConfigProvider
that wrap the existing platform-specific classes.

These adapters allow the existing code to work unchanged while
providing a unified interface for plugins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from sonorium.platform import PathProvider, ConfigProvider

if TYPE_CHECKING:
    from sonorium.paths import PackagePaths


class PackagePathsAdapter:
    """
    Adapter that wraps PackagePaths to implement PathProvider protocol.

    PackagePaths already handles platform detection internally, so this
    adapter simply delegates to the existing implementation.
    """

    def __init__(self, paths: 'PackagePaths'):
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
        return self._paths.platform


class StandaloneConfigAdapter:
    """
    Adapter that wraps standalone AppConfig to implement ConfigProvider.

    Used in Windows standalone and Docker deployments where config
    is stored in a JSON file.
    """

    def __init__(self, config: Any):  # AppConfig type
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self._config, key, default)

    def set(self, key: str, value: Any) -> None:
        if hasattr(self._config, key):
            setattr(self._config, key, value)
            self._config.save()

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        settings = getattr(self._config, 'plugin_settings', {})
        return settings.get(plugin_id, {})

    def set_plugin_settings(self, plugin_id: str, settings: dict[str, Any]) -> None:
        if not hasattr(self._config, 'plugin_settings'):
            self._config.plugin_settings = {}
        self._config.plugin_settings[plugin_id] = settings
        self._config.save()

    @property
    def stream_url(self) -> str:
        # Standalone builds stream URL from local IP and port
        from sonorium.config import get_stream_base_url
        return get_stream_base_url(self.stream_port)

    @property
    def stream_port(self) -> int:
        return getattr(self._config, 'server_port', 8008)

    @property
    def audio_path(self) -> Path:
        path_str = getattr(self._config, 'audio_path', '')
        if path_str:
            return Path(path_str)
        from sonorium.config import get_default_audio_dir
        return get_default_audio_dir()

    @property
    def max_channels(self) -> int:
        return getattr(self._config, 'max_channels', 4)


class HAAddonConfigAdapter:
    """
    Adapter that wraps HA addon Settings to implement ConfigProvider.

    Used in Home Assistant addon deployments where config comes from
    options.json and environment variables via pydantic-settings.
    """

    def __init__(self, settings: Any):  # Settings type from settings.py
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
        from sonorium.paths import paths

        settings_file = paths.data / 'plugin_settings.json'
        try:
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    all_settings = json.load(f)
            else:
                all_settings = {}

            all_settings[plugin_id] = settings

            with open(settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)
        except Exception as e:
            from sonorium.obs import logger
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
        from sonorium.paths import paths
        return paths.audio

    @property
    def max_channels(self) -> int:
        return getattr(self._settings, 'max_channels', 6)


def create_standalone_runtime():
    """
    Create and initialize RuntimeContext for standalone/Docker deployment.

    Call this during standalone app initialization.
    """
    from sonorium.paths import paths
    from sonorium.config import get_config
    from sonorium.platform import RuntimeContext

    path_adapter = PackagePathsAdapter(paths)
    config_adapter = StandaloneConfigAdapter(get_config())

    return RuntimeContext.initialize(path_adapter, config_adapter)


def create_ha_addon_runtime():
    """
    Create and initialize RuntimeContext for HA addon deployment.

    Call this during HA addon initialization.
    """
    from sonorium.paths import paths
    from sonorium.settings import settings
    from sonorium.platform import RuntimeContext

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
