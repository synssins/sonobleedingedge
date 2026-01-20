"""
AirPlay Speaker Plugin

TRUE PLUGIN - Deleting this folder removes AirPlay support entirely.
Core code has ZERO references to AirPlay.
"""

from sonorium.plugins.builtin.airplay.plugin import AirPlayPlugin, Plugin

__all__ = ["AirPlayPlugin", "Plugin"]
