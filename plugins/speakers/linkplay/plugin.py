"""
LinkPlay/Arylic Speaker Plugin

Provides discovery and playback control for LinkPlay-based devices (Arylic, Up2Stream, etc.)
using the LinkPlay HTTP API.

This is a TRUE plugin - deleting this folder removes LinkPlay support entirely.
"""

from __future__ import annotations

import asyncio
import socket
import logging
from typing import Optional, Any

from sonorium.plugins import (
    SpeakerPlugin,
    PluginManifest,
    PluginType,
    DiscoveredSpeaker,
)

logger = logging.getLogger(__name__)

# Default LinkPlay UPnP port
LINKPLAY_PORT = 49152


class LinkPlayPlugin(SpeakerPlugin):
    """
    LinkPlay/Arylic speaker plugin.

    Discovers LinkPlay devices via subnet scanning and controls them
    using the LinkPlay HTTP API.
    """

    def __init__(self):
        self._discovery_timeout = 10
        self._scan_batch_size = 50
        self._devices: dict[str, dict] = {}

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="linkplay",
            name="LinkPlay/Arylic",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to LinkPlay and Arylic devices",
            author="Sonorium",
            dependencies=["aiohttp>=3.8.0"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            import aiohttp
            logger.info("LinkPlay plugin initialized")
            return True
        except ImportError:
            logger.warning("LinkPlay plugin: aiohttp not installed")
            return False

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._devices.clear()

    def set_config(self, config: dict) -> None:
        """Apply plugin configuration."""
        self._discovery_timeout = config.get("discovery_timeout", 10)
        self._scan_batch_size = config.get("scan_batch_size", 50)

    def _get_local_ip(self) -> Optional[str]:
        """Get the local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover LinkPlay/Arylic devices by probing the local subnet."""
        discovered = []

        try:
            import aiohttp
            import re

            logger.info("Starting LinkPlay direct probe discovery...")

            local_ip = self._get_local_ip()
            if not local_ip:
                logger.warning("Could not determine local IP for LinkPlay scan")
                return discovered

            # Get subnet (assume /24)
            subnet_prefix = '.'.join(local_ip.split('.')[:3])
            logger.info(f"Scanning subnet {subnet_prefix}.0/24 for LinkPlay devices...")

            async def probe_host(host: str) -> Optional[DiscoveredSpeaker]:
                """Probe a single host for LinkPlay device."""
                url = f"http://{host}:{LINKPLAY_PORT}/description.xml"
                try:
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=2)
                    ) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                text = await response.text()

                                # Check if it's a media renderer
                                if 'MediaRenderer' not in text and 'AVTransport' not in text:
                                    return None

                                info = {}

                                # Extract device info
                                match = re.search(r'<friendlyName>([^<]+)</friendlyName>', text, re.IGNORECASE)
                                if match:
                                    info['friendlyName'] = match.group(1)

                                match = re.search(r'<modelName>([^<]+)</modelName>', text, re.IGNORECASE)
                                if match:
                                    info['modelName'] = match.group(1)

                                match = re.search(r'<manufacturer>([^<]+)</manufacturer>', text, re.IGNORECASE)
                                if match:
                                    info['manufacturer'] = match.group(1)

                                match = re.search(r'<UDN>uuid:([^<]+)</UDN>', text, re.IGNORECASE)
                                if match:
                                    info['uuid'] = match.group(1)

                                # Create speaker
                                device_id = info.get('uuid', host.replace('.', '_'))[:20]
                                speaker_id = f"linkplay_{device_id}"

                                name = info.get('friendlyName', f"LinkPlay ({host})")
                                model = info.get('modelName')
                                manufacturer = info.get('manufacturer', 'LinkPlay')

                                # Store device info for later use
                                self._devices[speaker_id] = {
                                    'host': host,
                                    'port': LINKPLAY_PORT,
                                    'location': url,
                                    'uuid': info.get('uuid', ''),
                                }

                                speaker = DiscoveredSpeaker(
                                    id=speaker_id,
                                    name=name,
                                    host=host,
                                    port=LINKPLAY_PORT,
                                    model=model,
                                    manufacturer=manufacturer,
                                    extra={
                                        'location': url,
                                        'uuid': info.get('uuid', ''),
                                    }
                                )
                                logger.info(f"Found LinkPlay: {name} ({model}) at {host}")
                                return speaker

                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

                return None

            # Probe all hosts in subnet concurrently (in batches)
            all_hosts = [f"{subnet_prefix}.{i}" for i in range(1, 255)]

            for batch_start in range(0, len(all_hosts), self._scan_batch_size):
                batch = all_hosts[batch_start:batch_start + self._scan_batch_size]
                tasks = [probe_host(host) for host in batch]
                results = await asyncio.gather(*tasks)

                for speaker in results:
                    if speaker:
                        # Skip if duplicate
                        if not any(s.id == speaker.id for s in discovered):
                            discovered.append(speaker)

            logger.info(f"LinkPlay discovery found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"LinkPlay discovery error: {e}")

        return discovered

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Play a URL on a LinkPlay device using HTTP API."""
        try:
            import aiohttp

            device = self._devices.get(speaker_id)
            if not device:
                host = kwargs.get('host')
                if not host:
                    logger.error(f"LinkPlay: No device info for {speaker_id}")
                    return False
                device = {'host': host, 'port': LINKPLAY_PORT}

            host = device['host']
            speaker_name = kwargs.get('name', host)

            logger.info(f"LinkPlay HTTP: Starting stream to {speaker_name} at {host}")

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as http_session:
                # First, verify the device responds to HTTP API
                status_url = f"http://{host}/httpapi.asp?command=getStatusEx"
                try:
                    async with http_session.get(status_url) as resp:
                        if resp.status == 200:
                            import json
                            try:
                                status = json.loads(await resp.text())
                                device_name = status.get('DeviceName', 'Unknown')
                                logger.info(f"LinkPlay HTTP: Device confirmed: {device_name}")
                            except Exception:
                                logger.debug("LinkPlay HTTP: Could not parse status, continuing anyway")
                except Exception as e:
                    logger.debug(f"LinkPlay HTTP: Status check failed: {e}, continuing anyway")

                # Tell device to play our stream URL
                play_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:play:{url}"
                logger.info(f"LinkPlay HTTP: Sending play command")

                async with http_session.get(play_url) as resp:
                    response_text = await resp.text()
                    logger.debug(f"LinkPlay HTTP: Play response: {response_text}")

                    if response_text.strip() == "OK":
                        logger.info(f"LinkPlay HTTP: {speaker_name} now playing {url}")
                        return True
                    else:
                        logger.error(f"LinkPlay HTTP: Play failed with response: {response_text}")
                        return False

        except ImportError as e:
            logger.error(f"LinkPlay HTTP: Import error: {e}")
            return False
        except Exception as e:
            logger.error(f"LinkPlay HTTP: Error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a LinkPlay device."""
        try:
            import aiohttp

            device = self._devices.get(speaker_id)
            if not device:
                logger.warning(f"LinkPlay: No device info for {speaker_id}")
                return False

            host = device['host']
            stop_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:stop"

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as http_session:
                async with http_session.get(stop_url) as resp:
                    logger.info(f"LinkPlay HTTP: Stop command sent to {host}")
                    return True

        except Exception as e:
            logger.warning(f"LinkPlay HTTP: Error stopping playback: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume on a LinkPlay device (0.0-1.0 -> 0-100)."""
        try:
            import aiohttp

            device = self._devices.get(speaker_id)
            if not device:
                return False

            host = device['host']
            vol_percent = int(max(0.0, min(1.0, volume)) * 100)
            vol_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:vol:{vol_percent}"

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as http_session:
                async with http_session.get(vol_url) as resp:
                    logger.debug(f"LinkPlay: Set volume to {vol_percent}%")
                    return True

        except Exception as e:
            logger.warning(f"LinkPlay: Error setting volume: {e}")
            return False

    async def stop_all(self) -> int:
        """Stop all LinkPlay speakers."""
        count = 0
        for speaker_id in list(self._devices.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count


# Plugin entry point
Plugin = LinkPlayPlugin
