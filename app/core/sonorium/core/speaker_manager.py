"""
Sonorium Speaker Manager

Central manager for all network speakers across all enabled speaker plugins.
Aggregates speakers discovered by protocol plugins (AirPlay, Chromecast, Sonos, DLNA)
and provides a unified interface for the UI and API.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional, Callable

from sonorium.obs import logger
from sonorium.plugins.speaker_base import NetworkSpeaker, SpeakerState

if TYPE_CHECKING:
    from sonorium.plugins.manager import PluginManager
    from sonorium.plugins.speaker_base import SpeakerPlugin


class SpeakerManager:
    """
    Central manager for all network speakers.

    Aggregates speakers discovered by all enabled speaker plugins
    and provides a unified interface for the UI and API.
    """

    def __init__(self, plugin_manager: "PluginManager"):
        """
        Initialize the SpeakerManager.

        Args:
            plugin_manager: The plugin manager to get speaker plugins from
        """
        self.plugin_manager = plugin_manager

        # Cache of all speakers: speaker_id -> NetworkSpeaker
        self._speakers: dict[str, NetworkSpeaker] = {}

        # Map speaker_id to the plugin that owns it
        self._plugin_map: dict[str, "SpeakerPlugin"] = {}

        # Callback for speaker state changes
        self._on_change_callback: Optional[Callable[[NetworkSpeaker], None]] = None

        # Discovery state
        self._discovery_running = False
        self._discovery_task: Optional[asyncio.Task] = None

        logger.info("SpeakerManager initialized")

    def set_change_callback(self, callback: Callable[[NetworkSpeaker], None]) -> None:
        """Set callback for speaker state changes."""
        self._on_change_callback = callback

    def _get_speaker_plugins(self) -> list["SpeakerPlugin"]:
        """Get all enabled speaker plugins."""
        plugins = []
        for plugin in self.plugin_manager.get_plugins_by_type("speaker"):
            if plugin.enabled:
                plugins.append(plugin)
        return plugins

    def _on_speaker_change(self, speaker: NetworkSpeaker) -> None:
        """Handle speaker state change from a plugin."""
        self._speakers[speaker.id] = speaker
        if self._on_change_callback:
            self._on_change_callback(speaker)

    # --- Discovery ---

    async def discover_all(self) -> list[NetworkSpeaker]:
        """
        Run discovery on all enabled speaker plugins.

        Returns:
            List of all discovered speakers
        """
        speakers = []
        plugins = self._get_speaker_plugins()

        # Discover in parallel for better performance
        if plugins:
            tasks = [plugin.refresh_speakers() for plugin in plugins]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for plugin, result in zip(plugins, results):
                if isinstance(result, Exception):
                    logger.error(f"Discovery failed for {plugin.name}: {result}")
                    continue

                for speaker in result:
                    # Ensure protocol is set
                    if not speaker.protocol:
                        speaker.protocol = plugin.protocol

                    self._speakers[speaker.id] = speaker
                    self._plugin_map[speaker.id] = plugin
                    speakers.append(speaker)

        logger.info(f"SpeakerManager: Discovered {len(speakers)} speakers from {len(plugins)} plugins")
        return speakers

    async def start_discovery(self, interval: float = 30.0) -> None:
        """
        Start continuous discovery on all speaker plugins.

        Args:
            interval: Seconds between discovery scans
        """
        if self._discovery_running:
            return

        self._discovery_running = True

        # Start discovery on all plugins
        for plugin in self._get_speaker_plugins():
            plugin.set_speaker_change_callback(self._on_speaker_change)
            await plugin.start_discovery(interval)

        logger.info(f"SpeakerManager: Started discovery (interval: {interval}s)")

    async def stop_discovery(self) -> None:
        """Stop discovery on all speaker plugins."""
        self._discovery_running = False

        for plugin in self._get_speaker_plugins():
            await plugin.stop_discovery()

        logger.info("SpeakerManager: Stopped discovery")

    # --- Speaker Access ---

    def get_speakers(self) -> list[NetworkSpeaker]:
        """Get all discovered speakers."""
        return list(self._speakers.values())

    def get_speaker(self, speaker_id: str) -> Optional[NetworkSpeaker]:
        """Get a speaker by ID."""
        return self._speakers.get(speaker_id)

    def get_speakers_by_protocol(self, protocol: str) -> list[NetworkSpeaker]:
        """Get speakers filtered by protocol."""
        return [s for s in self._speakers.values() if s.protocol == protocol]

    def get_speakers_by_state(self, state: SpeakerState) -> list[NetworkSpeaker]:
        """Get speakers filtered by state."""
        return [s for s in self._speakers.values() if s.state == state]

    def get_playing_speakers(self) -> list[NetworkSpeaker]:
        """Get speakers that are currently playing."""
        return self.get_speakers_by_state(SpeakerState.PLAYING)

    # --- Streaming Control ---

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Start streaming to a speaker.

        Args:
            speaker_id: Target speaker ID
            url: Audio stream URL

        Returns:
            True if streaming started successfully
        """
        if speaker_id not in self._plugin_map:
            logger.warning(f"SpeakerManager: Unknown speaker {speaker_id}")
            return False

        plugin = self._plugin_map[speaker_id]
        try:
            success = await plugin.play_url(speaker_id, url)
            if success:
                speaker = self._speakers.get(speaker_id)
                if speaker:
                    speaker.state = SpeakerState.PLAYING
                    speaker.current_media = url
            return success
        except Exception as e:
            logger.error(f"SpeakerManager: Failed to play on {speaker_id}: {e}")
            return False

    async def play_theme(
        self,
        speaker_id: str,
        theme_id: str,
        preset_id: Optional[str] = None
    ) -> bool:
        """
        Play a theme on a speaker.

        Args:
            speaker_id: Target speaker
            theme_id: Theme to play
            preset_id: Optional preset

        Returns:
            True if playback started
        """
        if speaker_id not in self._plugin_map:
            logger.warning(f"SpeakerManager: Unknown speaker {speaker_id}")
            return False

        plugin = self._plugin_map[speaker_id]
        return await plugin.play_theme(speaker_id, theme_id, preset_id)

    async def stop(self, speaker_id: str) -> bool:
        """
        Stop streaming to a speaker.

        Args:
            speaker_id: Target speaker ID

        Returns:
            True if stopped successfully
        """
        if speaker_id not in self._plugin_map:
            logger.warning(f"SpeakerManager: Unknown speaker {speaker_id}")
            return False

        plugin = self._plugin_map[speaker_id]
        try:
            success = await plugin.stop(speaker_id)
            if success:
                speaker = self._speakers.get(speaker_id)
                if speaker:
                    speaker.state = SpeakerState.IDLE
                    speaker.current_media = None
            return success
        except Exception as e:
            logger.error(f"SpeakerManager: Failed to stop {speaker_id}: {e}")
            return False

    async def stop_all(self) -> dict[str, bool]:
        """
        Stop streaming to all speakers.

        Returns:
            Dict mapping speaker_id to success status
        """
        results = {}
        for speaker_id in list(self._speakers.keys()):
            results[speaker_id] = await self.stop(speaker_id)
        return results

    # --- Volume Control ---

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """
        Set volume on a speaker.

        Args:
            speaker_id: Target speaker ID
            level: Volume level 0.0-1.0

        Returns:
            True if volume was set
        """
        if speaker_id not in self._plugin_map:
            logger.warning(f"SpeakerManager: Unknown speaker {speaker_id}")
            return False

        plugin = self._plugin_map[speaker_id]
        try:
            success = await plugin.set_volume(speaker_id, level)
            if success:
                speaker = self._speakers.get(speaker_id)
                if speaker:
                    speaker.volume = level
            return success
        except Exception as e:
            logger.error(f"SpeakerManager: Failed to set volume on {speaker_id}: {e}")
            return False

    async def mute(self, speaker_id: str, muted: bool = True) -> bool:
        """
        Mute/unmute a speaker.

        Args:
            speaker_id: Target speaker ID
            muted: Whether to mute

        Returns:
            True if mute state was set
        """
        if speaker_id not in self._plugin_map:
            return False

        plugin = self._plugin_map[speaker_id]
        try:
            success = await plugin.mute(speaker_id, muted)
            if success:
                speaker = self._speakers.get(speaker_id)
                if speaker:
                    speaker.is_muted = muted
            return success
        except Exception as e:
            logger.error(f"SpeakerManager: Failed to mute {speaker_id}: {e}")
            return False

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Serialize manager state for API."""
        protocols = set(s.protocol for s in self._speakers.values() if s.protocol)
        return {
            "speaker_count": len(self._speakers),
            "protocols": list(protocols),
            "discovery_running": self._discovery_running,
            "speakers": [s.to_dict() for s in self._speakers.values()],
        }

    def list_speakers(self) -> list[dict]:
        """Get all speakers as serialized dicts for API."""
        return [s.to_dict() for s in self._speakers.values()]
