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
from pathlib import Path
from typing import Optional, Any
from urllib.parse import urlparse

from sonorium.plugins.speaker_base import (
    SpeakerPlugin,
    NetworkSpeaker,
    SpeakerState,
)
from sonorium.obs import logger


class DLNAPlugin(SpeakerPlugin):
    """
    DLNA/UPnP speaker plugin.

    Discovers UPnP media renderers on the network using SSDP and provides
    playback control using the async-upnp-client library.

    Supports:
    - DLNA-certified devices
    - UPnP AV media renderers
    - Many smart speakers (Arylic, Linkplay, etc.)
    """

    plugin_type: str = "speaker"

    # SSDP constants
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Settings
        self._discovery_timeout = settings.get("discovery_timeout", 5)
        self._include_all = settings.get("include_all_devices", False)

        # Device cache (DMR objects)
        self._devices: dict[str, Any] = {}
        self._device_locations: dict[str, str] = {}

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """
        Discover DLNA/UPnP media renderers using SSDP.

        Returns:
            List of discovered NetworkSpeaker objects
        """
        discovered = []

        try:
            import aiohttp

            logger.info("Starting DLNA/SSDP discovery...")

            # Search targets for media renderers
            search_targets = [
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                "urn:schemas-upnp-org:service:AVTransport:1",
            ]
            if self._include_all:
                search_targets.append("ssdp:all")

            devices_found = {}

            async def fetch_device_info(location: str) -> dict:
                """Fetch device description XML to get friendly name and model."""
                try:
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as session:
                        async with session.get(location) as response:
                            if response.status == 200:
                                text = await response.text()
                                import re
                                info = {}

                                # Extract friendlyName
                                match = re.search(
                                    r'<friendlyName>([^<]+)</friendlyName>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['friendlyName'] = match.group(1)

                                # Extract modelName
                                match = re.search(
                                    r'<modelName>([^<]+)</modelName>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['modelName'] = match.group(1)

                                # Extract manufacturer
                                match = re.search(
                                    r'<manufacturer>([^<]+)</manufacturer>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['manufacturer'] = match.group(1)

                                # Check if it's a media renderer
                                if 'MediaRenderer' in text or 'AVTransport' in text:
                                    info['is_renderer'] = True

                                return info
                except Exception as e:
                    logger.debug(f"Failed to fetch device info from {location}: {e}")
                return {}

            def ssdp_search(search_target: str) -> list[dict]:
                """Perform SSDP M-SEARCH and collect responses."""
                responses = []

                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(self._discovery_timeout / len(search_targets))

                search_msg = (
                    f"M-SEARCH * HTTP/1.1\r\n"
                    f"HOST: {self.SSDP_ADDR}:{self.SSDP_PORT}\r\n"
                    f"MAN: \"ssdp:discover\"\r\n"
                    f"MX: 3\r\n"
                    f"ST: {search_target}\r\n"
                    f"\r\n"
                )

                try:
                    sock.sendto(search_msg.encode(), (self.SSDP_ADDR, self.SSDP_PORT))
                    logger.debug(f"Sent SSDP search for {search_target}")

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
                                logger.debug(
                                    f"SSDP response from {addr}: "
                                    f"{headers.get('LOCATION', 'no location')}"
                                )
                        except socket.timeout:
                            break
                        except Exception as e:
                            logger.debug(f"Error receiving SSDP response: {e}")
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
                    logger.warning(f"SSDP search for {st} failed: {e}")

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

                    # Check if device is a media renderer
                    server = headers.get('SERVER', '').lower()
                    is_media_device = (
                        device_details.get('is_renderer') or
                        'mediarenderer' in usn.lower() or
                        'avtransport' in usn.lower() or
                        'arylic' in server or
                        'linkplay' in server or
                        'dlna' in server
                    )

                    if not is_media_device and not self._include_all:
                        continue

                    # Create speaker ID
                    if usn:
                        device_id = usn.split('::')[0].replace('uuid:', '')
                    else:
                        device_id = host.replace('.', '_')
                    speaker_id = f"dlna_{device_id[:20]}"

                    # Skip duplicates
                    if any(s.id == speaker_id for s in discovered):
                        continue

                    name = device_details.get('friendlyName', f"DLNA Device ({host})")
                    model = device_details.get('modelName')
                    manufacturer = device_details.get(
                        'manufacturer',
                        headers.get('SERVER', '').split('/')[0]
                    )

                    speaker = NetworkSpeaker(
                        id=speaker_id,
                        name=name,
                        model=model or "DLNA Renderer",
                        manufacturer=manufacturer or "Unknown",
                        ip_address=host,
                        port=port,
                        state=SpeakerState.IDLE,
                        volume=1.0,
                        is_muted=False,
                        capabilities=["volume"],
                        extra={
                            'usn': usn,
                            'location': location,
                            'server': headers.get('SERVER', ''),
                        }
                    )

                    self._device_locations[speaker_id] = location
                    discovered.append(speaker)
                    logger.info(
                        f"Found DLNA: {speaker.name} "
                        f"({model or 'unknown model'}) at {speaker.ip_address}"
                    )

                except Exception as e:
                    logger.warning(f"Error processing DLNA device: {e}")

            logger.info(f"DLNA discovery found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"DLNA discovery error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return discovered

    async def _get_dmr_device(self, speaker_id: str) -> Optional[Any]:
        """
        Get or create a DMR (Digital Media Renderer) device.

        Args:
            speaker_id: The speaker ID

        Returns:
            DmrDevice object or None
        """
        if speaker_id in self._devices:
            return self._devices[speaker_id]

        location = self._device_locations.get(speaker_id)
        if not location:
            speaker = self.get_speaker(speaker_id)
            if speaker:
                location = speaker.extra.get('location')

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

    def _create_didl_metadata(self, stream_url: str, title: str = "Sonorium") -> str:
        """Create DIDL-Lite metadata XML for DLNA streaming."""
        safe_url = html.escape(stream_url)
        safe_title = html.escape(title)

        return f'''<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
<item id="1" parentID="0" restricted="1">
<dc:title>{safe_title}</dc:title>
<upnp:class>object.item.audioItem.musicTrack</upnp:class>
<res protocolInfo="http-get:*:audio/mpeg:DLNA.ORG_PN=MP3;DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000">{safe_url}</res>
</item>
</DIDL-Lite>'''

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Play a URL on a DLNA device.

        Args:
            speaker_id: The speaker ID
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        try:
            dmr = await self._get_dmr_device(speaker_id)
            if not dmr:
                return False

            logger.info(f"Starting DLNA playback on {speaker_id}...")
            logger.info(f"Setting transport URI: {url}")

            meta_data = self._create_didl_metadata(url, 'Sonorium')
            logger.debug(f"DIDL metadata: {meta_data}")

            await dmr.async_set_transport_uri(url, 'Sonorium', meta_data=meta_data)
            await asyncio.sleep(0.5)

            logger.info(f"DLNA transport state after SetAVTransportURI: {dmr.transport_state}")

            await dmr.async_play()
            await asyncio.sleep(0.5)

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.PLAYING
                speaker.current_media = url
                self._update_speaker(speaker)

            logger.info(f"DLNA device now playing {url}")
            logger.info(f"DLNA transport state after Play: {dmr.transport_state}")
            return True

        except ImportError:
            logger.error("async-upnp-client not installed")
            return False
        except Exception as e:
            logger.error(f"DLNA playback error: {e}", exc_info=True)
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                logger.warning(f"DLNA device not connected: {speaker_id}")
                return False

            await dmr.async_stop()

            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.IDLE
                speaker.current_media = None
                self._update_speaker(speaker)

            logger.info(f"Stopped DLNA {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping DLNA: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                dmr = await self._get_dmr_device(speaker_id)
                if not dmr:
                    return False

            level = max(0.0, min(1.0, level))
            volume = int(level * 100)

            await dmr.async_set_volume_level(level)

            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.volume = level
                self._update_speaker(speaker)

            logger.debug(f"Set DLNA {speaker_id} volume to {volume}%")
            return True

        except Exception as e:
            logger.warning(f"Error setting DLNA volume: {e}")
            return False

    async def pause(self, speaker_id: str) -> bool:
        """Pause playback on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                return False

            await dmr.async_pause()

            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.PAUSED
                self._update_speaker(speaker)

            return True
        except Exception as e:
            logger.warning(f"Error pausing DLNA: {e}")
            return False

    async def resume(self, speaker_id: str) -> bool:
        """Resume playback on a DLNA device."""
        try:
            dmr = self._devices.get(speaker_id)
            if not dmr:
                return False

            await dmr.async_play()

            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.PLAYING
                self._update_speaker(speaker)

            return True
        except Exception as e:
            logger.warning(f"Error resuming DLNA: {e}")
            return False

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities."""
        return ["volume", "pause", "resume"]

    def get_settings_schema(self) -> dict:
        """Plugin settings."""
        return {
            "discovery_timeout": {
                "type": "number",
                "default": 10,
                "label": "Discovery Timeout (seconds)",
                "description": "How long to wait for DLNA/SSDP devices to respond",
                "min": 3,
                "max": 60
            },
            "scan_interval": {
                "type": "number",
                "default": 5,
                "label": "Scan Interval (seconds)",
                "description": "How long to scan for devices during discovery",
                "min": 2,
                "max": 30
            }
        }


# Plugin entry point
Plugin = DLNAPlugin
