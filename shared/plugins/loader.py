"""
Sonorium Plugin Loader

Handles discovery and dynamic loading of plugins from multiple directories.
Supports both bundled plugins (shipped with the app) and user-installed plugins.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Type, List

from sonorium.plugins.base import BasePlugin
from sonorium.obs import logger


# ============================================================
# Module-level caches
# ============================================================
_builtin_plugin_ids_cache: Optional[list[str]] = None


# ============================================================
# Plugin Directory Functions
# ============================================================

def get_bundled_plugins_dir() -> Path:
    """
    Get the bundled plugins directory (read-only, shipped with the app).

    Returns:
        Path to bundled plugins directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE - bundled plugins next to EXE
        return Path(sys.executable).parent / 'plugins'
    else:
        # Running as script - plugins are inside the sonorium package
        # This is the same for both HA addon and development
        return Path(__file__).parent


def get_user_plugins_dir() -> Path:
    """
    Get the user plugins directory (writable, for user-installed plugins).

    This is where users can install additional plugins via the UI.

    Returns:
        Path to user plugins directory
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE - user plugins in AppData
        import appdirs
        user_dir = Path(appdirs.user_data_dir("Sonorium", "Sonorium")) / 'plugins'
    elif os.environ.get('SUPERVISOR_TOKEN'):
        # Running in HA addon - user plugins in /data/plugins (persistent)
        user_dir = Path('/data/plugins')
    else:
        # Running as script/development - user plugins in project root
        user_dir = Path(__file__).parent.parent.parent / 'plugins'

    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_all_plugin_dirs() -> List[Path]:
    """
    Get all plugin directories to scan, in priority order.

    User plugins directory is first (higher priority for overrides),
    followed by bundled plugins directory.

    Returns:
        List of plugin directory paths
    """
    dirs = []

    # User plugins first (can override bundled)
    user_dir = get_user_plugins_dir()
    if user_dir.exists():
        dirs.append(user_dir)

    # Bundled plugins second
    bundled_dir = get_bundled_plugins_dir()
    if bundled_dir.exists() and bundled_dir != user_dir:
        dirs.append(bundled_dir)

    return dirs


def get_plugins_dir() -> Path:
    """
    Get the primary plugins directory (for backwards compatibility).

    Returns the user plugins directory as the primary writable location.
    Use get_all_plugin_dirs() to get all directories for discovery.

    Returns:
        Path to primary (user) plugins directory
    """
    return get_user_plugins_dir()


# ============================================================
# Plugin Discovery
# ============================================================

def discover_plugins(plugins_dir: Optional[Path] = None) -> list[Path]:
    """
    Discover plugin directories.

    Each plugin must be a directory containing at least a plugin.py file.
    Supports both flat structure (plugins/chromecast/) and categorized
    structure (plugins/speakers/chromecast/).

    Args:
        plugins_dir: Specific directory to scan, or None to scan all directories

    Returns:
        List of paths to valid plugin directories
    """
    if plugins_dir is not None:
        # Scan specific directory
        return _scan_plugins_dir(plugins_dir)

    # Scan all plugin directories
    all_dirs = get_all_plugin_dirs()
    logger.info(f"Discovering plugins from {len(all_dirs)} location(s)")

    plugin_dirs = []
    seen_ids = set()  # Track plugin IDs to avoid duplicates

    for search_dir in all_dirs:
        found = _scan_plugins_dir(search_dir)
        for plugin_dir in found:
            plugin_id = plugin_dir.name
            if plugin_id not in seen_ids:
                plugin_dirs.append(plugin_dir)
                seen_ids.add(plugin_id)
            else:
                logger.debug(f"Skipping duplicate plugin '{plugin_id}' from {search_dir}")

    logger.info(f"Plugin discovery complete: found {len(plugin_dirs)} unique plugin(s)")
    return plugin_dirs


def _scan_plugins_dir(plugins_dir: Path) -> list[Path]:
    """
    Scan a single directory for plugins.

    Args:
        plugins_dir: Directory to scan

    Returns:
        List of plugin directory paths found
    """
    logger.debug(f"Scanning for plugins in: {plugins_dir}")

    if not plugins_dir.exists():
        logger.warning(f"Plugins directory does not exist: {plugins_dir}")
        return []

    plugin_dirs = []

    def scan_directory(directory: Path, depth: int = 0):
        """Recursively scan for plugin directories (max depth 2)."""
        if depth > 2:  # Prevent infinite recursion
            return

        logger.debug(f"Scanning directory (depth {depth}): {directory}")

        try:
            items = list(directory.iterdir())
            logger.debug(f"  Found {len(items)} items in {directory.name}")
        except PermissionError as e:
            logger.warning(f"Permission denied scanning {directory}: {e}")
            return
        except OSError as e:
            logger.warning(f"Error scanning {directory}: {e}")
            return

        for item in items:
            if item.is_dir() and not item.name.startswith(('__', '.')):
                plugin_file = item / "plugin.py"
                if plugin_file.exists():
                    plugin_dirs.append(item)
                    logger.debug(f"Found plugin: {item.name} at {item}")
                else:
                    # Check subdirectories (for categorized structure like speakers/, sources/)
                    scan_directory(item, depth + 1)

    scan_directory(plugins_dir)
    return plugin_dirs


def get_builtin_plugin_ids() -> list[str]:
    """
    Get list of plugin IDs that are bundled with the application.

    These are the plugins shipped in the bundled plugins directory.
    Results are cached to avoid repeated directory scans.

    Returns:
        List of plugin ID strings
    """
    global _builtin_plugin_ids_cache

    # Return cached result if available
    if _builtin_plugin_ids_cache is not None:
        return _builtin_plugin_ids_cache

    bundled_dir = get_bundled_plugins_dir()
    if not bundled_dir.exists():
        _builtin_plugin_ids_cache = []
        return _builtin_plugin_ids_cache

    builtin_ids = []
    for plugin_dir in _scan_plugins_dir(bundled_dir):
        builtin_ids.append(plugin_dir.name)

    _builtin_plugin_ids_cache = builtin_ids
    logger.debug(f"Cached {len(builtin_ids)} builtin plugin IDs")
    return builtin_ids


def clear_builtin_plugin_cache() -> None:
    """
    Clear the builtin plugin ID cache.

    Call this if plugins are added/removed and the cache needs to be refreshed.
    """
    global _builtin_plugin_ids_cache
    _builtin_plugin_ids_cache = None


def is_plugin_bundled(plugin_id: str) -> bool:
    """
    Check if a plugin is a bundled (built-in) plugin.

    Args:
        plugin_id: The plugin ID to check

    Returns:
        True if plugin is bundled, False otherwise
    """
    return plugin_id in get_builtin_plugin_ids()


def get_plugin_location(plugin_id: str) -> Optional[Path]:
    """
    Find where a specific plugin is located.

    Searches all plugin directories for the given plugin ID.

    Args:
        plugin_id: The plugin ID to find

    Returns:
        Path to plugin directory, or None if not found
    """
    for search_dir in get_all_plugin_dirs():
        # Check flat structure
        direct_path = search_dir / plugin_id
        if (direct_path / "plugin.py").exists():
            return direct_path

        # Check categorized structure (speakers/, sources/, etc.)
        try:
            for category in search_dir.iterdir():
                if category.is_dir() and not category.name.startswith(('__', '.')):
                    plugin_path = category / plugin_id
                    if (plugin_path / "plugin.py").exists():
                        return plugin_path
        except (PermissionError, OSError):
            continue

    return None


# ============================================================
# Manifest Loading
# ============================================================

def load_manifest(plugin_dir: Path) -> dict:
    """
    Load or generate a manifest for a plugin.

    If manifest.json exists, load it. Otherwise, try to generate one
    from the plugin class attributes.

    Args:
        plugin_dir: Path to the plugin directory

    Returns:
        Manifest dictionary
    """
    manifest_path = plugin_dir / "manifest.json"

    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception as e:
            logger.warning(f"Failed to read manifest from {manifest_path}: {e}")

    # Generate default manifest
    return {
        "id": plugin_dir.name,
        "name": plugin_dir.name.replace("_", " ").title(),
        "version": "1.0.0",
        "description": "",
        "author": "Unknown",
        "entry_point": "plugin.py",
        "plugin_class": None,  # Will be auto-detected
    }


def save_manifest(plugin_dir: Path, manifest: dict) -> bool:
    """
    Save a manifest to disk.

    Args:
        plugin_dir: Path to the plugin directory
        manifest: Manifest data to save

    Returns:
        True if saved successfully
    """
    try:
        manifest_path = plugin_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save manifest to {plugin_dir}: {e}")
        return False


# ============================================================
# Plugin Loading
# ============================================================

def load_plugin_class(plugin_dir: Path, manifest: dict) -> Optional[Type[BasePlugin]]:
    """
    Dynamically load the plugin class from a plugin directory.

    Args:
        plugin_dir: Path to the plugin directory
        manifest: Plugin manifest

    Returns:
        Plugin class (not instance) if found, None otherwise
    """
    entry_point = manifest.get("entry_point", "plugin.py")
    plugin_file = plugin_dir / entry_point

    if not plugin_file.exists():
        logger.error(f"Plugin entry point not found: {plugin_file}")
        return None

    try:
        # Create a unique module name to avoid conflicts
        module_name = f"sonorium_plugin_{plugin_dir.name}"

        # Load the module dynamically
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            logger.error(f"Failed to create module spec for {plugin_file}")
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find the plugin class
        plugin_class_name = manifest.get("plugin_class")

        if plugin_class_name:
            # Use explicitly specified class
            plugin_class = getattr(module, plugin_class_name, None)
        else:
            # Auto-detect: find first class that inherits from BasePlugin
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin
                ):
                    plugin_class = attr
                    break

        if plugin_class is None:
            logger.error(f"No BasePlugin subclass found in {plugin_file}")
            return None

        logger.debug(f"Loaded plugin class: {plugin_class.__name__} from {plugin_dir.name}")
        return plugin_class

    except Exception as e:
        logger.error(f"Failed to load plugin from {plugin_dir}: {e}")
        return None


def instantiate_plugin(
    plugin_class: Type[BasePlugin],
    plugin_dir: Path,
    settings: dict,
    audio_path: Optional[Path] = None,
) -> Optional[BasePlugin]:
    """
    Create an instance of a plugin.

    Args:
        plugin_class: The plugin class to instantiate
        plugin_dir: Path to the plugin directory
        settings: Plugin settings from config
        audio_path: Path to audio/themes directory

    Returns:
        Plugin instance if successful, None otherwise
    """
    try:
        instance = plugin_class(
            plugin_dir=plugin_dir,
            settings=settings,
            audio_path=audio_path,
        )
        logger.debug(f"Instantiated plugin: {instance.name} v{instance.version}")
        return instance
    except Exception as e:
        logger.error(f"Failed to instantiate plugin {plugin_class.__name__}: {e}")
        return None
