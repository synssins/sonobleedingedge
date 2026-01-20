"""
Linkplay/Arylic Speaker Plugin

Provides discovery and playback control for Linkplay and Arylic devices via HTTP API.
These devices often don't respond reliably to SSDP but have a description.xml on port 49152.

API Reference: https://developer.arylic.com/httpapi/

This is a TRUE plugin - deleting this folder removes Linkplay support entirely.
"""

from __future__ import annotations

import asyncio
import re
import socket
from pathlib import Path
from typing import Optional, Any

from sonorium.plugins.speaker_base import (
    SpeakerPlugin,
    NetworkSpeaker,
    SpeakerState,
)
from sonorium.obs import logger


class LinkplayPlugin(SpeakerPlugin):
    """
    Linkplay/Arylic speaker plugin.

    Discovers Linkplay devices by probing the local subnet on port 49152,
    and provides playback control via the Linkplay HTTP API.

    Supports:
    - Arylic speakers (A50+, Up2Stream, etc.)
    - Linkplay-based devices
    - Up2Stream modules
    """

    plugin_type: str = "speaker"

    # Linkplay port
    LINKPLAY_PORT = 49152

    # Known Linkplay/Arylic patterns
    LINKPLAY_PATTERNS = ['arylic', 'linkplay', 'up2stream', 'a50', 'a30', 'office_c']

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Settings
        self._discovery_timeout = settings.get("discovery_timeout", 5)
        self._scan_subnet = settings.get("scan_subnet", True)

        # Active sessions
        self._active_hosts: dict[str, str] = {}

    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """
        Discover Linkplay devices by probing the local subnet.

        Returns:
            List of discovered NetworkSpeaker objects
        """
        discovered = []

        if not self._scan_subnet:
            return discovered

        try:
            import aiohttp

            logger.info("Starting Linkplay direct probe discovery...")

            local_ip = self._get_local_ip()
            if not local_ip:
                logger.warning("Could not determine local IP for Linkplay scan")
                return discovered

            subnet_prefix = '.'.join(local_ip.split('.')[:3])
            logger.info(f"Scanning subnet {subnet_prefix}.0/24 for Linkplay devices...")

            async def probe_host(host: str) -> Optional[NetworkSpeaker]:
                """Probe a single host for Linkplay device."""
                url = f"http://{host}:{self.LINKPLAY_PORT}/description.xml"
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
                                match = re.search(
                                    r'<friendlyName>([^<]+)</friendlyName>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['friendlyName'] = match.group(1)

                                match = re.search(
                                    r'<modelName>([^<]+)</modelName>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['modelName'] = match.group(1)

                                match = re.search(
                                    r'<manufacturer>([^<]+)</manufacturer>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['manufacturer'] = match.group(1)

                                match = re.search(
                                    r'<UDN>uuid:([^<]+)</UDN>',
                                    text, re.IGNORECASE
                                )
                                if match:
                                    info['uuid'] = match.group(1)

                                # Create speaker
                                device_id = info.get('uuid', host.replace('.', '_'))[:20]
                                speaker_id = f"linkplay_{device_id}"

                                name = info.get('friendlyName', f"Linkplay ({host})")
                                model = info.get('modelName')
                                manufacturer = info.get('manufacturer', 'Linkplay')

                                speaker = NetworkSpeaker(
                                    id=speaker_id,
                                    name=name,
                                    model=model or "Linkplay Device",
                                    manufacturer=manufacturer,
                                    ip_address=host,
                                    port=self.LINKPLAY_PORT,
                                    state=SpeakerState.IDLE,
                                    volume=1.0,
                                    is_muted=False,
                                    capabilities=["volume"],
                                    extra={
                                        'location': url,
                                        'uuid': info.get('uuid', ''),
                                    }
                                )
                                logger.info(f"Found Linkplay: {name} ({model}) at {host}")
                                return speaker

                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

                return None

            # Probe all hosts in batches
            BATCH_SIZE = 50
            all_hosts = [f"{subnet_prefix}.{i}" for i in range(1, 255)]

            for batch_start in range(0, len(all_hosts), BATCH_SIZE):
                batch = all_hosts[batch_start:batch_start + BATCH_SIZE]
                tasks = [probe_host(host) for host in batch]
                results = await asyncio.gather(*tasks)

                for speaker in results:
                    if speaker and not any(s.id == speaker.id for s in discovered):
                        discovered.append(speaker)

            logger.info(f"Linkplay probe found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"Linkplay discovery error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return discovered

    def is_linkplay_device(self, speaker: NetworkSpeaker) -> bool:
        """Check if a speaker is a Linkplay/Arylic device."""
        name = speaker.name.lower()
        manufacturer = speaker.manufacturer.lower() if speaker.manufacturer else ""
        model = speaker.model.lower() if speaker.model else ""

        for pattern in self.LINKPLAY_PATTERNS:
            if pattern in name or pattern in manufacturer or pattern in model:
                return True

        return False

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Play a URL on a Linkplay device via HTTP API.

        Args:
            speaker_id: The speaker ID
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        speaker = self.get_speaker(speaker_id)
        if not speaker:
            logger.error(f"Linkplay: Speaker not found: {speaker_id}")
            return False

        host = speaker.ip_address
        logger.info(f"Linkplay HTTP: Starting stream to {speaker.name} at {host}")

        try:
            import aiohttp

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                # Verify device responds
                status_url = f"http://{host}/httpapi.asp?command=getStatusEx"
                try:
                    async with session.get(status_url) as resp:
                        if resp.status == 200:
                            import json
                            try:
                                status = json.loads(await resp.text())
                                device_name = status.get('DeviceName', 'Unknown')
                                logger.info(f"Linkplay HTTP: Device confirmed: {device_name}")
                            except json.JSONDecodeError:
                                logger.warning("Linkplay HTTP: Could not parse status")
                except Exception as e:
                    logger.warning(f"Linkplay HTTP: Status check failed: {e}")

                # Send play command
                play_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:play:{url}"
                logger.info(f"Linkplay HTTP: Sending play command")

                async with session.get(play_url) as resp:
                    response_text = await resp.text()
                    logger.info(f"Linkplay HTTP: Play response: {response_text}")

                    if response_text.strip() == "OK":
                        self._active_hosts[speaker_id] = host

                        speaker.state = SpeakerState.PLAYING
                        speaker.current_media = url
                        self._update_speaker(speaker)

                        logger.info(f"Linkplay HTTP: {speaker.name} now playing {url}")
                        return True
                    else:
                        logger.error(f"Linkplay HTTP: Play failed: {response_text}")
                        return False

        except Exception as e:
            logger.error(f"Linkplay HTTP error: {e}", exc_info=True)
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop Linkplay playback."""
        try:
            host = self._active_hosts.get(speaker_id)
            if host:
                try:
                    import aiohttp

                    stop_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:stop"

                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as session:
                        async with session.get(stop_url) as resp:
                            logger.info(f"Linkplay HTTP: Stop command sent to {host}")

                except Exception as e:
                    logger.warning(f"Linkplay HTTP: Error stopping: {e}")

                del self._active_hosts[speaker_id]

            # Update state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.IDLE
                speaker.current_media = None
                self._update_speaker(speaker)

            logger.info(f"Stopped Linkplay {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping Linkplay: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume on a Linkplay device."""
        speaker = self.get_speaker(speaker_id)
        if not speaker:
            return False

        host = speaker.ip_address

        try:
            import aiohttp

            level = max(0.0, min(1.0, level))
            volume = int(level * 100)

            vol_url = f"http://{host}/httpapi.asp?command=setPlayerCmd:vol:{volume}"

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                async with session.get(vol_url) as resp:
                    if resp.status == 200:
                        speaker.volume = level
                        self._update_speaker(speaker)

                        logger.debug(f"Set Linkplay {speaker_id} volume to {volume}%")
                        return True

            return False

        except Exception as e:
            logger.warning(f"Error setting Linkplay volume: {e}")
            return False

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities."""
        return ["volume"]


# Plugin entry point
Plugin = LinkplayPlugin
