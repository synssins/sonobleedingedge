"""
Sonorium Plugin Base Class

All plugins must inherit from BasePlugin and implement the required methods.

This module provides:
- BasePlugin: Base class for all plugins
- SonoriumPlugin: Alias for BasePlugin (architectural compatibility)
- APIRoute: Data class for plugin API route definitions
- HTTPMethod: Enum for HTTP methods
"""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sonorium.plugins.context import PluginContext, PluginState


class HTTPMethod(Enum):
    """HTTP method types for API route registration."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class APIRoute:
    """
    Defines an API route that a plugin provides.

    Attributes:
        path: Route path (will be prefixed with /api/plugins/{plugin_id})
        method: HTTP method
        handler: Async handler function
        summary: Brief description for documentation
        requires_auth: Whether the route requires authentication
    """
    path: str
    method: HTTPMethod
    handler: Callable
    summary: str = ""
    requires_auth: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize route definition for API responses."""
        return {
            "path": self.path,
            "method": self.method.value,
            "summary": self.summary,
            "requires_auth": self.requires_auth,
        }


class HAEntityType(Enum):
    """Home Assistant entity types for HA addon integration."""
    SWITCH = "switch"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SELECT = "select"
    NUMBER = "number"
    BUTTON = "button"


@dataclass
class HAEntityDefinition:
    """
    Defines a Home Assistant entity that a plugin creates.

    Only relevant when running as HA addon.
    """
    entity_type: HAEntityType
    unique_id: str
    name: str
    icon: str = "mdi:puzzle"
    state_getter: Optional[Callable[[], Any]] = None
    state_setter: Optional[Callable[[Any], None]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize entity definition."""
        return {
            "entity_type": self.entity_type.value,
            "unique_id": self.unique_id,
            "name": self.name,
            "icon": self.icon,
        }


class BasePlugin(ABC):
    """
    Base class that all Sonorium plugins must inherit from.

    Plugins are directory-based with the following structure:
    plugins/
    └── plugin_name/
        ├── manifest.json       # Auto-generated if missing
        └── plugin.py           # Contains the plugin class

    The plugin class should define class attributes:
        id: str - Unique identifier (e.g., "ambient_mixer")
        name: str - Display name (e.g., "Ambient Mixer Importer")
        version: str - Semantic version (e.g., "1.0.0")
        description: str - Brief description
        author: str - Plugin author
    """

    # Override these in your plugin
    id: str = ""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    builtin: bool = False  # True for plugins shipped with Sonorium
    category: str = ""  # Category for UI grouping (speakers, sources, importers, utilities)

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        """
        Initialize the plugin.

        Args:
            plugin_dir: Path to the plugin directory
            settings: Plugin settings from config
            audio_path: Path to audio/themes directory
        """
        self.plugin_dir = plugin_dir
        self.settings = settings
        self.audio_path = audio_path or Path("themes")
        self._enabled = False
        self._builtin = self.builtin  # Can be overridden by manifest

    @property
    def enabled(self) -> bool:
        """Check if plugin is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        """Set plugin enabled state."""
        self._enabled = value

    # Lifecycle hooks

    async def on_load(self) -> None:
        """
        Called when the plugin is loaded.
        Override to perform initialization tasks.
        """
        pass

    async def on_unload(self) -> None:
        """
        Called when the plugin is being unloaded.
        Override to perform cleanup tasks.
        """
        pass

    async def on_enable(self) -> None:
        """
        Called when the plugin is enabled.
        Override to start any background tasks.
        """
        pass

    async def on_disable(self) -> None:
        """
        Called when the plugin is disabled.
        Override to stop any background tasks.
        """
        pass

    # UI Integration

    def get_ui_schema(self) -> dict:
        """
        Return the UI schema for the plugin settings and actions.

        The schema describes what form fields and action buttons to display.

        Returns:
            dict with structure:
            {
                "type": "form",  # or "custom"
                "fields": [
                    {
                        "name": "url",
                        "type": "url",  # string, number, boolean, url, select
                        "label": "URL to import",
                        "required": True,
                        "placeholder": "https://..."
                    }
                ],
                "actions": [
                    {
                        "id": "import",
                        "label": "Import",
                        "primary": True
                    }
                ]
            }
        """
        return {}

    def get_settings_schema(self) -> dict:
        """
        Return the schema for plugin settings that persist across sessions.

        Returns:
            dict mapping setting names to their type info:
            {
                "download_path": {
                    "type": "string",
                    "default": "/media/sonorium",
                    "label": "Download Path"
                },
                "auto_create_metadata": {
                    "type": "boolean",
                    "default": True,
                    "label": "Auto-create metadata"
                }
            }
        """
        return {}

    async def handle_action(self, action: str, data: dict) -> dict:
        """
        Handle an action triggered from the UI.

        Args:
            action: The action ID (e.g., "import")
            data: Form data from the UI

        Returns:
            dict with result:
            {
                "success": True,
                "message": "Import completed successfully",
                "data": {...}  # Optional additional data
            }
        """
        return {"success": False, "message": f"Unknown action: {action}"}

    # Theme Integration Hooks

    async def on_theme_created(self, theme_id: str, theme_path: Path) -> None:
        """
        Called when a new theme is created.

        Args:
            theme_id: The new theme's ID
            theme_path: Path to the theme directory
        """
        pass

    async def on_theme_deleted(self, theme_id: str) -> None:
        """
        Called when a theme is deleted.

        Args:
            theme_id: The deleted theme's ID
        """
        pass

    # Utility methods

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value with fallback to default."""
        return self.settings.get(key, default)

    def update_settings(self, new_settings: dict) -> None:
        """Update plugin settings (call save separately)."""
        self.settings.update(new_settings)

    def to_dict(self) -> dict:
        """Serialize plugin info to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "enabled": self.enabled,
            "builtin": self._builtin,
            "settings": self.settings,
            "ui_schema": self.get_ui_schema(),
            "settings_schema": self.get_settings_schema(),
            "has_api_routes": len(self.get_api_routes()) > 0,
            "has_ha_entities": len(self.get_ha_entities()) > 0,
        }

    # API Route Registration (Stage 2 feature)

    def get_api_routes(self) -> List[APIRoute]:
        """
        Return API routes this plugin provides.

        Override this method to register custom HTTP endpoints for your plugin.
        Routes are automatically prefixed with /api/plugins/{plugin_id}/

        Returns:
            List of APIRoute definitions

        Example:
            def get_api_routes(self):
                return [
                    APIRoute(
                        path="/export",
                        method=HTTPMethod.POST,
                        handler=self.handle_export,
                        summary="Export theme pack",
                    ),
                ]
        """
        return []

    # Home Assistant Entity Registration (Stage 3 feature)

    def get_ha_entities(self) -> List[HAEntityDefinition]:
        """
        Return Home Assistant entities this plugin creates.

        Only called when running as HA addon. Override to create
        switches, sensors, or other HA entities for your plugin.

        Returns:
            List of HAEntityDefinition objects
        """
        return []

    # Actions for automation (callable by other plugins or automations)

    def get_actions(self) -> Dict[str, Callable]:
        """
        Return callable actions for automation/other plugins.

        Actions can be invoked by other plugins or automation systems
        to trigger plugin functionality.

        Returns:
            Dict mapping action names to async handler functions
        """
        return {}


# Alias for architectural compatibility with the plugin spec
SonoriumPlugin = BasePlugin
