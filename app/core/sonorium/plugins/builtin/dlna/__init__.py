"""
DLNA/UPnP Speaker Plugin

TRUE PLUGIN - Deleting this folder removes DLNA support entirely.
Core code has ZERO references to DLNA.
"""

from sonorium.plugins.builtin.dlna.plugin import DLNAPlugin, Plugin

__all__ = ["DLNAPlugin", "Plugin"]
