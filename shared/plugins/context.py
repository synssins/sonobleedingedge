"""
Sonorium Plugin Context

Provides the PluginContext class that gives plugins access to Sonorium services
and the PluginState enum for tracking plugin lifecycle states.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sonorium.plugins.events import EventBus


class PluginState(Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"      # Plugin discovered but not loaded
    LOADING = "loading"        # Plugin is being loaded
    LOADED = "loaded"          # Plugin loaded but not active
    ACTIVATING = "activating"  # Plugin is being activated
    ACTIVE = "active"          # Plugin is active and running
    DEACTIVATING = "deactivating"  # Plugin is being deactivated
    ERROR = "error"            # Plugin encountered an error
    DISABLED = "disabled"      # Plugin explicitly disabled by user


class Platform(Enum):
    """Deployment platform types."""
    STANDALONE = "standalone"  # Windows/Mac/Linux desktop app
    HA_ADDON = "ha_addon"      # Home Assistant Add-on
    DOCKER = "docker"          # Docker container (standalone)


def detect_platform() -> Platform:
    """
    Detect the current deployment platform.

    Returns:
        Platform enum value indicating the current environment
    """
    # Check for Home Assistant Supervisor token (indicates HA addon)
    if os.environ.get("SUPERVISOR_TOKEN"):
        return Platform.HA_ADDON

    # Check for Docker container
    if os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
        return Platform.DOCKER

    # Default to standalone
    return Platform.STANDALONE


def get_plugins_directory() -> Path:
    """
    Get the appropriate plugins directory for the current platform.

    Returns:
        Path to the plugins directory
    """
    platform = detect_platform()

    if platform == Platform.HA_ADDON:
        # HA addon: user plugins in /config/sonorium/plugins
        return Path("/config/sonorium/plugins")

    if platform == Platform.DOCKER:
        # Docker: plugins in /data/plugins
        data_dir = os.environ.get("SONORIUM_DATA_DIR", "/data")
        return Path(data_dir) / "plugins"

    # Standalone: platform-specific user directory
    if sys.platform == "win32":
        # Windows: %APPDATA%/Sonorium/plugins
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Sonorium" / "plugins"
        return Path.home() / "Sonorium" / "plugins"

    if sys.platform == "darwin":
        # macOS: ~/Library/Application Support/Sonorium/plugins
        return Path.home() / "Library" / "Application Support" / "Sonorium" / "plugins"

    # Linux/other: ~/.sonorium/plugins
    return Path.home() / ".sonorium" / "plugins"


def get_data_directory() -> Path:
    """
    Get the appropriate data directory for the current platform.

    Returns:
        Path to the data directory
    """
    platform = detect_platform()

    if platform == Platform.HA_ADDON:
        return Path("/config/sonorium")

    if platform == Platform.DOCKER:
        return Path(os.environ.get("SONORIUM_DATA_DIR", "/data"))

    # Standalone
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Sonorium"
        return Path.home() / "Sonorium"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Sonorium"

    return Path.home() / ".sonorium"


@dataclass
class PluginContext:
    """
    Context object injected into plugins providing access to Sonorium services.

    This is the primary interface through which plugins interact with the
    Sonorium system. It provides access to managers, configuration, and
    the event bus for communication.

    Attributes:
        plugin_id: Unique identifier for this plugin
        plugin_dir: Path to the plugin's directory
        data_dir: Path to the plugin's data directory for persistence
        config: Plugin-specific configuration dictionary
        platform: Current deployment platform
        event_bus: Reference to the global event bus
    """
    plugin_id: str
    plugin_dir: Path
    data_dir: Path
    config: Dict[str, Any] = field(default_factory=dict)
    platform: Platform = field(default_factory=detect_platform)

    # Service references (set after initialization)
    event_bus: Optional[EventBus] = None
    theme_manager: Optional[Any] = None
    session_manager: Optional[Any] = None
    config_manager: Optional[Any] = None

    # Home Assistant specific (None if not HA addon)
    ha_client: Optional[Any] = None

    def __post_init__(self):
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a plugin setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self.config.get(key, default)

    async def set_setting(self, key: str, value: Any) -> None:
        """
        Set a plugin setting value.

        Args:
            key: Setting key
            value: Setting value

        Note:
            This updates the in-memory config. Persistence is handled
            by the PluginManager.
        """
        self.config[key] = value

    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Emit an event from this plugin.

        Args:
            event_type: Type of event to emit
            data: Event data dictionary
        """
        if self.event_bus:
            await self.event_bus.emit(event_type, data, source=self.plugin_id)

    def get_plugin_data_path(self, filename: str) -> Path:
        """
        Get a path within the plugin's data directory.

        Args:
            filename: Filename or relative path

        Returns:
            Full path to the file in the plugin's data directory
        """
        return self.data_dir / filename

    def is_ha_addon(self) -> bool:
        """Check if running as Home Assistant add-on."""
        return self.platform == Platform.HA_ADDON

    def is_standalone(self) -> bool:
        """Check if running as standalone application."""
        return self.platform == Platform.STANDALONE

    def is_docker(self) -> bool:
        """Check if running in Docker container."""
        return self.platform == Platform.DOCKER


def create_plugin_context(
    plugin_id: str,
    plugin_dir: Path,
    config: Optional[Dict[str, Any]] = None,
    event_bus: Optional[EventBus] = None,
) -> PluginContext:
    """
    Factory function to create a PluginContext.

    Args:
        plugin_id: Unique identifier for the plugin
        plugin_dir: Path to the plugin's directory
        config: Plugin-specific configuration
        event_bus: Reference to the event bus

    Returns:
        Configured PluginContext instance
    """
    data_dir = get_data_directory() / "plugin_data" / plugin_id

    return PluginContext(
        plugin_id=plugin_id,
        plugin_dir=plugin_dir,
        data_dir=data_dir,
        config=config or {},
        event_bus=event_bus,
    )
