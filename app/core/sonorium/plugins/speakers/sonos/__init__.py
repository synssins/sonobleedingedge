"""
Sonos Speaker Plugin

TRUE PLUGIN - Deleting this folder removes Sonos support entirely.
Core code has ZERO references to Sonos.
"""

from sonorium.plugins.speakers.sonos.plugin import SonosPlugin, Plugin

__all__ = ["SonosPlugin", "Plugin"]
