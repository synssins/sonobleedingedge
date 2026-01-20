"""
Sonorium Plugin Manager

Manages the lifecycle and coordination of all loaded plugins.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from sonorium.plugins.base import BasePlugin
from sonorium.plugins.loader import (
    get_plugins_dir,
    discover_plugins,
    load_manifest,
    load_plugin_class,
    instantiate_plugin,
    save_manifest,
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
        Discover and load all plugins.

        Should be called during application startup.
        """
        if self._initialized:
            return

        logger.info("Initializing plugin manager...")
        logger.info(f"Plugins directory: {self.plugins_dir}")

        # Ensure plugins directory exists
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        # Discover and load plugins
        plugin_dirs = discover_plugins(self.plugins_dir)
        logger.info(f"Found {len(plugin_dirs)} plugin(s)")

        for plugin_dir in plugin_dirs:
            await self._load_plugin(plugin_dir)

        # Enable previously enabled plugins
        enabled_list = self.config.enabled_plugins
        for plugin_id in enabled_list:
            if plugin_id in self.plugins:
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

            # Set builtin flag from manifest if present
            if manifest.get("builtin", False):
                plugin._builtin = True

            # Update manifest with plugin info if it was auto-generated
            if not manifest.get("plugin_class"):
                manifest["plugin_class"] = plugin_class.__name__
                manifest["id"] = plugin.id or plugin_dir.name
                manifest["name"] = plugin.name or manifest["name"]
                manifest["version"] = plugin.version
                manifest["description"] = plugin.description
                manifest["author"] = plugin.author
                save_manifest(plugin_dir, manifest)

            # Call on_load hook
            await plugin.on_load()

            # Store plugin
            self.plugins[plugin.id] = plugin
            logger.info(f"Loaded plugin: {plugin.name} ({plugin.id})")

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
                self.config.save()

            logger.info(f"Enabled plugin: {plugin.name}")

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

    # Plugin Installation/Deletion

    async def install_plugin_from_zip(self, zip_path: Path) -> dict:
        """
        Install a plugin from a zip file.

        The zip file should contain a plugin directory with:
        - manifest.json (optional but recommended)
        - plugin.py (required)

        Args:
            zip_path: Path to the zip file

        Returns:
            dict with success status and message
        """
        try:
            if not zip_path.exists():
                return {"success": False, "message": f"Zip file not found: {zip_path}"}

            if not zipfile.is_zipfile(zip_path):
                return {"success": False, "message": "Invalid zip file"}

            # Extract to temporary directory first
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_path)

                # Find the plugin directory (could be root or first subdirectory)
                plugin_dir = None
                plugin_py = temp_path / "plugin.py"

                if plugin_py.exists():
                    # Plugin files are at root of zip
                    plugin_dir = temp_path
                else:
                    # Look for first subdirectory with plugin.py
                    for item in temp_path.iterdir():
                        if item.is_dir() and (item / "plugin.py").exists():
                            plugin_dir = item
                            break

                if plugin_dir is None:
                    return {
                        "success": False,
                        "message": "No plugin.py found in zip file"
                    }

                # Load manifest to get plugin ID
                manifest = load_manifest(plugin_dir)
                plugin_id = manifest.get("id", plugin_dir.name)

                # Check if plugin already exists
                if plugin_id in self.plugins:
                    existing = self.plugins[plugin_id]
                    if existing._builtin:
                        return {
                            "success": False,
                            "message": f"Cannot overwrite builtin plugin: {plugin_id}"
                        }
                    # Unload existing plugin
                    await self._unload_plugin(plugin_id)
                    del self.plugins[plugin_id]

                # Determine target directory
                target_dir = self.plugins_dir / plugin_id

                # Remove existing directory if present
                if target_dir.exists():
                    shutil.rmtree(target_dir)

                # Copy plugin to plugins directory
                if plugin_dir == temp_path:
                    # Files at root - create directory and copy contents
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for item in plugin_dir.iterdir():
                        if item.is_dir():
                            shutil.copytree(item, target_dir / item.name)
                        else:
                            shutil.copy2(item, target_dir / item.name)
                else:
                    # Copy subdirectory
                    shutil.copytree(plugin_dir, target_dir)

                # Load the new plugin
                plugin = await self._load_plugin(target_dir)
                if plugin is None:
                    # Cleanup on failure
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    return {
                        "success": False,
                        "message": "Failed to load plugin after installation"
                    }

                logger.info(f"Installed plugin: {plugin.name} ({plugin.id})")
                return {
                    "success": True,
                    "message": f"Plugin '{plugin.name}' installed successfully",
                    "plugin": plugin.to_dict()
                }

        except Exception as e:
            logger.error(f"Failed to install plugin from {zip_path}: {e}")
            return {"success": False, "message": str(e)}

    async def install_plugin_from_bytes(self, data: bytes, filename: str) -> dict:
        """
        Install a plugin from uploaded zip bytes.

        Args:
            data: Raw zip file bytes
            filename: Original filename (for logging)

        Returns:
            dict with success status and message
        """
        try:
            # Write to temporary file
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tf:
                tf.write(data)
                temp_zip = Path(tf.name)

            try:
                result = await self.install_plugin_from_zip(temp_zip)
                return result
            finally:
                # Clean up temp file
                if temp_zip.exists():
                    temp_zip.unlink()

        except Exception as e:
            logger.error(f"Failed to install plugin from uploaded file: {e}")
            return {"success": False, "message": str(e)}

    async def delete_plugin(self, plugin_id: str) -> dict:
        """
        Delete a plugin.

        Builtin plugins cannot be deleted.

        Args:
            plugin_id: The plugin to delete

        Returns:
            dict with success status and message
        """
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            return {"success": False, "message": f"Plugin not found: {plugin_id}"}

        if plugin._builtin:
            return {
                "success": False,
                "message": f"Cannot delete builtin plugin: {plugin_id}"
            }

        try:
            # Get plugin directory before unloading
            plugin_dir = plugin.plugin_dir
            plugin_name = plugin.name

            # Disable and unload
            if plugin.enabled:
                await self.disable_plugin(plugin_id)
            await self._unload_plugin(plugin_id)

            # Remove from plugins dict
            del self.plugins[plugin_id]

            # Delete the plugin directory
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)
                logger.info(f"Deleted plugin directory: {plugin_dir}")

            # Remove settings
            if plugin_id in self.config.plugin_settings:
                del self.config.plugin_settings[plugin_id]
                self.config.save()

            logger.info(f"Deleted plugin: {plugin_name} ({plugin_id})")
            return {
                "success": True,
                "message": f"Plugin '{plugin_name}' deleted successfully"
            }

        except Exception as e:
            logger.error(f"Failed to delete plugin {plugin_id}: {e}")
            return {"success": False, "message": str(e)}

    def get_plugins_by_type(self, plugin_type: str) -> list[BasePlugin]:
        """
        Get all plugins of a specific type.

        Args:
            plugin_type: The plugin type (speaker, importer, utility, automation)

        Returns:
            List of plugins matching the type
        """
        return [
            plugin for plugin in self.plugins.values()
            if plugin.plugin_type == plugin_type
        ]

    def get_speaker_plugins(self) -> list[BasePlugin]:
        """Get all speaker plugins."""
        return self.get_plugins_by_type("speaker")

    def get_importer_plugins(self) -> list[BasePlugin]:
        """Get all importer plugins."""
        return self.get_plugins_by_type("importer")
