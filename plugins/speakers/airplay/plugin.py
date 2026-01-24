"""
AirPlay Speaker Plugin

Provides discovery and playback control for AirPlay devices using pyatv.
Supports Apple TV, HomePod, AirPort Express, and third-party AirPlay speakers.

This is a TRUE plugin - deleting this folder removes AirPlay support entirely.
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


class AirPlayPlugin(SpeakerPlugin):
    """
    AirPlay speaker plugin.

    Discovers AirPlay devices on the network and provides playback control
    using the pyatv library with RAOP streaming.
    """

    def __init__(self):
        self._discovery_timeout = 10
        self._buffer_size = 32768
        self._connections: dict[str, Any] = {}
        self._stream_tasks: dict[str, asyncio.Task] = {}
        self._http_sessions: dict[str, Any] = {}

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="airplay",
            name="AirPlay",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to AirPlay devices",
            author="Sonorium",
            dependencies=["pyatv>=0.14.0", "aiohttp>=3.8.0"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            import pyatv
            logger.info("AirPlay plugin initialized (pyatv available)")
            return True
        except ImportError:
            logger.warning("AirPlay plugin: pyatv not installed")
            return False

    async def shutdown(self) -> None:
        """Clean up all connections."""
        for speaker_id in list(self._stream_tasks.keys()):
            await self.stop(speaker_id)
        self._connections.clear()

    def set_config(self, config: dict) -> None:
        """Apply plugin configuration."""
        self._discovery_timeout = config.get("discovery_timeout", 10)
        self._buffer_size = config.get("buffer_size", 32768)

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover AirPlay devices using pyatv."""
        discovered = []

        try:
            import pyatv

            logger.info("Starting AirPlay discovery...")

            loop = asyncio.get_event_loop()
            devices = await pyatv.scan(loop, timeout=min(timeout, self._discovery_timeout))

            for device in devices:
                try:
                    # Check for AirPlay/RAOP support
                    airplay_service = device.get_service(pyatv.const.Protocol.AirPlay)
                    raop_service = device.get_service(pyatv.const.Protocol.RAOP)

                    if not airplay_service and not raop_service:
                        continue

                    # Create unique ID
                    device_id = str(device.identifier) if device.identifier else str(device.address).replace('.', '_')
                    speaker_id = f"airplay_{device_id[:20]}"

                    # Skip duplicates
                    if any(s.id == speaker_id for s in discovered):
                        continue

                    # Get port
                    port = 7000
                    if airplay_service and airplay_service.port:
                        port = airplay_service.port
                    elif raop_service and raop_service.port:
                        port = raop_service.port

                    # Get model
                    model = "AirPlay Device"
                    if device.device_info and device.device_info.model:
                        model = str(device.device_info.model)

                    speaker = DiscoveredSpeaker(
                        id=speaker_id,
                        name=device.name or f"AirPlay ({device.address})",
                        host=str(device.address),
                        port=port,
                        model=model,
                        manufacturer="Apple",
                        unique_id=str(device.identifier) if device.identifier else None,
                        extra={
                            'identifier': str(device.identifier) if device.identifier else None,
                            'services': [str(s.protocol) for s in device.services],
                        }
                    )

                    discovered.append(speaker)
                    logger.info(f"Found AirPlay: {device.name} at {device.address}")

                except Exception as e:
                    logger.debug(f"Error processing AirPlay device: {e}")

            logger.info(f"AirPlay discovery found {len(discovered)} devices")

        except ImportError:
            logger.warning("pyatv not installed - AirPlay discovery disabled")
        except Exception as e:
            logger.error(f"AirPlay discovery error: {e}")

        return discovered

    async def _connect_device(self, speaker_id: str, host: str, port: int, identifier: Optional[str]) -> Optional[Any]:
        """Connect to an AirPlay device."""
        if speaker_id in self._connections:
            return self._connections[speaker_id]

        try:
            import pyatv
            from pyatv.conf import AppleTV, RaopService

            logger.info(f"AirPlay: Connecting to {host}:{port}...")

            loop = asyncio.get_event_loop()

            if identifier:
                # Build config from stored info
                device_config = AppleTV(host, "AirPlay Device")
                raop_service = RaopService(identifier=identifier, port=port, properties={})
                device_config.add_service(raop_service)
            else:
                # Scan for device
                devices = await pyatv.scan(loop, hosts=[host], timeout=self._discovery_timeout)
                if not devices:
                    logger.error(f"AirPlay: No device found at {host}")
                    return None
                device_config = devices[0]

            atv = await pyatv.connect(device_config, loop)
            self._connections[speaker_id] = atv
            logger.info(f"AirPlay: Connected to {host}")
            return atv

        except Exception as e:
            logger.error(f"AirPlay connection error: {e}")
            return None

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Play a URL on an AirPlay device."""
        try:
            import aiohttp

            # Get speaker info from kwargs or stored data
            host = kwargs.get('host', '')
            port = kwargs.get('port', 7000)
            identifier = kwargs.get('identifier')

            atv = await self._connect_device(speaker_id, host, port, identifier)
            if not atv:
                return False

            if not atv.stream:
                logger.error(f"AirPlay: Device has no stream interface")
                return False

            logger.info(f"AirPlay: Starting stream to {speaker_id}: {url}")

            # Create HTTP session
            http_session = aiohttp.ClientSession()
            self._http_sessions[speaker_id] = http_session

            async def stream_task():
                response = None
                try:
                    response = await http_session.get(url)
                    if response.status != 200:
                        logger.error(f"AirPlay: HTTP {response.status} from stream")
                        return

                    # Pre-buffer
                    reader = asyncio.StreamReader()
                    buffer = bytearray()

                    async for chunk in response.content.iter_chunked(8192):
                        buffer.extend(chunk)
                        if len(buffer) >= self._buffer_size:
                            break

                    reader.feed_data(bytes(buffer))

                    # Continue feeding
                    async def feed():
                        try:
                            async for chunk in response.content.iter_chunked(8192):
                                reader.feed_data(chunk)
                            reader.feed_eof()
                        except asyncio.CancelledError:
                            reader.feed_eof()

                    feed_task = asyncio.create_task(feed())
                    await atv.stream.stream_file(reader)
                    feed_task.cancel()

                except asyncio.CancelledError:
                    logger.info(f"AirPlay: Stream cancelled for {speaker_id}")
                except Exception as e:
                    logger.error(f"AirPlay: Stream error: {e}")
                finally:
                    if response:
                        response.close()

            task = asyncio.create_task(stream_task())
            self._stream_tasks[speaker_id] = task

            await asyncio.sleep(1)
            if task.done():
                try:
                    task.result()
                except Exception as e:
                    logger.error(f"AirPlay: Task failed: {e}")
                    await http_session.close()
                    return False

            logger.info(f"AirPlay: {speaker_id} streaming")
            return True

        except ImportError as e:
            logger.error(f"AirPlay: Import error: {e}")
            return False
        except Exception as e:
            logger.error(f"AirPlay streaming error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop AirPlay playback."""
        try:
            # Cancel stream task
            if speaker_id in self._stream_tasks:
                task = self._stream_tasks[speaker_id]
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                del self._stream_tasks[speaker_id]

            # Close HTTP session
            if speaker_id in self._http_sessions:
                try:
                    await self._http_sessions[speaker_id].close()
                except Exception:
                    pass
                del self._http_sessions[speaker_id]

            # Close connection
            if speaker_id in self._connections:
                atv = self._connections[speaker_id]
                try:
                    if hasattr(atv, 'remote_control') and atv.remote_control:
                        await atv.remote_control.stop()
                    await atv.close()
                except Exception as e:
                    logger.warning(f"Error closing AirPlay: {e}")
                del self._connections[speaker_id]

            logger.info(f"Stopped AirPlay {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping AirPlay: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume on an AirPlay device."""
        try:
            atv = self._connections.get(speaker_id)
            if not atv:
                return False

            volume = max(0.0, min(1.0, volume))

            if hasattr(atv, 'audio') and atv.audio:
                await atv.audio.set_volume(volume * 100)
                logger.debug(f"Set AirPlay {speaker_id} volume to {int(volume * 100)}%")
                return True

            return False

        except Exception as e:
            logger.warning(f"Error setting AirPlay volume: {e}")
            return False

    async def stop_all(self) -> int:
        """Stop all AirPlay speakers."""
        count = 0
        for speaker_id in list(self._stream_tasks.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count


# Plugin entry point
Plugin = AirPlayPlugin
