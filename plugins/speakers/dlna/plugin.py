"""
DLNA/UPnP Speaker Plugin

Provides discovery and playback control for DLNA/UPnP media renderers.
Uses SSDP for discovery and async-upnp-client for control.

This is a TRUE plugin - deleting this folder removes DLNA support entirely.
"""

from __future__ import annotations

import asyncio
import html
import socket
import logging
from typing import Optional, Any
from urllib.parse import urlparse

from sonorium.plugins import (
    SpeakerPlugin,
    PluginManifest,
    PluginType,
    DiscoveredSpeaker,
)

logger = logging.getLogger(__name__)

# SSDP constants
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900


class DLNAPlugin(SpeakerPlugin):
    """
    DLNA/UPnP speaker plugin.

    Discovers UPnP media renderers on the network using SSDP.
    """

    def __init__(self):
        self._discovery_timeout = 5
        self._devices: dict[str, Any] = {}
        self._device_locations: dict[str, str] = {}

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="dlna",
            name="DLNA/UPnP",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to DLNA renderers",
            author="Sonorium",
            dependencies=["async-upnp-client>=0.38.0", "aiohttp>=3.8.0"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        try:
            import aiohttp
            logger.info("DLNA plugin initialized")
            return True
        except ImportError:
            logger.warning("DLNA plugin: aiohttp not installed")
            return False

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._devices.clear()
        self._device_locations.clear()

    def set_config(self, config: dict) -> None:
        """Apply plugin configuration."""
        self._discovery_timeout = config.get("discovery_timeout", 5)

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover DLNA/UPnP media renderers using SSDP."""
        discovered = []

        try:
            import aiohttp

            logger.info("Starting DLNA/SSDP discovery...")

            search_targets = [
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                "urn:schemas-upnp-org:service:AVTransport:1",
            ]

            devices_found = {}

            async def fetch_device_info(location: str) -> dict:
                """Fetch device description XML."""
                try:
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as session:
                        async with session.get(location) as response:
                            if response.status == 200:
                                text = await response.text()
                                import re
                                info = {}

                                match = re.search(r'<friendlyName>([^<]+)</friendlyName>', text, re.IGNORECASE)
                                if match:
                                    info['friendlyName'] = match.group(1)

                                match = re.search(r'<modelName>([^<]+)</modelName>', text, re.IGNORECASE)
                                if match:
                                    info['modelName'] = match.group(1)

                                match = re.search(r'<manufacturer>([^<]+)</manufacturer>', text, re.IGNORECASE)
                                if match:
                                    info['manufacturer'] = match.group(1)

                                if 'MediaRenderer' in text or 'AVTransport' in text:
                                    info['is_renderer'] = True

                                return info
                except Exception as e:
                    logger.debug(f"Failed to fetch device info: {e}")
                return {}

            def ssdp_search(search_target: str) -> list[dict]:
                """Perform SSDP M-SEARCH."""
                responses = []

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(self._discovery_timeout / len(search_targets))

                search_msg = (
                    f"M-SEARCH * HTTP/1.1\r\n"
                    f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
                    f"MAN: \"ssdp:discover\"\r\n"
                    f"MX: 3\r\n"
                    f"ST: {search_target}\r\n"
                    f"\r\n"
                )

                try:
                    sock.sendto(search_msg.encode(), (SSDP_ADDR, SSDP_PORT))

                    while True:
                        try:
                            data, addr = sock.recvfrom(4096)
                            response_text = data.decode('utf-8', errors='ignore')

                            headers = {}
                            for line in response_text.split('\r\n'):
                                if ':' in line:
                                    key, value = line.split(':', 1)
                                    headers[key.upper().strip()] = value.strip()

                            if 'LOCATION' in headers:
                                headers['_addr'] = addr
                                responses.append(headers)
                        except socket.timeout:
                            break
                        except Exception:
                            break
                finally:
                    sock.close()

                return responses

            # Run SSDP searches
            loop = asyncio.get_event_loop()
            all_responses = []

            for st in search_targets:
                try:
                    responses = await loop.run_in_executor(None, ssdp_search, st)
                    all_responses.extend(responses)
                except Exception as e:
                    logger.warning(f"SSDP search failed: {e}")

            # Process unique devices
            for headers in all_responses:
                try:
                    location = headers.get('LOCATION', '')
                    usn = headers.get('USN', '')

                    if not location or location in devices_found:
                        continue

                    devices_found[location] = headers

                    parsed = urlparse(location)
                    host = parsed.hostname or ''
                    port = parsed.port or 80

                    device_details = await fetch_device_info(location)

                    server = headers.get('SERVER', '').lower()
                    is_media_device = (
                        device_details.get('is_renderer') or
                        'mediarenderer' in usn.lower() or
                        'avtransport' in usn.lower() or
                        'dlna' in server
                    )

                    if not is_media_device:
                        continue

                    if usn:
                        device_id = usn.split('::')[0].replace('uuid:', '')
                    else:
                        device_id = host.replace('.', '_')
                    speaker_id = f"dlna_{device_id[:20]}"

                    if any(s.id == speaker_id for s in discovered):
                        continue

                    speaker = DiscoveredSpeaker(
                        id=speaker_id,
                        name=device_details.get('friendlyName', f"DLNA ({host})"),
                        host=host,
                        port=port,
                        model=device_details.get('modelName', 'DLNA Renderer'),
                        manufacturer=device_details.get('manufacturer', 'Unknown'),
                        extra={
                            'usn': usn,
                            'location': location,
                        }
                    )

                    self._device_locations[speaker_id] = location
                    discovered.append(speaker)
                    logger.info(f"Found DLNA: {speaker.name} at {host}")

                except Exception as e:
                    logger.warning(f"Error processing DLNA device: {e}")

            logger.info(f"DLNA discovery found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"DLNA discovery error: {e}")

        return discovered

    async def _get_dmr_device(self, speaker_id: str) -> Optional[Any]:
        """Get or create a DMR device."""
        if speaker_id in self._devices:
            return self._devices[speaker_id]

        location = self._device_locations.get(speaker_id)
        if not location:
            logger.error(f"No DLNA location for {speaker_id}")
            return None

        try:
            from async_upnp_client.aiohttp import AiohttpRequester
            from async_upnp_client.client_factory import UpnpFactory
            from async_upnp_client.profiles.dlna import DmrDevice

            logger.info(f"Connecting to DLNA device at {location}...")

            requester = AiohttpRequester()
            factory = UpnpFactory(requester)
            device = await factory.async_create_device(location)

            dmr = DmrDevice(device, None)
            self._devices[speaker_id] = dmr

            logger.info(f"DLNA device created: {device.name}")
            return dmr

        except ImportError:
            logger.error("async-upnp-client not installed")
        except Exception as e:
            logger.error(f"DLNA connection error: {e}")

        return None

    def _create_didl_metadata(self, url: str, title: str = "Sonorium") -> str:
        """Create DIDL-Lite metadata XML."""
        safe_url = html.escape(url)
        safe_title = html.escape(title)

        return f'''<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
<item id="1" parentID="0" restricted="1">
<dc:title>{safe_title}</dc:title>
<upnp:class>object.item.audioItem.musicTrack</upnp:class>
<res protocolInfo="http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01">{safe_url}</res>
</item>
</DIDL-Lite>'''

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Play a URL on a DLNA device."""
        try:
            dmr = await self._get_dmr_device(speaker_id)
            if not dmr:
                return False

            logger.info(f"Starting DLNA playback on {speaker_id}: {url}")

            meta_data = self._create_didl_metadata(url)
            await dmr.async_set_transport_uri(url, 'Sonorium', meta_data=meta_data)
            await asyncio.sleep(0.5)
            await dmr.async_play()

            logger.info(f"DLNA device now playing")
            return True

        except ImportError:
            logger.error("async-upnp-client not installed")
            return False
        except Exception as e:
            logger.error(f"DLNA playback error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                return False

            await dmr.async_stop()
            logger.info(f"Stopped DLNA {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping DLNA: {e}")
            return False

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                dmr = await self._get_dmr_device(speaker_id)
                if not dmr:
                    return False

            await dmr.async_set_volume_level(max(0.0, min(1.0, volume)))
            return True

        except Exception as e:
            logger.warning(f"Error setting DLNA volume: {e}")
            return False

    async def stop_all(self) -> int:
        """Stop all DLNA speakers."""
        count = 0
        for speaker_id in list(self._devices.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count


# Plugin entry point
Plugin = DLNAPlugin
