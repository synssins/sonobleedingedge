"""
AirPlay Speaker Plugin

Provides discovery and playback control for AirPlay devices using pyatv.
Supports Apple TV, HomePod, AirPort Express, and third-party AirPlay speakers.

This is a TRUE plugin - deleting this folder removes AirPlay support entirely.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Any

from sonorium.plugins.speaker_base import (
    SpeakerPlugin,
    NetworkSpeaker,
    SpeakerState,
)
from sonorium.obs import logger


class AirPlayPlugin(SpeakerPlugin):
    """
    AirPlay speaker plugin.

    Discovers AirPlay devices on the network and provides playback control
    using the pyatv library with RAOP streaming.

    Supports:
    - Apple TV (all generations)
    - HomePod / HomePod mini
    - AirPort Express
    - Third-party AirPlay speakers (Sonos, B&O, etc.)
    - Linkplay/Arylic devices (via fallback HTTP API)
    """

    plugin_type: str = "speaker"

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Settings
        self._discovery_timeout = settings.get("discovery_timeout", 10)
        self._buffer_size = settings.get("buffer_size", 32768)

        # Active connections
        self._connections: dict[str, Any] = {}
        self._stream_tasks: dict[str, asyncio.Task] = {}
        self._http_sessions: dict[str, Any] = {}

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """
        Discover AirPlay devices using pyatv.

        Returns:
            List of discovered NetworkSpeaker objects
        """
        discovered = []

        try:
            import pyatv

            logger.info("Starting AirPlay discovery...")

            loop = asyncio.get_event_loop()
            devices = await pyatv.scan(loop, timeout=self._discovery_timeout)

            for device in devices:
                try:
                    # Check if device supports AirPlay
                    airplay_service = device.get_service(pyatv.const.Protocol.AirPlay)
                    raop_service = device.get_service(pyatv.const.Protocol.RAOP)

                    if not airplay_service and not raop_service:
                        logger.debug(f"Device {device.name} doesn't support AirPlay, skipping")
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

                    # Get model info
                    model = None
                    if device.device_info and device.device_info.model:
                        model = str(device.device_info.model)

                    speaker = NetworkSpeaker(
                        id=speaker_id,
                        name=device.name or f"AirPlay Device ({device.address})",
                        model=model or "AirPlay Device",
                        manufacturer="Apple",
                        ip_address=str(device.address),
                        port=port,
                        state=SpeakerState.IDLE,
                        volume=1.0,
                        is_muted=False,
                        capabilities=["volume"],
                        extra={
                            'identifier': str(device.identifier) if device.identifier else None,
                            'all_identifiers': [str(i) for i in device.all_identifiers] if device.all_identifiers else [],
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
            import traceback
            logger.error(traceback.format_exc())

        return discovered

    async def _connect_device(self, speaker_id: str) -> Optional[Any]:
        """
        Connect to an AirPlay device.

        Args:
            speaker_id: The speaker ID

        Returns:
            pyatv connection or None
        """
        if speaker_id in self._connections:
            return self._connections[speaker_id]

        speaker = self.get_speaker(speaker_id)
        if not speaker:
            logger.error(f"AirPlay: Speaker not found: {speaker_id}")
            return None

        try:
            import pyatv
            from pyatv.conf import AppleTV, RaopService

            host = speaker.ip_address
            port = speaker.port
            identifier = speaker.extra.get('identifier')

            logger.info(f"AirPlay: Connecting to {speaker.name} at {host}:{port}...")

            loop = asyncio.get_event_loop()
            device_config = None

            if identifier:
                # Build config from stored info
                logger.info(f"AirPlay: Building config from stored info (identifier: {identifier})")
                device_config = AppleTV(host, speaker.name)

                raop_service = RaopService(
                    identifier=identifier,
                    port=port,
                    properties={}
                )
                device_config.add_service(raop_service)
            else:
                # Scan for device
                logger.info(f"AirPlay: No stored identifier, scanning for device...")
                devices = await pyatv.scan(loop, hosts=[host], timeout=self._discovery_timeout)

                if not devices:
                    logger.error(f"AirPlay: No device found at {host}")
                    return None

                device_config = devices[0]
                protocols = [str(s.protocol) for s in device_config.services]
                logger.info(f"AirPlay: Found device '{device_config.name}' with protocols: {protocols}")

            # Connect
            atv = await pyatv.connect(device_config, loop)
            self._connections[speaker_id] = atv

            logger.info(f"AirPlay: Connected to {speaker.name}")
            return atv

        except ImportError:
            logger.error("pyatv not installed")
        except Exception as e:
            logger.error(f"AirPlay connection error: {e}")

        return None

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Play a URL on an AirPlay device.

        Uses pyatv's stream_file() with aiohttp to fetch the HTTP stream.

        Args:
            speaker_id: The speaker ID
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        try:
            import aiohttp

            atv = await self._connect_device(speaker_id)
            if not atv:
                return False

            speaker = self.get_speaker(speaker_id)
            speaker_name = speaker.name if speaker else speaker_id

            # Check streaming interface
            if not atv.stream:
                logger.error(f"AirPlay: Device {speaker_name} has no stream interface")
                return False

            logger.info(f"AirPlay: Starting stream to {speaker_name} via RAOP: {url}")

            # Create HTTP session
            http_session = aiohttp.ClientSession()
            self._http_sessions[speaker_id] = http_session

            # Stream task
            async def stream_task():
                response = None
                try:
                    logger.info(f"AirPlay: Connecting to stream URL: {url}")
                    response = await http_session.get(url)

                    if response.status != 200:
                        logger.error(f"AirPlay: HTTP {response.status} from stream URL")
                        return

                    logger.info(f"AirPlay: Streaming started to {speaker_name}")

                    # Pre-buffer for MP3 headers
                    reader = asyncio.StreamReader()
                    initial_buffer = bytearray()

                    logger.info(f"AirPlay: Pre-buffering {self._buffer_size} bytes...")
                    async for chunk in response.content.iter_chunked(8192):
                        initial_buffer.extend(chunk)
                        if len(initial_buffer) >= self._buffer_size:
                            break

                    reader.feed_data(bytes(initial_buffer))
                    logger.info(f"AirPlay: Pre-buffered {len(initial_buffer)} bytes, starting stream")

                    # Continue feeding in background
                    async def feed_reader():
                        try:
                            async for chunk in response.content.iter_chunked(8192):
                                reader.feed_data(chunk)
                            reader.feed_eof()
                        except asyncio.CancelledError:
                            reader.feed_eof()
                        except Exception as e:
                            logger.error(f"AirPlay: Error feeding stream: {e}")
                            reader.feed_eof()

                    feed_task = asyncio.create_task(feed_reader())

                    # Stream to AirPlay
                    await atv.stream.stream_file(reader)
                    feed_task.cancel()

                    logger.info(f"AirPlay: Stream completed to {speaker_name}")

                except asyncio.CancelledError:
                    logger.info(f"AirPlay: Stream cancelled for {speaker_name}")
                except Exception as e:
                    logger.error(f"AirPlay: Stream error for {speaker_name}: {e}")
                finally:
                    if response:
                        try:
                            response.close()
                        except Exception:
                            pass

            # Start streaming task
            task = asyncio.create_task(stream_task())
            self._stream_tasks[speaker_id] = task

            # Wait briefly and check for immediate failure
            await asyncio.sleep(1)

            if task.done():
                try:
                    task.result()
                except Exception as e:
                    logger.error(f"AirPlay: Task failed immediately: {e}")
                    await http_session.close()
                    return False

            # Update state
            if speaker:
                speaker.state = SpeakerState.PLAYING
                speaker.current_media = url
                self._update_speaker(speaker)

            logger.info(f"AirPlay: {speaker_name} streaming from {url}")
            return True

        except ImportError as e:
            logger.error(f"AirPlay: Import error: {e}")
            return False
        except Exception as e:
            logger.error(f"AirPlay streaming error: {e}", exc_info=True)
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

            # Close pyatv connection
            if speaker_id in self._connections:
                atv = self._connections[speaker_id]
                try:
                    if hasattr(atv, 'remote_control') and atv.remote_control:
                        await atv.remote_control.stop()
                    await atv.close()
                except Exception as e:
                    logger.warning(f"Error closing AirPlay connection: {e}")
                del self._connections[speaker_id]

            # Update state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.IDLE
                speaker.current_media = None
                self._update_speaker(speaker)

            logger.info(f"Stopped AirPlay {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping AirPlay: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume on an AirPlay device."""
        try:
            atv = self._connections.get(speaker_id)
            if not atv:
                atv = await self._connect_device(speaker_id)
                if not atv:
                    return False

            level = max(0.0, min(1.0, level))

            if hasattr(atv, 'audio') and atv.audio:
                await atv.audio.set_volume(level * 100)

                speaker = self.get_speaker(speaker_id)
                if speaker:
                    speaker.volume = level
                    self._update_speaker(speaker)

                logger.debug(f"Set AirPlay {speaker_id} volume to {int(level * 100)}%")
                return True

            logger.warning(f"AirPlay device {speaker_id} doesn't support volume control")
            return False

        except Exception as e:
            logger.warning(f"Error setting AirPlay volume: {e}")
            return False

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities."""
        return ["volume"]

    async def on_disable(self) -> None:
        """Clean up all connections when disabled."""
        await super().on_disable()

        # Stop all streams
        for speaker_id in list(self._stream_tasks.keys()):
            await self.stop(speaker_id)


# Plugin entry point
Plugin = AirPlayPlugin
