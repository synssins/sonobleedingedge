"""
Sonorium plugin system.

Provides interfaces and management for speaker and source plugins.
"""

from .base import (
    BasePlugin,
    SpeakerPlugin,
    SourcePlugin,
    PluginType,
    PluginManifest,
    DiscoveredSpeaker,
)

from .manager import (
    PluginManager,
    get_plugin_manager,
    init_plugin_manager,
)

__all__ = [
    # Base classes
    "BasePlugin",
    "SpeakerPlugin",
    "SourcePlugin",
    "PluginType",
    "PluginManifest",
    "DiscoveredSpeaker",
    # Manager
    "PluginManager",
    "get_plugin_manager",
    "init_plugin_manager",
]
