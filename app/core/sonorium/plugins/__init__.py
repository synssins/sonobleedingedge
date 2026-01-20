"""
Sonorium Plugin System

This module provides the plugin architecture for extending Sonorium functionality.
It follows the modular architecture defined in FOUNDATIONAL_CHANGES.md.

Shared Code: This file is managed in shared/plugins/ and synced to deployment targets.

Module Interface:
    - __feature_name__: "Plugin System"
    - __required__: False (optional module - app runs without it)
    - init(app_context): Initialize the plugin system
    - shutdown(): Cleanup and unload all plugins
    - health_check(): Return system health status
    - is_available(): Check if module can be loaded

Exports:
    - BasePlugin: Base class for all plugins
    - SonoriumPlugin: Alias for BasePlugin
    - PluginManager: Manages plugin lifecycle
    - PluginContext: Context injected into plugins
    - PluginState: Plugin lifecycle states
    - EventBus: Event-based plugin communication
    - EventTypes: Standard event type constants
    - Event: Event data class
    - APIRoute: API route definition
    - HTTPMethod: HTTP method enum
    - HAEntityDefinition: HA entity definition
    - HAEntityType: HA entity types
    - SpeakerPlugin: Base class for speaker plugins
    - NetworkSpeaker: Network speaker data class
    - SpeakerState: Speaker state enum
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

# Base classes
from sonorium.plugins.base import (
    BasePlugin,
    SonoriumPlugin,
    APIRoute,
    HTTPMethod,
    HAEntityDefinition,
    HAEntityType,
)

# Context and state
from sonorium.plugins.context import (
    PluginContext,
    PluginState,
    Platform,
    detect_platform,
    get_plugins_directory,
    get_data_directory,
    create_plugin_context,
)

# Event system
from sonorium.plugins.events import (
    EventBus,
    EventTypes,
    Event,
    Subscription,
    get_event_bus,
    reset_event_bus,
)

# Manager
from sonorium.plugins.manager import PluginManager

# Speaker plugins
from sonorium.plugins.speaker_base import (
    SpeakerPlugin,
    NetworkSpeaker,
    SpeakerState,
)

logger = logging.getLogger("sonorium.plugins")

# =============================================================================
# Module Metadata (per FOUNDATIONAL_CHANGES.md)
# =============================================================================

__feature_name__ = "Plugin System"
__required__ = False  # App runs without plugins
__depends_on__ = []   # No dependencies on other optional modules

# =============================================================================
# Module State
# =============================================================================

_plugin_manager: Optional[PluginManager] = None
_event_bus: Optional[EventBus] = None
_initialized: bool = False

# =============================================================================
# Module Interface Functions
# =============================================================================


async def init(app_context: Any) -> bool:
    """
    Initialize the plugin system.

    Args:
        app_context: Application context containing config and services

    Returns:
        True if initialized successfully, False otherwise
    """
    global _plugin_manager, _event_bus, _initialized

    if _initialized:
        logger.warning("Plugin system already initialized")
        return True

    try:
        logger.info("Initializing plugin system...")

        # Get or create the event bus
        _event_bus = get_event_bus()

        # Create plugin manager
        # app_context is expected to have:
        # - config: AppConfig with plugin_settings, enabled_plugins, audio_path
        # - plugins_dir: Optional custom plugins directory
        _plugin_manager = PluginManager(
            config=app_context.config,
            plugins_dir=getattr(app_context, 'plugins_dir', None),
            audio_path=getattr(app_context, 'audio_path', None),
        )

        # Initialize plugins
        await _plugin_manager.initialize()

        # Emit startup event
        await _event_bus.emit(
            EventTypes.SYSTEM_STARTUP,
            {"feature": "plugins", "plugin_count": len(_plugin_manager.plugins)},
        )

        _initialized = True
        logger.info(
            f"Plugin system initialized with {len(_plugin_manager.plugins)} plugin(s)"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize plugin system: {e}")
        return False


async def shutdown() -> None:
    """
    Shutdown the plugin system and unload all plugins.
    """
    global _plugin_manager, _event_bus, _initialized

    if not _initialized:
        return

    logger.info("Shutting down plugin system...")

    try:
        if _event_bus:
            await _event_bus.emit(
                EventTypes.SYSTEM_SHUTDOWN,
                {"feature": "plugins"},
            )

        if _plugin_manager:
            # Disable and unload all plugins
            for plugin_id in list(_plugin_manager.plugins.keys()):
                try:
                    await _plugin_manager.disable_plugin(plugin_id)
                    await _plugin_manager._unload_plugin(plugin_id)
                except Exception as e:
                    logger.error(f"Error unloading plugin {plugin_id}: {e}")

    except Exception as e:
        logger.error(f"Error during plugin system shutdown: {e}")
    finally:
        _plugin_manager = None
        _initialized = False
        reset_event_bus()
        _event_bus = None
        logger.info("Plugin system shutdown complete")


def health_check() -> Dict[str, Any]:
    """
    Return health status of the plugin system.

    Returns:
        Dict with health information:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "initialized": bool,
            "plugin_count": int,
            "enabled_plugins": list[str],
            "event_subscriptions": int,
        }
    """
    if not _initialized:
        return {
            "status": "unhealthy",
            "initialized": False,
            "plugin_count": 0,
            "enabled_plugins": [],
            "event_subscriptions": 0,
            "message": "Plugin system not initialized",
        }

    enabled_plugins = []
    plugin_count = 0

    if _plugin_manager:
        plugin_count = len(_plugin_manager.plugins)
        enabled_plugins = [
            p.id for p in _plugin_manager.plugins.values() if p.enabled
        ]

    event_subs = _event_bus.get_subscription_count() if _event_bus else 0

    # Determine status
    status = "healthy"
    if plugin_count == 0:
        status = "degraded"  # No plugins loaded

    return {
        "status": status,
        "initialized": True,
        "plugin_count": plugin_count,
        "enabled_plugins": enabled_plugins,
        "event_subscriptions": event_subs,
    }


def is_available() -> bool:
    """
    Check if the plugin system module can be loaded.

    This always returns True for this module since there are no
    external dependencies that could prevent loading.

    Returns:
        True if module can be used
    """
    return True


# =============================================================================
# Convenience Functions
# =============================================================================


def get_plugin_manager() -> Optional[PluginManager]:
    """Get the current PluginManager instance."""
    return _plugin_manager


def is_initialized() -> bool:
    """Check if the plugin system has been initialized."""
    return _initialized


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Module interface
    '__feature_name__',
    '__required__',
    '__depends_on__',
    'init',
    'shutdown',
    'health_check',
    'is_available',

    # Convenience functions
    'get_plugin_manager',
    'get_event_bus',
    'is_initialized',

    # Base classes
    'BasePlugin',
    'SonoriumPlugin',
    'APIRoute',
    'HTTPMethod',
    'HAEntityDefinition',
    'HAEntityType',

    # Context and state
    'PluginContext',
    'PluginState',
    'Platform',
    'detect_platform',
    'get_plugins_directory',
    'get_data_directory',
    'create_plugin_context',

    # Event system
    'EventBus',
    'EventTypes',
    'Event',
    'Subscription',
    'reset_event_bus',

    # Manager
    'PluginManager',

    # Speaker plugins
    'SpeakerPlugin',
    'NetworkSpeaker',
    'SpeakerState',
]
