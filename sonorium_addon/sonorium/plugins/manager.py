"""
Sonorium Plugin Manager

Manages the lifecycle and coordination of all loaded plugins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from sonorium.plugins.base import BasePlugin
from sonorium.plugins.loader import (
    get_plugins_dir,
    get_bundled_plugins_dir,
    get_user_plugins_dir,
    get_all_plugin_dirs,
    discover_plugins,
    load_manifest,
    load_plugin_class,
    instantiate_plugin,
    save_manifest,
    is_plugin_bundled,
)
from sonorium.plugins.events import EventTypes, get_event_bus
from sonorium.obs import logger

if TYPE_CHECKING:
    from sonorium.config import AppConfig


class PluginManager:
    """
    Manages all Sonorium plugins.

    Handles:
    - Plugin discovery and loading
    - Enabling/disabling plugins
    - Plugin settings persistence
    - Routing actions to plugins
    """

    def __init__(
        self,
        config: AppConfig,
        plugins_dir: Optional[Path] = None,
        audio_path: Optional[Path] = None,
    ):
        """
        Initialize the plugin manager.

        Args:
            config: Application config for persisting settings
            plugins_dir: Directory containing plugins
            audio_path: Path to audio/themes directory
        """
        self.config = config
        self.plugins_dir = plugins_dir or get_plugins_dir()
        self.audio_path = audio_path or Path(config.audio_path)
        self.plugins: dict[str, BasePlugin] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """
        Discover and load all plugins from all plugin directories.

        Should be called during application startup.
        """
        if self._initialized:
            return

        logger.info("Initializing plugin manager...")

        # Log all plugin directories
        all_dirs = get_all_plugin_dirs()
        logger.debug(f"Plugin search paths ({len(all_dirs)}): {[str(d) for d in all_dirs]}")

        # Ensure user plugins directory exists
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # Discover plugins from ALL directories (not just self.plugins_dir)
        plugin_dirs = discover_plugins()  # No arg = scan all directories
        logger.info(f"Found {len(plugin_dirs)} plugin(s)")

        for plugin_dir in plugin_dirs:
            await self._load_plugin(plugin_dir)

        # Enable previously enabled plugins
        enabled_list = self.config.enabled_plugins
        for plugin_id in enabled_list:
            if plugin_id in self.plugins:
                await self.enable_plugin(plugin_id)

        # Auto-enable speaker plugins by default (unless explicitly disabled)
        disabled_list = getattr(self.config, 'disabled_plugins', [])
        for plugin_id, plugin in self.plugins.items():
            # Skip if already enabled or explicitly disabled
            if plugin.enabled or plugin_id in disabled_list:
                continue
            # Auto-enable speaker plugins
            if getattr(plugin, 'plugin_type', None) == 'speaker':
                logger.debug(f"Auto-enabling speaker plugin: {plugin_id}")
                await self.enable_plugin(plugin_id)

        self._initialized = True
        logger.info(f"Plugin manager initialized with {len(self.plugins)} plugin(s)")

    async def _load_plugin(self, plugin_dir: Path) -> Optional[BasePlugin]:
        """Load a single plugin from its directory."""
        try:
            # Load manifest
            manifest = load_manifest(plugin_dir)

            # Get plugin settings from config
            plugin_id = manifest.get("id", plugin_dir.name)
            settings = self.config.plugin_settings.get(plugin_id, {})

            # Load plugin class
            plugin_class = load_plugin_class(plugin_dir, manifest)
            if plugin_class is None:
                return None

            # Instantiate plugin with audio_path
            plugin = instantiate_plugin(plugin_class, plugin_dir, settings, self.audio_path)
            if plugin is None:
                return None

            # Set builtin flag - check manifest first, then location
            if manifest.get("builtin", False) or is_plugin_bundled(plugin_id):
                plugin._builtin = True

            # Apply manifest values to plugin instance if plugin class didn't define them
            # This is important because many plugins rely on manifest.json for metadata
            if not plugin.id and manifest.get("id"):
                plugin.id = manifest["id"]
            if not plugin.name and manifest.get("name"):
                plugin.name = manifest["name"]
            if plugin.version == "1.0.0" and manifest.get("version"):
                plugin.version = manifest["version"]
            if not plugin.description and manifest.get("description"):
                plugin.description = manifest["description"]
            if not plugin.author and manifest.get("author"):
                plugin.author = manifest["author"]
            if not plugin.category and manifest.get("category"):
                plugin.category = manifest["category"]

            # Fallback: use directory name if still no id
            if not plugin.id:
                plugin.id = plugin_dir.name

            # Update manifest with plugin info if it was auto-generated
            if not manifest.get("plugin_class"):
                manifest["plugin_class"] = plugin_class.__name__
                manifest["id"] = plugin.id
                manifest["name"] = plugin.name or manifest.get("name", plugin_dir.name)
                manifest["version"] = plugin.version
                manifest["description"] = plugin.description
                manifest["author"] = plugin.author
                save_manifest(plugin_dir, manifest)

            # Call on_load hook
            await plugin.on_load()

            # Store plugin
            self.plugins[plugin.id] = plugin
            logger.debug(f"Loaded plugin: {plugin.name} ({plugin.id})")

            # Emit plugin loaded event
            try:
                event_bus = get_event_bus()
                await event_bus.emit(
                    EventTypes.PLUGIN_LOADED,
                    {"plugin_id": plugin.id, "plugin_name": plugin.name},
                )
            except Exception as e:
                logger.debug(f"Could not emit plugin loaded event: {e}")

            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
            # Emit plugin error event
            try:
                event_bus = get_event_bus()
                await event_bus.emit(
                    EventTypes.PLUGIN_ERROR,
                    {"plugin_dir": str(plugin_dir), "error": str(e)},
                )
            except Exception:
                pass
            return None

    async def reload_plugins(self) -> None:
        """Reload all plugins."""
        # Unload existing plugins
        for plugin_id in list(self.plugins.keys()):
            await self._unload_plugin(plugin_id)

        self.plugins.clear()
        self._initialized = False

        # Reinitialize
        await self.initialize()

    async def _unload_plugin(self, plugin_id: str) -> None:
        """Unload a single plugin."""
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            return

        plugin_name = plugin.name
        try:
            if plugin.enabled:
                await plugin.on_disable()
            await plugin.on_unload()

            # Emit plugin unloaded event
            try:
                event_bus = get_event_bus()
                await event_bus.emit(
                    EventTypes.PLUGIN_UNLOADED,
                    {"plugin_id": plugin_id, "plugin_name": plugin_name},
                )
            except Exception as e:
                logger.debug(f"Could not emit plugin unloaded event: {e}")

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}")

    def list_plugins(self) -> list[dict]:
        """
        List all loaded plugins.

        Returns:
            List of plugin info dicts
        """
        return [plugin.to_dict() for plugin in self.plugins.values()]

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """Get a plugin by ID."""
        return self.plugins.get(plugin_id)

    def get_plugins_by_type(self, plugin_type: str) -> list[BasePlugin]:
        """
        Get all plugins of a specific type.

        Args:
            plugin_type: The plugin type to filter by (e.g., "speaker", "source")

        Returns:
            List of plugins matching the type
        """
        return [
            plugin for plugin in self.plugins.values()
            if getattr(plugin, 'plugin_type', None) == plugin_type
        ]

    async def enable_plugin(self, plugin_id: str) -> bool:
        """
        Enable a plugin.

        Args:
            plugin_id: The plugin to enable

        Returns:
            True if enabled successfully
        """
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            logger.error(f"Plugin not found: {plugin_id}")
            return False

        if plugin.enabled:
            return True  # Already enabled

        try:
            await plugin.on_enable()
            plugin.enabled = True

            # Persist enabled state
            enabled_list = self.config.enabled_plugins
            if plugin_id not in enabled_list:
                enabled_list.append(plugin_id)

            # Remove from disabled list if present
            disabled_list = getattr(self.config, 'disabled_plugins', None)
            if disabled_list is not None and plugin_id in disabled_list:
                disabled_list.remove(plugin_id)

            self.config.save()
            logger.debug(f"Enabled plugin: {plugin.name}")

            # Emit plugin activated event
            try:
                event_bus = get_event_bus()
                await event_bus.emit(
                    EventTypes.PLUGIN_ACTIVATED,
                    {"plugin_id": plugin_id, "plugin_name": plugin.name},
                )
            except Exception as e:
                logger.debug(f"Could not emit plugin activated event: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to enable plugin {plugin_id}: {e}")
            return False

    async def disable_plugin(self, plugin_id: str) -> bool:
        """
        Disable a plugin.

        Args:
            plugin_id: The plugin to disable

        Returns:
            True if disabled successfully
        """
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            logger.error(f"Plugin not found: {plugin_id}")
            return False

        if not plugin.enabled:
            return True  # Already disabled

        try:
            await plugin.on_disable()
            plugin.enabled = False

            # Persist enabled state
            enabled_list = self.config.enabled_plugins
            if plugin_id in enabled_list:
                enabled_list.remove(plugin_id)

            # Track explicitly disabled plugins (prevents auto-enable for speaker plugins)
            disabled_list = getattr(self.config, 'disabled_plugins', None)
            if disabled_list is not None and plugin_id not in disabled_list:
                disabled_list.append(plugin_id)

            self.config.save()
            logger.info(f"Disabled plugin: {plugin.name}")

            # Emit plugin deactivated event
            try:
                event_bus = get_event_bus()
                await event_bus.emit(
                    EventTypes.PLUGIN_DEACTIVATED,
                    {"plugin_id": plugin_id, "plugin_name": plugin.name},
                )
            except Exception as e:
                logger.debug(f"Could not emit plugin deactivated event: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_id}: {e}")
            return False

    async def call_action(
        self,
        plugin_id: str,
        action: str,
        data: dict,
    ) -> dict:
        """
        Call an action on a plugin.

        Args:
            plugin_id: The plugin to call
            action: The action to perform
            data: Action data/parameters

        Returns:
            Result dict from the plugin
        """
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            return {"success": False, "message": f"Plugin not found: {plugin_id}"}

        if not plugin.enabled:
            return {"success": False, "message": f"Plugin is not enabled: {plugin_id}"}

        try:
            result = await plugin.handle_action(action, data)
            return result
        except Exception as e:
            logger.error(f"Error calling action {action} on {plugin_id}: {e}")
            return {"success": False, "message": str(e)}

    def get_plugin_settings(self, plugin_id: str) -> dict:
        """Get settings for a plugin."""
        return self.config.plugin_settings.get(plugin_id, {})

    def update_plugin_settings(self, plugin_id: str, settings: dict) -> bool:
        """
        Update settings for a plugin.

        Args:
            plugin_id: The plugin to update
            settings: New settings dict

        Returns:
            True if updated successfully
        """
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            return False

        # Update in-memory settings
        plugin.update_settings(settings)

        # Persist to config
        self.config.plugin_settings[plugin_id] = settings
        self.config.save()

        return True

    # Theme Integration Hooks

    async def notify_theme_created(self, theme_id: str, theme_path: Path) -> None:
        """Notify all enabled plugins that a theme was created."""
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    await plugin.on_theme_created(theme_id, theme_path)
                except Exception as e:
                    logger.error(
                        f"Error in {plugin.id}.on_theme_created: {e}"
                    )

    async def notify_theme_deleted(self, theme_id: str) -> None:
        """Notify all enabled plugins that a theme was deleted."""
        for plugin in self.plugins.values():
            if plugin.enabled:
                try:
                    await plugin.on_theme_deleted(theme_id)
                except Exception as e:
                    logger.error(
                        f"Error in {plugin.id}.on_theme_deleted: {e}"
                    )

    # Plugin Directory Info

    def get_plugin_directories(self) -> dict:
        """
        Get information about plugin directories.

        Returns:
            Dict with directory info for API responses
        """
        bundled = get_bundled_plugins_dir()
        user = get_user_plugins_dir()
        all_dirs = get_all_plugin_dirs()

        return {
            "bundled": {
                "path": str(bundled),
                "exists": bundled.exists(),
                "writable": False,  # Bundled is read-only
            },
            "user": {
                "path": str(user),
                "exists": user.exists(),
                "writable": user.exists() and user.is_dir(),
            },
            "all_paths": [str(d) for d in all_dirs],
        }

    @property
    def state_store(self):
        """Get the config/state store (for API compatibility)."""
        return self.config
