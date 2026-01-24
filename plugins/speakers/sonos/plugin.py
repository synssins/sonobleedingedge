"""
Sonos Speaker Plugin

Provides discovery and playback control for Sonos speakers using the soco library.
This is a TRUE plugin - deleting this folder removes Sonos support entirely.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any

# Import from core plugin framework
from sonorium.plugins import (
    SpeakerPlugin,
    PluginManifest,
    PluginType,
    DiscoveredSpeaker,
)

logger = logging.getLogger(__name__)


class SonosPlugin(SpeakerPlugin):
    """
    Sonos speaker plugin.

    Discovers Sonos devices on the network and provides playback control
    using the soco (Sonos Controller) library.
    """

    def __init__(self):
        self._discovery_timeout = 5
        self._use_groups = True
        self._devices: dict[str, Any] = {}  # speaker_id -> soco.SoCo device

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="sonos",
            name="Sonos",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to Sonos speakers",
            author="Sonorium",
            dependencies=["soco>=0.30.0"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            import soco
            logger.info("Sonos plugin initialized (soco available)")
            return True
        except ImportError:
            logger.warning("Sonos plugin: soco not installed")
            return False

    async def shutdown(self) -> None:
        """Clean up resources."""
        await self.stop_all()
        self._devices.clear()

    def set_config(self, config: dict) -> None:
        """Apply plugin configuration."""
        self._discovery_timeout = config.get("discovery_timeout", 5)
        self._use_groups = config.get("use_groups", True)

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """
        Discover Sonos speakers on the network.

        Returns:
            List of discovered speakers
        """
        discovered = []

        try:
            import soco

            logger.info("Starting Sonos discovery...")

            # Use provided timeout or configured default
            actual_timeout = min(timeout, self._discovery_timeout)

            # Run blocking discovery in thread
            def _discover():
                return list(soco.discover(timeout=actual_timeout) or [])

            loop = asyncio.get_event_loop()
            devices = await loop.run_in_executor(None, _discover)

            for device in devices:
                try:
                    speaker_id = f"sonos_{device.uid}"

                    # Get volume
                    volume = 0.5
                    try:
                        volume = device.volume / 100.0
                    except Exception:
                        pass

                    # Check if group coordinator
                    is_group = False
                    group_members = []
                    if self._use_groups and device.is_coordinator:
                        try:
                            members = list(device.group.members)
                            if len(members) > 1:
                                is_group = True
                                group_members = [m.uid for m in members]
                        except Exception:
                            pass

                    speaker = DiscoveredSpeaker(
                        id=speaker_id,
                        name=device.player_name,
                        host=device.ip_address,
                        port=1400,
                        model=device.speaker_info.get('model_name', 'Sonos'),
                        manufacturer="Sonos",
                        unique_id=device.uid,
                        extra={
                            'uid': device.uid,
                            'zone_name': device.speaker_info.get('zone_name'),
                            'is_coordinator': device.is_coordinator,
                            'is_group': is_group,
                            'group_members': group_members,
                            'volume': volume,
                        }
                    )

                    # Cache device for playback
                    self._devices[speaker_id] = device
                    discovered.append(speaker)
                    logger.debug(f"Found Sonos: {speaker.name} at {speaker.host}")

                except Exception as e:
                    logger.warning(f"Error processing Sonos device: {e}")

            logger.info(f"Sonos discovery found {len(discovered)} devices")

        except ImportError:
            logger.warning("soco not installed - Sonos discovery disabled")
        except Exception as e:
            logger.error(f"Sonos discovery error: {e}")

        return discovered

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """
        Play a URL on a Sonos speaker.

        Args:
            speaker_id: The speaker ID (sonos_{uid})
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        try:
            import soco

            device = self._devices.get(speaker_id)
            if not device:
                logger.error(f"Sonos device not found: {speaker_id}")
                return False

            logger.info(f"Starting Sonos playback on {speaker_id}: {url}")

            loop = asyncio.get_event_loop()

            def _play():
                device.stop()
                device.clear_queue()
                device.play_uri(uri=url, title='Sonorium', force_radio=True)
                return True

            result = await loop.run_in_executor(None, _play)
            logger.info(f"Sonos {speaker_id} now playing")
            return result

        except ImportError:
            logger.error("soco not installed")
            return False
        except Exception as e:
            logger.error(f"Sonos playback error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a Sonos speaker."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                logger.warning(f"Sonos device not found: {speaker_id}")
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.stop)

            logger.info(f"Stopped Sonos {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping Sonos: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume on a Sonos speaker (0.0-1.0)."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                return False

            # Convert 0.0-1.0 to 0-100
            vol = int(max(0, min(100, volume * 100)))

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: setattr(device, 'volume', vol))

            logger.debug(f"Set Sonos {speaker_id} volume to {vol}%")
            return True

        except Exception as e:
            logger.warning(f"Error setting Sonos volume: {e}")
            return False

    async def stop_all(self) -> int:
        """Stop all Sonos speakers."""
        count = 0
        for speaker_id in list(self._devices.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count

    async def get_state(self, speaker_id: str) -> Optional[dict]:
        """Get current state of a Sonos speaker."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                return None

            loop = asyncio.get_event_loop()

            def _get_state():
                transport_info = device.get_current_transport_info()
                return {
                    'state': transport_info.get('current_transport_state', 'STOPPED'),
                    'volume': device.volume / 100.0,
                    'muted': device.mute,
                }

            return await loop.run_in_executor(None, _get_state)

        except Exception as e:
            logger.warning(f"Error getting Sonos state: {e}")
            return None


# Plugin entry point - required for plugin loader
Plugin = SonosPlugin
