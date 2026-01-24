"""
Sonorium Plugin System.

Provides base classes, interfaces, and management for speaker and source plugins.
This is the FRAMEWORK that enables plugins - actual plugins live in the external
plugins/ folder and are loaded at runtime.
"""

import asyncio
import importlib
import importlib.util
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Speaker

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Types and Manifest
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Base Plugin Classes
# ─────────────────────────────────────────────────────────────────────────────

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


class SpeakerPlugin(BasePlugin):
    """
    Base class for speaker protocol plugins.

    Speaker plugins discover and control network speakers using
    specific protocols (Sonos, Chromecast, AirPlay, etc.).
    """

    @abstractmethod
    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
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


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Manager
# ─────────────────────────────────────────────────────────────────────────────

class PluginManager:
    """
    Manages plugin lifecycle and provides access to plugin functionality.

    Usage:
        manager = PluginManager()
        await manager.load_plugins("/path/to/plugins")

        # Discover speakers using all plugins
        speakers = await manager.discover_speakers()

        # Play to a speaker
        await manager.play_url(speaker_id, url)
    """

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._speaker_plugins: dict[str, SpeakerPlugin] = {}
        self._source_plugins: dict[str, SourcePlugin] = {}
        self._speaker_to_plugin: dict[str, str] = {}  # speaker_id -> plugin_id

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    @property
    def speaker_plugins(self) -> dict[str, SpeakerPlugin]:
        """Get all speaker plugins."""
        return self._speaker_plugins.copy()

    # ─────────────────────────────────────────────────────────────
    # Plugin Loading
    # ─────────────────────────────────────────────────────────────

    async def load_plugins(self, plugins_dir: Path) -> int:
        """
        Load all plugins from a directory.

        Expected structure:
            plugins_dir/
                speakers/
                    sonos/
                        __init__.py  (or plugin.py)
                    chromecast/
                        __init__.py

        Args:
            plugins_dir: Path to plugins directory

        Returns:
            Number of plugins loaded
        """
        count = 0
        plugins_dir = Path(plugins_dir)

        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return 0

        # Load speaker plugins
        speakers_dir = plugins_dir / "speakers"
        if speakers_dir.exists():
            for plugin_dir in speakers_dir.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                    if await self._load_plugin(plugin_dir, PluginType.SPEAKER):
                        count += 1

        # Load source plugins
        sources_dir = plugins_dir / "sources"
        if sources_dir.exists():
            for plugin_dir in sources_dir.iterdir():
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                    if await self._load_plugin(plugin_dir, PluginType.SOURCE):
                        count += 1

        logger.info(f"Loaded {count} plugins")
        return count

    async def _load_plugin(self, plugin_dir: Path, expected_type: PluginType) -> bool:
        """Load a single plugin from directory."""
        plugin_id = plugin_dir.name

        try:
            # Find plugin module
            plugin_file = plugin_dir / "plugin.py"
            if not plugin_file.exists():
                plugin_file = plugin_dir / "__init__.py"
            if not plugin_file.exists():
                logger.warning(f"No plugin file found in {plugin_dir}")
                return False

            # Load module
            spec = importlib.util.spec_from_file_location(
                f"sonorium_plugins.{plugin_id}",
                plugin_file
            )
            if spec is None or spec.loader is None:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BasePlugin) and
                    attr not in (BasePlugin, SpeakerPlugin, SourcePlugin)):
                    plugin_class = attr
                    break

            if plugin_class is None:
                logger.warning(f"No plugin class found in {plugin_dir}")
                return False

            # Instantiate plugin
            plugin = plugin_class()

            # Verify manifest
            manifest = plugin.manifest
            if manifest.type != expected_type:
                logger.warning(f"Plugin {plugin_id} type mismatch: expected {expected_type}, got {manifest.type}")

            # Initialize plugin
            if not await plugin.initialize():
                logger.error(f"Plugin {plugin_id} initialization failed")
                return False

            # Register plugin
            self._plugins[plugin_id] = plugin

            if isinstance(plugin, SpeakerPlugin):
                self._speaker_plugins[plugin_id] = plugin
                logger.info(f"Loaded speaker plugin: {manifest.name} ({plugin_id})")
            elif isinstance(plugin, SourcePlugin):
                self._source_plugins[plugin_id] = plugin
                logger.info(f"Loaded source plugin: {manifest.name} ({plugin_id})")

            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {e}")
            return False

    def register_plugin(self, plugin: BasePlugin) -> None:
        """Register a plugin instance directly (for built-in plugins)."""
        plugin_id = plugin.plugin_id
        self._plugins[plugin_id] = plugin

        if isinstance(plugin, SpeakerPlugin):
            self._speaker_plugins[plugin_id] = plugin
        elif isinstance(plugin, SourcePlugin):
            self._source_plugins[plugin_id] = plugin

    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            return False

        try:
            await plugin.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down plugin {plugin_id}: {e}")

        del self._plugins[plugin_id]
        self._speaker_plugins.pop(plugin_id, None)
        self._source_plugins.pop(plugin_id, None)

        # Remove speaker mappings
        self._speaker_to_plugin = {
            sid: pid for sid, pid in self._speaker_to_plugin.items()
            if pid != plugin_id
        }

        logger.info(f"Unloaded plugin: {plugin_id}")
        return True

    async def shutdown(self) -> None:
        """Shutdown all plugins."""
        for plugin_id in list(self._plugins.keys()):
            await self.unload_plugin(plugin_id)

    # ─────────────────────────────────────────────────────────────
    # Speaker Discovery
    # ─────────────────────────────────────────────────────────────

    async def discover_speakers(self, timeout: float = 10.0) -> list:
        """
        Discover speakers using all enabled speaker plugins.

        Args:
            timeout: Discovery timeout per plugin

        Returns:
            List of discovered speakers
        """
        from .models import Speaker, SpeakerProtocol, DiscoverySource
        from .core.state import get_state_manager

        speakers = []
        state_manager = get_state_manager()

        # Get enabled protocols from settings
        enabled_protocols = state_manager.get_settings().discovery.enabled_protocols

        # Run discovery on all enabled plugins
        tasks = []
        for plugin_id, plugin in self._speaker_plugins.items():
            if plugin_id in enabled_protocols:
                tasks.append(self._discover_with_plugin(plugin_id, plugin, timeout))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Discovery error: {result}")
            elif isinstance(result, list):
                speakers.extend(result)

        logger.info(f"Discovered {len(speakers)} speakers total")
        return speakers

    async def _discover_with_plugin(
        self,
        plugin_id: str,
        plugin: SpeakerPlugin,
        timeout: float
    ) -> list:
        """Run discovery with a single plugin."""
        from .models import Speaker, SpeakerProtocol, DiscoverySource
        from .core.state import get_state_manager

        speakers = []

        try:
            discovered = await plugin.discover(timeout=timeout)

            # Convert to Speaker models
            protocol = SpeakerProtocol(plugin_id) if plugin_id in [e.value for e in SpeakerProtocol] else SpeakerProtocol.UNKNOWN

            for d in discovered:
                speaker = Speaker(
                    id=d.id,
                    name=d.name,
                    protocol=protocol,
                    host=d.host,
                    port=d.port,
                    model=d.model,
                    manufacturer=d.manufacturer,
                    discovery_sources=[DiscoverySource.DIRECT],
                )

                # Track which plugin handles this speaker
                self._speaker_to_plugin[d.id] = plugin_id

                speakers.append(speaker)

            logger.debug(f"Plugin {plugin_id} found {len(discovered)} speakers")

        except Exception as e:
            logger.error(f"Discovery failed for plugin {plugin_id}: {e}")

        return speakers

    # ─────────────────────────────────────────────────────────────
    # Speaker Control
    # ─────────────────────────────────────────────────────────────

    def _get_plugin_for_speaker(self, speaker_id: str) -> Optional[SpeakerPlugin]:
        """Get the plugin that handles a speaker."""
        plugin_id = self._speaker_to_plugin.get(speaker_id)
        if plugin_id:
            return self._speaker_plugins.get(plugin_id)

        # Try to determine from speaker data
        from .core.state import get_state_manager
        state_manager = get_state_manager()
        speaker = state_manager.state.speakers.get(speaker_id)
        if speaker:
            plugin_id = speaker.protocol.value
            return self._speaker_plugins.get(plugin_id)

        return None

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """
        Play URL on a speaker.

        Args:
            speaker_id: Speaker identifier
            url: Audio stream URL
            **kwargs: Additional options

        Returns:
            True if playback started
        """
        plugin = self._get_plugin_for_speaker(speaker_id)
        if plugin is None:
            logger.error(f"No plugin found for speaker {speaker_id}")
            return False

        try:
            return await plugin.play_url(speaker_id, url, **kwargs)
        except Exception as e:
            logger.error(f"Play failed for speaker {speaker_id}: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """
        Stop playback on a speaker.

        Args:
            speaker_id: Speaker identifier

        Returns:
            True if stop succeeded
        """
        plugin = self._get_plugin_for_speaker(speaker_id)
        if plugin is None:
            logger.error(f"No plugin found for speaker {speaker_id}")
            return False

        try:
            return await plugin.stop(speaker_id)
        except Exception as e:
            logger.error(f"Stop failed for speaker {speaker_id}: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """
        Set speaker volume.

        Args:
            speaker_id: Speaker identifier
            volume: Volume level (0.0 - 1.0)

        Returns:
            True if volume was set
        """
        plugin = self._get_plugin_for_speaker(speaker_id)
        if plugin is None:
            return False

        try:
            return await plugin.set_volume(speaker_id, volume)
        except Exception as e:
            logger.error(f"Set volume failed for speaker {speaker_id}: {e}")
            return False

    async def stop_all(self) -> int:
        """
        Stop playback on all speakers.

        Returns:
            Number of speakers stopped
        """
        count = 0
        for plugin in self._speaker_plugins.values():
            try:
                count += await plugin.stop_all()
            except Exception as e:
                logger.error(f"Stop all failed for plugin: {e}")
        return count


# ─────────────────────────────────────────────────────────────────────────────
# Global Plugin Manager
# ─────────────────────────────────────────────────────────────────────────────

_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


async def init_plugin_manager(plugins_dir: Path) -> PluginManager:
    """Initialize the global plugin manager and load plugins."""
    manager = get_plugin_manager()
    await manager.load_plugins(plugins_dir)
    return manager


# ─────────────────────────────────────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Types
    "PluginType",
    "PluginManifest",
    "DiscoveredSpeaker",
    # Base classes
    "BasePlugin",
    "SpeakerPlugin",
    "SourcePlugin",
    # Manager
    "PluginManager",
    "get_plugin_manager",
    "init_plugin_manager",
]
