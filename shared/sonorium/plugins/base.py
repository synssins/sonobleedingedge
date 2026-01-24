"""
Plugin base classes.

Defines the interfaces that all plugins must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class PluginType(str, Enum):
    """Types of plugins."""
    SPEAKER = "speaker"         # Speaker protocol plugin
    SOURCE = "source"           # Audio source plugin
    EFFECT = "effect"           # Audio effect plugin


@dataclass
class PluginManifest:
    """
    Plugin metadata manifest.

    Every plugin must provide this information.
    """
    id: str                             # Unique identifier (e.g., "sonos")
    name: str                           # Display name (e.g., "Sonos")
    type: PluginType                    # Plugin type
    version: str                        # Plugin version
    description: str = ""               # Plugin description
    author: str = ""                    # Plugin author
    dependencies: list[str] = field(default_factory=list)  # Required Python packages

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
        }


class BasePlugin(ABC):
    """
    Base class for all Sonorium plugins.

    All plugins must inherit from this class and implement the required methods.
    """

    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return plugin manifest with metadata."""
        pass

    @property
    def plugin_id(self) -> str:
        """Plugin unique identifier."""
        return self.manifest.id

    @property
    def plugin_name(self) -> str:
        """Plugin display name."""
        return self.manifest.name

    async def initialize(self) -> bool:
        """
        Initialize the plugin.

        Called when plugin is loaded. Override to perform setup.
        Returns True if initialization succeeded.
        """
        return True

    async def shutdown(self) -> None:
        """
        Shutdown the plugin.

        Called when plugin is unloaded. Override to perform cleanup.
        """
        pass

    def get_config(self) -> dict:
        """Get plugin configuration."""
        return {}

    def set_config(self, config: dict) -> None:
        """Set plugin configuration."""
        pass


class SpeakerPlugin(BasePlugin):
    """
    Base class for speaker protocol plugins.

    Speaker plugins discover and control network speakers using
    specific protocols (Sonos, Chromecast, AirPlay, etc.).
    """

    @abstractmethod
    async def discover(self, timeout: float = 10.0) -> list["DiscoveredSpeaker"]:
        """
        Discover speakers on the network.

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered speakers
        """
        pass

    @abstractmethod
    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """
        Stream audio URL to a speaker.

        Args:
            speaker_id: Speaker identifier
            url: Audio stream URL
            **kwargs: Protocol-specific options

        Returns:
            True if playback started successfully
        """
        pass

    @abstractmethod
    async def stop(self, speaker_id: str) -> bool:
        """
        Stop playback on a speaker.

        Args:
            speaker_id: Speaker identifier

        Returns:
            True if stop succeeded
        """
        pass

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """
        Set speaker volume.

        Args:
            speaker_id: Speaker identifier
            volume: Volume level (0.0 - 1.0)

        Returns:
            True if volume was set (default returns False for unsupported)
        """
        return False

    async def get_state(self, speaker_id: str) -> Optional[dict]:
        """
        Get current state of a speaker.

        Args:
            speaker_id: Speaker identifier

        Returns:
            State dict or None if unavailable
        """
        return None

    async def stop_all(self) -> int:
        """
        Stop playback on all speakers managed by this plugin.

        Returns:
            Number of speakers stopped
        """
        return 0


@dataclass
class DiscoveredSpeaker:
    """
    A speaker discovered by a plugin.

    Plugins return this from discover() and it gets converted
    to a full Speaker model.
    """
    id: str                             # Unique identifier
    name: str                           # Display name
    host: str                           # IP address or hostname
    port: Optional[int] = None          # Port (protocol-specific)
    model: Optional[str] = None         # Device model
    manufacturer: Optional[str] = None  # Device manufacturer
    unique_id: Optional[str] = None     # MAC address or other unique ID
    extra: dict = field(default_factory=dict)  # Protocol-specific data

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "unique_id": self.unique_id,
            "extra": self.extra,
        }


class SourcePlugin(BasePlugin):
    """
    Base class for audio source plugins.

    Source plugins provide audio content (themes, streams, etc.).
    """

    @abstractmethod
    async def get_sources(self) -> list[dict]:
        """
        Get available audio sources.

        Returns:
            List of source definitions
        """
        pass

    @abstractmethod
    async def get_stream_url(self, source_id: str) -> Optional[str]:
        """
        Get stream URL for a source.

        Args:
            source_id: Source identifier

        Returns:
            Stream URL or None if unavailable
        """
        pass
