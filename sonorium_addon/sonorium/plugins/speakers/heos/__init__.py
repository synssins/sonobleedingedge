"""
HEOS Speaker Plugin (Denon/Marantz)

TRUE PLUGIN - Deleting this folder removes HEOS support entirely.
Core code has ZERO references to HEOS.
"""

from sonorium.plugins.speakers.heos.plugin import HEOSPlugin, Plugin

__all__ = ["HEOSPlugin", "Plugin"]
