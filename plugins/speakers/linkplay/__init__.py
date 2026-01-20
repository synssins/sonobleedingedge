"""
Linkplay/Arylic Speaker Plugin

TRUE PLUGIN - Deleting this folder removes Linkplay support entirely.
Core code has ZERO references to Linkplay.
"""

from sonorium.plugins.speakers.linkplay.plugin import LinkplayPlugin, Plugin

__all__ = ["LinkplayPlugin", "Plugin"]
