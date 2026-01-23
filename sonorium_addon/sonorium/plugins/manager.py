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

        # Auto-install platform default plugins on first run
        await self._install_platform_defaults()

        # Fix plugin categories from catalog (for plugins installed before category fix)
        await self._fix_plugin_categories()

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

            # Apply category from manifest or derive from plugin_type
            if not plugin.category:
                if manifest.get("category"):
                    plugin.category = manifest["category"]
                elif hasattr(plugin, 'plugin_type') and plugin.plugin_type:
                    # Map plugin_type to category for UI grouping
                    type_to_category = {
                        "speaker": "speakers",
                        "source": "sources",
                        "importer": "importers",
                    }
                    plugin.category = type_to_category.get(plugin.plugin_type, "utilities")

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

    async def _install_platform_defaults(self) -> None:
        """
        Install platform default plugins on first run.

        Checks the plugins_initialized flag in state/config.
        If False, fetches the catalog and installs default plugins for the platform.
        """
        # Check if already initialized
        if hasattr(self.config, 'settings'):
            # StateStore (HA addon)
            settings = self.config.settings
        elif hasattr(self.config, 'plugins_initialized'):
            # Direct config object
            settings = self.config
        else:
            logger.debug("Cannot determine plugins_initialized state, skipping auto-install")
            return

        if getattr(settings, 'plugins_initialized', False):
            logger.debug("Plugins already initialized, skipping auto-install")
            return

        logger.info("First run detected, installing platform default plugins...")

        try:
            import aiohttp
            import zipfile
            import io
            import shutil

            # Fetch catalog
            catalog_url = 'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/catalog.json'
            async with aiohttp.ClientSession() as session:
                async with session.get(catalog_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.warning(f"Failed to fetch plugin catalog: HTTP {resp.status}")
                        return
                    catalog = await resp.json(content_type=None)

            # Get platform defaults (default to ha_addon)
            platform = "ha_addon"  # TODO: detect platform properly
            platform_defaults = catalog.get('platform_defaults', {})
            default_plugins = platform_defaults.get(platform, [])

            if not default_plugins:
                logger.info(f"No default plugins defined for platform: {platform}")
                settings.plugins_initialized = True
                if hasattr(self.config, 'save'):
                    self.config.save()
                return

            logger.info(f"Installing {len(default_plugins)} default plugins for {platform}: {default_plugins}")

            # Build plugin info lookup
            plugin_lookup = {p['id']: p for p in catalog.get('plugins', [])}

            installed_count = 0
            for plugin_id in default_plugins:
                # Skip if already installed
                if plugin_id in self.plugins:
                    logger.debug(f"Plugin {plugin_id} already installed, skipping")
                    continue

                plugin_info = plugin_lookup.get(plugin_id)
                if not plugin_info:
                    logger.warning(f"Plugin {plugin_id} not found in catalog, skipping")
                    continue

                zip_filename = plugin_info.get('zip_file')
                if not zip_filename:
                    logger.warning(f"Plugin {plugin_id} has no zip_file, skipping")
                    continue

                # Download and install
                zip_url = f'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/{zip_filename}'
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(zip_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                            if resp.status != 200:
                                logger.warning(f"Failed to download {plugin_id}: HTTP {resp.status}")
                                continue
                            content = await resp.read()

                    # Extract to plugins directory
                    zip_buffer = io.BytesIO(content)
                    with zipfile.ZipFile(zip_buffer, 'r') as zf:
                        file_list = zf.namelist()
                        plugin_py_paths = [f for f in file_list if f.endswith('plugin.py')]
                        if not plugin_py_paths:
                            logger.warning(f"No plugin.py found in {plugin_id} ZIP")
                            continue

                        plugin_py = plugin_py_paths[0]
                        plugin_dir_name = plugin_py.rsplit('/', 1)[0] if '/' in plugin_py else ''
                        target_dir = self.plugins_dir / plugin_id

                        if target_dir.exists():
                            shutil.rmtree(target_dir)

                        target_dir.mkdir(parents=True, exist_ok=True)
                        for member in zf.namelist():
                            if plugin_dir_name and member.startswith(plugin_dir_name + '/'):
                                target_path = target_dir / member[len(plugin_dir_name) + 1:]
                            elif plugin_dir_name and member == plugin_dir_name:
                                continue
                            else:
                                target_path = target_dir / member

                            if member.endswith('/'):
                                target_path.mkdir(parents=True, exist_ok=True)
                            else:
                                target_path.parent.mkdir(parents=True, exist_ok=True)
                                with zf.open(member) as src, open(target_path, 'wb') as dst:
                                    dst.write(src.read())

                    # Update manifest.json with category from catalog
                    manifest_path = target_dir / 'manifest.json'
                    if manifest_path.exists() and plugin_info.get('category'):
                        import json
                        try:
                            with open(manifest_path, 'r') as f:
                                manifest = json.load(f)
                            manifest['category'] = plugin_info['category']
                            with open(manifest_path, 'w') as f:
                                json.dump(manifest, f, indent=2)
                        except Exception as e:
                            logger.warning(f"Could not update manifest category for {plugin_id}: {e}")

                    # Load the newly installed plugin
                    await self._load_plugin(target_dir)
                    installed_count += 1
                    logger.info(f"Installed default plugin: {plugin_id}")

                except Exception as e:
                    logger.error(f"Failed to install default plugin {plugin_id}: {e}")
                    continue

            logger.info(f"Installed {installed_count} default plugins")

        except Exception as e:
            logger.error(f"Failed to install platform defaults: {e}")

        # Mark as initialized regardless of success (don't retry on every startup)
        settings.plugins_initialized = True
        if hasattr(self.config, 'save'):
            self.config.save()

    async def _fix_plugin_categories(self) -> None:
        """
        Fix plugin categories by checking against the catalog.

        This corrects plugins that were installed before category support
        was properly implemented.
        """
        try:
            import aiohttp
            import json

            # Fetch catalog
            catalog_url = 'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/catalog.json'
            async with aiohttp.ClientSession() as session:
                async with session.get(catalog_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.debug("Could not fetch catalog for category fix")
                        return
                    catalog = await resp.json(content_type=None)

            # Build category lookup from catalog
            category_lookup = {p['id']: p.get('category') for p in catalog.get('plugins', [])}

            fixed_count = 0
            for plugin_id, plugin in self.plugins.items():
                catalog_category = category_lookup.get(plugin_id)
                if not catalog_category:
                    continue

                # Check if plugin has wrong or missing category
                current_category = getattr(plugin, 'category', None)
                if current_category == catalog_category:
                    continue

                # Update the plugin object
                plugin.category = catalog_category

                # Update the manifest file
                plugin_dir = self.plugins_dir / plugin_id
                manifest_path = plugin_dir / 'manifest.json'
                if manifest_path.exists():
                    try:
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                        manifest['category'] = catalog_category
                        with open(manifest_path, 'w') as f:
                            json.dump(manifest, f, indent=2)
                        fixed_count += 1
                        logger.debug(f"Fixed category for {plugin_id}: {current_category} -> {catalog_category}")
                    except Exception as e:
                        logger.warning(f"Could not update manifest for {plugin_id}: {e}")

            if fixed_count > 0:
                logger.info(f"Fixed categories for {fixed_count} plugin(s)")

        except Exception as e:
            logger.debug(f"Could not fix plugin categories: {e}")

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
