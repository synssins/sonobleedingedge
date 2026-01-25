"""
Sonorium Platform Adapters

Provides platform-agnostic interfaces that plugins can depend on.
Concrete implementations are provided by each deployment target.

The goal is to allow shared code (especially plugins) to access:
- Configuration values
- File paths
- Runtime environment info

Without knowing whether they're running on Windows, Docker, or HA addon.

CORE CODE: This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PathProvider(Protocol):
    """
    Protocol for path resolution.

    Implementations provide paths appropriate for the current platform.
    Plugins should depend on this interface, not concrete implementations.
    """

    @property
    def data(self) -> Path:
        """User data directory (config, state, user plugins)."""
        ...

    @property
    def audio(self) -> Path:
        """Audio/themes directory."""
        ...

    @property
    def plugins(self) -> Path:
        """User plugins directory."""
        ...

    @property
    def logs(self) -> Path:
        """Logs directory."""
        ...

    @property
    def package(self) -> Path:
        """Package installation directory."""
        ...

    @property
    def platform(self) -> str:
        """Current platform identifier: 'standalone', 'docker', 'ha_addon'."""
        ...


@runtime_checkable
class ConfigProvider(Protocol):
    """
    Protocol for configuration access.

    Implementations provide config values appropriate for the platform:
    - Standalone: JSON file-based AppConfig
    - HA Addon: pydantic-settings with options.json

    Plugins should depend on this interface for config access.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        ...

    def get_plugin_settings(self, plugin_id: str) -> dict[str, Any]:
        """Get settings for a specific plugin."""
        ...

    def set_plugin_settings(self, plugin_id: str, settings: dict[str, Any]) -> None:
        """Set settings for a specific plugin."""
        ...

    @property
    def stream_url(self) -> str:
        """Base URL for audio streaming endpoint."""
        ...

    @property
    def stream_port(self) -> int:
        """Port for audio streaming."""
        ...

    @property
    def audio_path(self) -> Path:
        """Path to audio/themes directory."""
        ...

    @property
    def max_channels(self) -> int:
        """Maximum number of concurrent streaming channels."""
        ...


class RuntimeContext:
    """
    Runtime context providing access to platform services.

    This is the main entry point for plugins to access platform-specific
    functionality through platform-agnostic interfaces.

    Usage in plugins:
        from sonorium.platform import runtime
        data_dir = runtime.paths.data
        stream_url = runtime.config.stream_url
    """

    _instance: 'RuntimeContext | None' = None
    _paths: PathProvider | None = None
    _config: ConfigProvider | None = None

    def __new__(cls) -> 'RuntimeContext':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, paths: PathProvider, config: ConfigProvider) -> 'RuntimeContext':
        """
        Initialize the runtime context with platform-specific providers.

        Called once during application startup by the platform-specific
        initialization code.

        Args:
            paths: PathProvider implementation for this platform
            config: ConfigProvider implementation for this platform

        Returns:
            The initialized RuntimeContext singleton
        """
        instance = cls()
        cls._paths = paths
        cls._config = config
        return instance

    @property
    def paths(self) -> PathProvider:
        """Get the path provider."""
        if self._paths is None:
            raise RuntimeError(
                "RuntimeContext not initialized. "
                "Call RuntimeContext.initialize() during app startup."
            )
        return self._paths

    @property
    def config(self) -> ConfigProvider:
        """Get the config provider."""
        if self._config is None:
            raise RuntimeError(
                "RuntimeContext not initialized. "
                "Call RuntimeContext.initialize() during app startup."
            )
        return self._config

    @property
    def platform(self) -> str:
        """Current platform identifier."""
        return self.paths.platform

    @property
    def is_ha_addon(self) -> bool:
        """Check if running as Home Assistant addon."""
        return self.platform == "ha_addon"

    @property
    def is_docker(self) -> bool:
        """Check if running in Docker container."""
        return self.platform == "docker"

    @property
    def is_standalone(self) -> bool:
        """Check if running as standalone application."""
        return self.platform == "standalone"


# Singleton instance - initialized during app startup
runtime = RuntimeContext()


# Import capabilities
from .capabilities import (
    PlatformCapabilities,
    HACapabilities,
    MQTTCapabilities,
    LocalAudioCapabilities,
    AudioDevice,
    detect_platform,
    detect_all_capabilities,
    get_capabilities,
    refresh_capabilities,
    update_capabilities_from_settings,
)

# Import secure storage
from .secure_storage import (
    SecureStorage,
    get_secure_storage,
    initialize_secure_storage,
)

# Import unified settings
from .unified_settings import (
    UnifiedSettings,
    UnifiedSettingsManager,
    HAIntegrationSettings,
    MQTTSettings,
    LocalAudioSettings,
    get_settings_manager,
    initialize_settings_manager,
)

# Import adapters
from .adapters import (
    PackagePathsAdapter,
    StandaloneConfigAdapter,
    HAAddonConfigAdapter,
    create_standalone_runtime,
    create_ha_addon_runtime,
)


__all__ = [
    # Core protocols
    "PathProvider",
    "ConfigProvider",
    "RuntimeContext",
    "runtime",
    # Capabilities
    "PlatformCapabilities",
    "HACapabilities",
    "MQTTCapabilities",
    "LocalAudioCapabilities",
    "AudioDevice",
    "detect_platform",
    "detect_all_capabilities",
    "get_capabilities",
    "refresh_capabilities",
    "update_capabilities_from_settings",
    # Secure storage
    "SecureStorage",
    "get_secure_storage",
    "initialize_secure_storage",
    # Settings
    "UnifiedSettings",
    "UnifiedSettingsManager",
    "HAIntegrationSettings",
    "MQTTSettings",
    "LocalAudioSettings",
    "get_settings_manager",
    "initialize_settings_manager",
    # Adapters
    "PackagePathsAdapter",
    "StandaloneConfigAdapter",
    "HAAddonConfigAdapter",
    "create_standalone_runtime",
    "create_ha_addon_runtime",
]
