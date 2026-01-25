"""
Speaker Coordinator

Coordinates network speaker discovery and control across all speaker plugins.
Acts as the bridge between the StreamingEngine and individual speaker plugins.

CORE CODE: This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Callable, Any

from ..plugins.speaker_base import SpeakerPlugin, NetworkSpeaker, SpeakerState
from ..models.speaker_model import UnifiedSpeaker, DiscoverySource, ControlMethod
from ..models.speaker_dedup import SpeakerDeduplicator

logger = logging.getLogger(__name__)


class SpeakerCoordinator:
    """
    Coordinates speaker discovery and control across all plugins.

    This is the central point for:
    - Aggregating speakers from all enabled speaker plugins
    - Deduplicating speakers found by multiple sources
    - Routing play/stop/volume commands to the correct plugin
    - Persisting speaker state

    The StreamingEngine uses this coordinator via set_plugin_manager().
    """

    def __init__(
        self,
        plugin_manager=None,
        data_dir: Optional[Path] = None,
    ):
        """
        Initialize the speaker coordinator.

        Args:
            plugin_manager: PluginManager instance for accessing speaker plugins
            data_dir: Directory for persisting speaker data
        """
        self._plugin_manager = plugin_manager
        self._data_dir = data_dir

        # Speaker deduplication
        self._deduplicator = SpeakerDeduplicator()

        # Raw speakers from plugins (before dedup)
        self._raw_speakers: dict[str, NetworkSpeaker] = {}

        # Map from speaker_id to plugin_id for routing commands
        self._speaker_to_plugin: dict[str, str] = {}

        # Enabled speakers (user has opted-in)
        self._enabled_speaker_ids: set[str] = set()

        # Discovery state
        self._discovering = False
        self._last_discovery = 0.0

        # State change callbacks
        self._on_speaker_change: list[Callable[[UnifiedSpeaker], None]] = []

        # Load persisted speaker state
        if data_dir:
            self._speakers_file = data_dir / "speakers.json"
            self._load_speaker_state()
        else:
            self._speakers_file = None

    def set_plugin_manager(self, manager) -> None:
        """Set the plugin manager for accessing speaker plugins."""
        self._plugin_manager = manager

    def set_data_dir(self, data_dir: Path) -> None:
        """Set the data directory for persistence."""
        self._data_dir = data_dir
        self._speakers_file = data_dir / "speakers.json"
        self._load_speaker_state()

    # ─────────────────────────────────────────────────────────────────────
    # Discovery
    # ─────────────────────────────────────────────────────────────────────

    async def discover_all(self, timeout: float = 15.0) -> list[UnifiedSpeaker]:
        """
        Discover speakers from all enabled speaker plugins.

        Args:
            timeout: Maximum time for discovery

        Returns:
            List of unified (deduplicated) speakers
        """
        if not self._plugin_manager:
            logger.warning("Plugin manager not set - cannot discover speakers")
            return []

        if self._discovering:
            logger.debug("Discovery already in progress")
            return self.get_speakers()

        self._discovering = True
        self._deduplicator.clear()
        self._raw_speakers.clear()
        self._speaker_to_plugin.clear()

        try:
            # Get all speaker plugins
            speaker_plugins = self._plugin_manager.get_plugins_by_type("speaker")
            logger.info(f"Discovering speakers from {len(speaker_plugins)} plugins...")

            # Run discovery on all plugins concurrently
            tasks = []
            plugin_map = {}  # task -> plugin_id

            for plugin in speaker_plugins:
                if not plugin.enabled:
                    logger.debug(f"Skipping disabled plugin: {plugin.id}")
                    continue

                task = asyncio.create_task(
                    asyncio.wait_for(
                        plugin.discover_speakers(),
                        timeout=timeout
                    )
                )
                tasks.append(task)
                plugin_map[id(task)] = plugin.id

            if not tasks:
                logger.warning("No enabled speaker plugins found")
                return []

            # Wait for all discoveries
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results from each plugin
            for i, (task, result) in enumerate(zip(tasks, results)):
                plugin_id = plugin_map.get(id(task), "unknown")

                if isinstance(result, Exception):
                    logger.error(f"Plugin {plugin_id} discovery failed: {result}")
                    continue

                if not isinstance(result, list):
                    logger.warning(f"Plugin {plugin_id} returned invalid result: {type(result)}")
                    continue

                logger.info(f"Plugin {plugin_id} found {len(result)} speakers")

                # Process each discovered speaker
                for network_speaker in result:
                    try:
                        self._process_discovered_speaker(network_speaker, plugin_id)
                    except Exception as e:
                        logger.error(f"Error processing speaker: {e}")

            # Log discovery summary
            unified = self._deduplicator.get_speakers()
            logger.info(
                f"Discovery complete: {len(self._raw_speakers)} raw speakers -> "
                f"{len(unified)} unified speakers"
            )

            # Restore enabled state from saved data
            self._restore_enabled_state()

            import time
            self._last_discovery = time.time()

            return unified

        finally:
            self._discovering = False

    def _process_discovered_speaker(
        self,
        network_speaker: NetworkSpeaker,
        plugin_id: str
    ) -> None:
        """
        Process a speaker discovered by a plugin.

        Converts to UnifiedSpeaker and adds to deduplicator.

        Args:
            network_speaker: Speaker from plugin
            plugin_id: Plugin that discovered it
        """
        # Store raw speaker
        self._raw_speakers[network_speaker.id] = network_speaker

        # Map speaker_id to plugin for routing
        self._speaker_to_plugin[network_speaker.id] = plugin_id

        # Convert to UnifiedSpeaker
        # Map plugin_id to DiscoverySource (plugin id often matches source name)
        source_map = {
            "sonos": DiscoverySource.SONOS,
            "chromecast": DiscoverySource.CHROMECAST,
            "airplay": DiscoverySource.AIRPLAY,
            "dlna": DiscoverySource.DLNA,
            "linkplay": DiscoverySource.LINKPLAY,
            "heos": DiscoverySource.HEOS,
        }
        source = source_map.get(plugin_id, plugin_id)

        unified = UnifiedSpeaker(
            canonical_id="",  # Will be assigned by deduplicator
            name=network_speaker.name,
            ip_address=network_speaker.ip_address,
            mac_address=network_speaker.extra.get("mac"),
            uuid=network_speaker.extra.get("uuid") or network_speaker.extra.get("uid"),
            found_by={source if isinstance(source, str) else source.value},
            preferred_control=ControlMethod.DIRECT,
            protocol=plugin_id,
            model=network_speaker.model,
            manufacturer=network_speaker.manufacturer,
            capabilities=network_speaker.capabilities.copy(),
            extra=network_speaker.extra.copy(),
            original_ids={network_speaker.id},
        )

        # Add to deduplicator (may merge with existing)
        self._deduplicator.add_speaker(unified)

    def _restore_enabled_state(self) -> None:
        """Restore enabled state from persisted data."""
        for speaker in self._deduplicator.get_speakers():
            if speaker.canonical_id in self._enabled_speaker_ids:
                # Still enabled from previous session
                pass
            else:
                # Check if any original_id was enabled
                for orig_id in speaker.original_ids:
                    if orig_id in self._enabled_speaker_ids:
                        self._enabled_speaker_ids.add(speaker.canonical_id)
                        break

    # ─────────────────────────────────────────────────────────────────────
    # Speaker Access
    # ─────────────────────────────────────────────────────────────────────

    def get_speakers(self) -> list[UnifiedSpeaker]:
        """Get all unified (deduplicated) speakers."""
        return self._deduplicator.get_speakers()

    def get_speaker(self, speaker_id: str) -> Optional[UnifiedSpeaker]:
        """
        Get a speaker by ID.

        Accepts either canonical_id or original speaker_id.

        Args:
            speaker_id: Speaker identifier

        Returns:
            UnifiedSpeaker or None
        """
        # Try canonical_id first
        speaker = self._deduplicator.get_speaker(speaker_id)
        if speaker:
            return speaker

        # Try to find by original_id
        for spk in self._deduplicator.get_speakers():
            if speaker_id in spk.original_ids:
                return spk

        return None

    def get_enabled_speakers(self) -> list[UnifiedSpeaker]:
        """Get all enabled speakers."""
        return [
            s for s in self._deduplicator.get_speakers()
            if s.canonical_id in self._enabled_speaker_ids
        ]

    def is_speaker_enabled(self, speaker_id: str) -> bool:
        """Check if a speaker is enabled."""
        speaker = self.get_speaker(speaker_id)
        if speaker:
            return speaker.canonical_id in self._enabled_speaker_ids
        return speaker_id in self._enabled_speaker_ids

    def enable_speaker(self, speaker_id: str) -> bool:
        """
        Enable a speaker for use.

        Args:
            speaker_id: Speaker to enable (canonical_id or original_id)

        Returns:
            True if speaker was enabled
        """
        speaker = self.get_speaker(speaker_id)
        if speaker:
            self._enabled_speaker_ids.add(speaker.canonical_id)
            self._save_speaker_state()
            logger.info(f"Enabled speaker: {speaker.name} ({speaker.canonical_id})")
            return True

        # Unknown speaker - enable by raw ID
        self._enabled_speaker_ids.add(speaker_id)
        self._save_speaker_state()
        return True

    def disable_speaker(self, speaker_id: str) -> bool:
        """
        Disable a speaker.

        Args:
            speaker_id: Speaker to disable

        Returns:
            True if speaker was disabled
        """
        speaker = self.get_speaker(speaker_id)
        if speaker:
            self._enabled_speaker_ids.discard(speaker.canonical_id)
            self._save_speaker_state()
            logger.info(f"Disabled speaker: {speaker.name} ({speaker.canonical_id})")
            return True

        self._enabled_speaker_ids.discard(speaker_id)
        self._save_speaker_state()
        return True

    # ─────────────────────────────────────────────────────────────────────
    # Playback Control (interface for StreamingEngine)
    # ─────────────────────────────────────────────────────────────────────

    async def play_url(
        self,
        speaker_id: str,
        url: str,
        volume: Optional[float] = None
    ) -> bool:
        """
        Play a URL on a speaker.

        Routes the command to the appropriate plugin based on speaker_id.

        Args:
            speaker_id: Target speaker (canonical_id or original_id)
            url: Audio stream URL
            volume: Optional volume level (0.0-1.0)

        Returns:
            True if playback started
        """
        plugin, original_id = self._get_plugin_for_speaker(speaker_id)
        if not plugin:
            logger.error(f"No plugin found for speaker: {speaker_id}")
            return False

        logger.info(f"Playing {url} on {speaker_id} via plugin {plugin.id}")

        try:
            # Set volume first if specified
            if volume is not None:
                await plugin.set_volume(original_id, volume)

            # Start playback
            success = await plugin.play_url(original_id, url)

            if success:
                logger.info(f"Playback started on {speaker_id}")
            else:
                logger.warning(f"Failed to start playback on {speaker_id}")

            return success

        except Exception as e:
            logger.error(f"Error playing on {speaker_id}: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """
        Stop playback on a speaker.

        Args:
            speaker_id: Target speaker

        Returns:
            True if stopped
        """
        plugin, original_id = self._get_plugin_for_speaker(speaker_id)
        if not plugin:
            logger.warning(f"No plugin found for speaker: {speaker_id}")
            return False

        try:
            success = await plugin.stop(original_id)
            if success:
                logger.debug(f"Stopped playback on {speaker_id}")
            return success
        except Exception as e:
            logger.error(f"Error stopping {speaker_id}: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """
        Set volume on a speaker.

        Args:
            speaker_id: Target speaker
            level: Volume level (0.0-1.0)

        Returns:
            True if volume set
        """
        plugin, original_id = self._get_plugin_for_speaker(speaker_id)
        if not plugin:
            logger.warning(f"No plugin found for speaker: {speaker_id}")
            return False

        try:
            level = max(0.0, min(1.0, level))
            success = await plugin.set_volume(original_id, level)
            if success:
                logger.debug(f"Set volume to {level:.0%} on {speaker_id}")
            return success
        except Exception as e:
            logger.error(f"Error setting volume on {speaker_id}: {e}")
            return False

    async def stop_all(self) -> int:
        """
        Stop playback on all speakers.

        Returns:
            Number of speakers stopped
        """
        count = 0
        for speaker in self.get_enabled_speakers():
            try:
                if await self.stop(speaker.canonical_id):
                    count += 1
            except Exception as e:
                logger.error(f"Error stopping {speaker.name}: {e}")

        logger.info(f"Stopped {count} speakers")
        return count

    def _get_plugin_for_speaker(
        self,
        speaker_id: str
    ) -> tuple[Optional[SpeakerPlugin], str]:
        """
        Get the plugin responsible for a speaker.

        Args:
            speaker_id: Speaker identifier (canonical or original)

        Returns:
            Tuple of (plugin, original_speaker_id) or (None, "")
        """
        if not self._plugin_manager:
            return None, ""

        # Get the unified speaker
        speaker = self.get_speaker(speaker_id)

        if speaker:
            # Find an original_id that we have a plugin mapping for
            for orig_id in speaker.original_ids:
                plugin_id = self._speaker_to_plugin.get(orig_id)
                if plugin_id:
                    plugin = self._plugin_manager.get_plugin(plugin_id)
                    if plugin and isinstance(plugin, SpeakerPlugin):
                        return plugin, orig_id

            # Fallback: try to determine plugin from protocol
            if speaker.protocol:
                plugin = self._plugin_manager.get_plugin(speaker.protocol)
                if plugin and isinstance(plugin, SpeakerPlugin):
                    # Use first original_id
                    orig_id = next(iter(speaker.original_ids), speaker.canonical_id)
                    return plugin, orig_id

        # Try direct lookup by speaker_id
        plugin_id = self._speaker_to_plugin.get(speaker_id)
        if plugin_id:
            plugin = self._plugin_manager.get_plugin(plugin_id)
            if plugin and isinstance(plugin, SpeakerPlugin):
                return plugin, speaker_id

        # Last resort: try to determine plugin from ID prefix
        for prefix in ["sonos_", "chromecast_", "airplay_", "dlna_", "linkplay_", "heos_"]:
            if speaker_id.startswith(prefix):
                plugin_name = prefix.rstrip("_")
                plugin = self._plugin_manager.get_plugin(plugin_name)
                if plugin and isinstance(plugin, SpeakerPlugin):
                    return plugin, speaker_id

        return None, ""

    # ─────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────

    def _load_speaker_state(self) -> None:
        """Load persisted speaker state."""
        if not self._speakers_file or not self._speakers_file.exists():
            return

        try:
            with open(self._speakers_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._enabled_speaker_ids = set(data.get("enabled_ids", []))
            logger.debug(f"Loaded {len(self._enabled_speaker_ids)} enabled speaker IDs")

        except Exception as e:
            logger.error(f"Error loading speaker state: {e}")

    def _save_speaker_state(self) -> None:
        """Persist speaker state."""
        if not self._speakers_file:
            return

        try:
            self._speakers_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "enabled_ids": list(self._enabled_speaker_ids),
            }

            with open(self._speakers_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(self._enabled_speaker_ids)} enabled speaker IDs")

        except Exception as e:
            logger.error(f"Error saving speaker state: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Events
    # ─────────────────────────────────────────────────────────────────────

    def on_speaker_change(self, callback: Callable[[UnifiedSpeaker], None]) -> Callable:
        """
        Subscribe to speaker changes.

        Args:
            callback: Function called when a speaker changes

        Returns:
            Unsubscribe function
        """
        self._on_speaker_change.append(callback)

        def unsubscribe():
            if callback in self._on_speaker_change:
                self._on_speaker_change.remove(callback)

        return unsubscribe

    def _notify_speaker_change(self, speaker: UnifiedSpeaker) -> None:
        """Notify listeners of a speaker change."""
        for callback in self._on_speaker_change:
            try:
                callback(speaker)
            except Exception as e:
                logger.error(f"Error in speaker change callback: {e}")


# ─────────────────────────────────────────────────────────────────────────
# Global Instance
# ─────────────────────────────────────────────────────────────────────────

_coordinator: Optional[SpeakerCoordinator] = None


def get_speaker_coordinator() -> SpeakerCoordinator:
    """Get the global speaker coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = SpeakerCoordinator()
    return _coordinator


def init_speaker_coordinator(
    plugin_manager=None,
    data_dir: Optional[Path] = None,
) -> SpeakerCoordinator:
    """
    Initialize the global speaker coordinator.

    Args:
        plugin_manager: PluginManager instance
        data_dir: Directory for persistence

    Returns:
        Initialized SpeakerCoordinator
    """
    global _coordinator
    _coordinator = SpeakerCoordinator(plugin_manager, data_dir)
    return _coordinator
