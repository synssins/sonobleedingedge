"""
Chromecast Speaker Plugin

Discovers and controls Chromecast and Google Cast devices on the local network.
This is a TRUE plugin - deleting this folder removes Chromecast support entirely.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any

from sonorium.plugins import (
    SpeakerPlugin,
    PluginManifest,
    PluginType,
    DiscoveredSpeaker,
)

logger = logging.getLogger(__name__)

# Try to import pychromecast
try:
    import pychromecast
    PYCHROMECAST_AVAILABLE = True
except ImportError:
    PYCHROMECAST_AVAILABLE = False
    pychromecast = None


class ChromecastPlugin(SpeakerPlugin):
    """
    Chromecast/Google Cast speaker plugin.

    Discovers Cast devices on the network and streams audio to them.
    """

    def __init__(self):
        self._browser = None
        self._casts: dict[str, Any] = {}
        self._discovery_lock = asyncio.Lock()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="chromecast",
            name="Chromecast",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to Chromecast devices",
            author="Sonorium",
            dependencies=["pychromecast>=14.0.0"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        if not PYCHROMECAST_AVAILABLE:
            logger.warning("Chromecast plugin: pychromecast not installed")
            return False
        logger.info("Chromecast plugin initialized")
        return True

    async def shutdown(self) -> None:
        """Clean up resources."""
        await self._disconnect_all()

    async def _disconnect_all(self) -> None:
        """Disconnect from all Cast devices."""
        for cast in self._casts.values():
            try:
                cast.disconnect()
            except Exception:
                pass
        self._casts.clear()

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover Chromecast devices on the network."""
        if not PYCHROMECAST_AVAILABLE:
            return []

        async with self._discovery_lock:
            try:
                loop = asyncio.get_event_loop()
                speakers = await loop.run_in_executor(None, self._discover_sync, timeout)
                return speakers
            except Exception as e:
                logger.error(f"Chromecast discovery error: {e}")
                return []

    def _discover_sync(self, timeout: float) -> list[DiscoveredSpeaker]:
        """Synchronous discovery (runs in thread pool)."""
        speakers = []

        try:
            logger.info("Starting Chromecast discovery...")
            chromecasts, browser = pychromecast.get_chromecasts(timeout=min(timeout, 5))

            logger.info(f"Chromecast discovery found {len(chromecasts)} devices")

            for cc in chromecasts:
                try:
                    device = cc.cast_info

                    speaker = DiscoveredSpeaker(
                        id=str(device.uuid),
                        name=device.friendly_name or device.host,
                        host=device.host,
                        port=device.port or 8009,
                        model=device.model_name or "Chromecast",
                        manufacturer="Google",
                        unique_id=str(device.uuid),
                        extra={
                            "cast_type": device.cast_type,
                            "uuid": str(device.uuid),
                        }
                    )
                    speakers.append(speaker)

                    # Store cast object
                    self._casts[str(device.uuid)] = cc
                    logger.info(f"Found Chromecast: {speaker.name} at {speaker.host}")

                except Exception as e:
                    logger.warning(f"Error processing Chromecast: {e}")

            browser.stop_discovery()

        except Exception as e:
            logger.error(f"Chromecast discovery failed: {e}")

        return speakers

    async def _get_cast(self, speaker_id: str) -> Optional[Any]:
        """Get or connect to a Cast device."""
        if speaker_id in self._casts:
            cast = self._casts[speaker_id]
            if cast.socket_client and cast.socket_client.is_connected:
                return cast

        # Need to rediscover
        await self.discover()
        return self._casts.get(speaker_id)

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Play a URL on a Chromecast device."""
        if not PYCHROMECAST_AVAILABLE:
            return False

        cast = await self._get_cast(speaker_id)
        if not cast:
            logger.error(f"Chromecast: Speaker {speaker_id} not found")
            return False

        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._play_sync, cast, url)
            return success
        except Exception as e:
            logger.error(f"Chromecast play failed: {e}")
            return False

    def _play_sync(self, cast: Any, url: str) -> bool:
        """Synchronous play."""
        try:
            cast.wait(timeout=10)
            mc = cast.media_controller
            mc.play_media(url, "audio/mpeg", title="Sonorium", stream_type="LIVE")
            mc.block_until_active(timeout=10)
            return True
        except Exception as e:
            logger.error(f"Chromecast play error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a Chromecast device."""
        if not PYCHROMECAST_AVAILABLE:
            return False

        cast = await self._get_cast(speaker_id)
        if not cast:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: cast.quit_app())
            logger.info(f"Stopped Chromecast {speaker_id}")
            return True
        except Exception as e:
            logger.error(f"Chromecast stop failed: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume (0.0-1.0)."""
        if not PYCHROMECAST_AVAILABLE:
            return False

        cast = await self._get_cast(speaker_id)
        if not cast:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: cast.set_volume(max(0.0, min(1.0, volume)))
            )
            return True
        except Exception as e:
            logger.error(f"Chromecast volume failed: {e}")
            return False

    async def stop_all(self) -> int:
        """Stop all Chromecast speakers."""
        count = 0
        for speaker_id in list(self._casts.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count


# Plugin entry point
Plugin = ChromecastPlugin
