"""
HEOS Speaker Plugin (Denon/Marantz)

Provides discovery and playback control for Denon and Marantz HEOS devices.
Uses pyheos library or raw telnet CLI commands on port 1255.

This is a TRUE plugin - deleting this folder removes HEOS support entirely.
"""

from __future__ import annotations

import asyncio
import json
import socket
import time
from pathlib import Path
from typing import Optional, Any
from urllib.parse import urlparse, quote

from sonorium.plugins.speaker_base import (
    SpeakerPlugin,
    NetworkSpeaker,
    SpeakerState,
)
from sonorium.obs import logger


class HEOSPlugin(SpeakerPlugin):
    """
    HEOS speaker plugin.

    Discovers Denon/Marantz HEOS devices on the network via SSDP and mDNS,
    and provides playback control using the HEOS CLI protocol (telnet port 1255).

    Supports:
    - Denon HEOS speakers and soundbars
    - Denon AV receivers with HEOS
    - Marantz HEOS speakers
    - Marantz AV receivers with HEOS
    """

    plugin_type: str = "speaker"

    # SSDP and HEOS constants
    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900
    HEOS_PORT = 1255

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Settings
        self._discovery_timeout = settings.get("discovery_timeout", 5)
        self._use_pyheos = settings.get("use_pyheos", True)

        # Active connections
        self._connections: dict[str, Any] = {}

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """
        Discover HEOS devices using SSDP and mDNS.

        Returns:
            List of discovered NetworkSpeaker objects
        """
        discovered = []

        try:
            logger.info("Starting HEOS discovery...")

            # Find HEOS hosts via SSDP
            heos_hosts = await self._find_heos_hosts_ssdp()

            if not heos_hosts:
                # Fallback to mDNS
                heos_hosts = await self._find_heos_hosts_mdns()

            if not heos_hosts:
                logger.info("No HEOS devices found via SSDP or mDNS")
                return discovered

            # Connect to one HEOS device and get all players
            for host in heos_hosts:
                try:
                    players = await self._get_heos_players(host)
                    if players:
                        for player in players:
                            speaker = self._create_speaker_from_player(player)
                            if speaker and not any(s.id == speaker.id for s in discovered):
                                discovered.append(speaker)
                        break  # Got players from one host
                except Exception as e:
                    logger.debug(f"Failed to get HEOS players from {host}: {e}")
                    continue

            logger.info(f"HEOS discovery found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"HEOS discovery error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return discovered

    async def _find_heos_hosts_ssdp(self) -> list[str]:
        """Find HEOS device IPs via SSDP."""
        hosts = []

        search_targets = [
            "urn:schemas-denon-com:device:ACT-Denon:1",
            "urn:schemas-upnp-org:device:MediaRenderer:1",
        ]

        def ssdp_search(search_target: str) -> list[str]:
            found = []
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(min(self._discovery_timeout / 2, 3))

            search_msg = (
                f"M-SEARCH * HTTP/1.1\r\n"
                f"HOST: {self.SSDP_ADDR}:{self.SSDP_PORT}\r\n"
                f"MAN: \"ssdp:discover\"\r\n"
                f"MX: 2\r\n"
                f"ST: {search_target}\r\n"
                f"\r\n"
            )

            try:
                sock.sendto(search_msg.encode(), (self.SSDP_ADDR, self.SSDP_PORT))

                while True:
                    try:
                        data, addr = sock.recvfrom(4096)
                        response = data.decode('utf-8', errors='ignore')

                        # Check for HEOS/Denon indicators
                        response_lower = response.lower()
                        if 'denon' in response_lower or 'heos' in response_lower or 'marantz' in response_lower:
                            for line in response.split('\r\n'):
                                if line.upper().startswith('LOCATION:'):
                                    location = line.split(':', 1)[1].strip()
                                    parsed = urlparse(location)
                                    if parsed.hostname and parsed.hostname not in found:
                                        found.append(parsed.hostname)
                                        logger.debug(f"HEOS SSDP found device at {parsed.hostname}")
                                    break
                    except socket.timeout:
                        break
            finally:
                sock.close()

            return found

        loop = asyncio.get_event_loop()
        for st in search_targets:
            try:
                found = await loop.run_in_executor(None, ssdp_search, st)
                hosts.extend([h for h in found if h not in hosts])
            except Exception as e:
                logger.debug(f"HEOS SSDP search for {st} failed: {e}")

        return hosts

    async def _find_heos_hosts_mdns(self) -> list[str]:
        """Find HEOS device IPs via mDNS."""
        hosts = []

        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

            class HeosListener(ServiceListener):
                def __init__(self):
                    self.hosts = []

                def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    try:
                        info = zc.get_service_info(type_, name, timeout=3000)
                        if info and info.addresses:
                            for addr in info.addresses:
                                ip = socket.inet_ntoa(addr)
                                if ip not in self.hosts:
                                    self.hosts.append(ip)
                                    logger.debug(f"HEOS mDNS found device at {ip}")
                    except Exception as e:
                        logger.debug(f"Error getting HEOS mDNS service info: {e}")

                def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass

                def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass

            def run_mdns_scan():
                zc = Zeroconf()
                listener = HeosListener()
                try:
                    browser = ServiceBrowser(zc, "_heos-audio._tcp.local.", listener)
                    time.sleep(min(self._discovery_timeout, 3))
                    return listener.hosts
                finally:
                    zc.close()

            loop = asyncio.get_event_loop()
            hosts = await loop.run_in_executor(None, run_mdns_scan)

        except ImportError:
            logger.debug("zeroconf not installed - HEOS mDNS discovery disabled")
        except Exception as e:
            logger.debug(f"HEOS mDNS discovery error: {e}")

        return hosts

    async def _get_heos_players(self, host: str) -> list[dict]:
        """Get all HEOS players via CLI telnet connection."""
        players = []

        try:
            # Try pyheos first
            if self._use_pyheos:
                try:
                    import pyheos
                    heos = await pyheos.Heos.create_and_connect(
                        host,
                        timeout=min(self._discovery_timeout, 10),
                        heart_beat=False
                    )
                    try:
                        player_dict = await heos.get_players(refresh=True)
                        for pid, player in player_dict.items():
                            players.append({
                                'pid': pid,
                                'name': player.name,
                                'model': player.model,
                                'ip': player.ip_address,
                                'version': player.version,
                            })
                        logger.info(f"HEOS pyheos found {len(players)} players via {host}")
                    finally:
                        await heos.disconnect()
                    return players
                except ImportError:
                    logger.debug("pyheos not installed, using raw telnet")

            # Fallback to raw telnet
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, self.HEOS_PORT),
                timeout=min(self._discovery_timeout, 5)
            )

            try:
                cmd = "heos://player/get_players\r\n"
                writer.write(cmd.encode())
                await writer.drain()

                response = await asyncio.wait_for(reader.read(8192), timeout=5)
                response_text = response.decode('utf-8', errors='ignore')

                for line in response_text.strip().split('\n'):
                    try:
                        data = json.loads(line)
                        if 'payload' in data and isinstance(data['payload'], list):
                            for p in data['payload']:
                                players.append({
                                    'pid': p.get('pid'),
                                    'name': p.get('name'),
                                    'model': p.get('model'),
                                    'ip': p.get('ip'),
                                    'version': p.get('version'),
                                })
                            break
                    except json.JSONDecodeError:
                        continue

                logger.info(f"HEOS telnet found {len(players)} players via {host}")

            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        except asyncio.TimeoutError:
            logger.debug(f"HEOS connection to {host} timed out")
        except ConnectionRefusedError:
            logger.debug(f"HEOS connection to {host} refused")
        except Exception as e:
            logger.debug(f"HEOS error connecting to {host}: {e}")

        return players

    def _create_speaker_from_player(self, player: dict) -> Optional[NetworkSpeaker]:
        """Create a NetworkSpeaker from HEOS player data."""
        pid = player.get('pid')
        ip = player.get('ip')

        if not pid or not ip:
            return None

        speaker_id = f"heos_{pid}"
        name = player.get('name', f"HEOS Device ({ip})")
        model = player.get('model')

        # Determine manufacturer from model
        manufacturer = "Denon"
        if model and 'marantz' in model.lower():
            manufacturer = "Marantz"

        return NetworkSpeaker(
            id=speaker_id,
            name=name,
            model=model or "HEOS Device",
            manufacturer=manufacturer,
            ip_address=ip,
            port=self.HEOS_PORT,
            state=SpeakerState.IDLE,
            volume=1.0,
            is_muted=False,
            capabilities=["volume"],
            extra={
                'pid': pid,
                'version': player.get('version'),
            }
        )

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Play a URL on a HEOS device.

        Uses the HEOS CLI play_stream command.

        Args:
            speaker_id: The speaker ID (heos_{pid})
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        speaker = self.get_speaker(speaker_id)
        if not speaker:
            logger.error(f"HEOS: Speaker not found: {speaker_id}")
            return False

        host = speaker.ip_address
        pid = speaker.extra.get('pid')

        if not pid:
            logger.error(f"HEOS: No pid in speaker_info for {speaker_id}")
            return False

        logger.info(f"HEOS: Starting stream to {speaker.name} (pid={pid}) at {host}")

        try:
            # Try pyheos first
            if self._use_pyheos:
                try:
                    import pyheos

                    heos = await pyheos.Heos.create_and_connect(
                        host,
                        timeout=10,
                        heart_beat=False
                    )

                    self._connections[speaker_id] = heos

                    players = await heos.get_players(refresh=True)
                    player = players.get(pid)

                    if not player:
                        for p in players.values():
                            if p.ip_address == host:
                                player = p
                                break

                    if not player:
                        logger.error(f"HEOS: Player {pid} not found in {list(players.keys())}")
                        await heos.disconnect()
                        return False

                    await player.play_url(url)

                    # Update state
                    speaker.state = SpeakerState.PLAYING
                    speaker.current_media = url
                    self._update_speaker(speaker)

                    logger.info(f"HEOS: {speaker.name} now playing {url}")
                    return True

                except ImportError:
                    logger.debug("pyheos not installed, using raw telnet")

            # Fallback to raw telnet
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, self.HEOS_PORT),
                timeout=10
            )

            self._connections[speaker_id] = (reader, writer)

            cmd = f"heos://browse/play_stream?pid={pid}&url={url}\r\n"
            logger.debug(f"HEOS: Sending command: {cmd.strip()}")

            writer.write(cmd.encode())
            await writer.drain()

            response = await asyncio.wait_for(reader.read(4096), timeout=5)
            response_text = response.decode('utf-8', errors='ignore')
            logger.debug(f"HEOS: Response: {response_text}")

            try:
                data = json.loads(response_text.strip())
                if data.get('heos', {}).get('result') == 'success':
                    speaker.state = SpeakerState.PLAYING
                    speaker.current_media = url
                    self._update_speaker(speaker)

                    logger.info(f"HEOS: {speaker.name} now playing {url}")
                    return True
                else:
                    error = data.get('heos', {}).get('message', 'Unknown error')
                    logger.error(f"HEOS: Command failed: {error}")
                    return False
            except json.JSONDecodeError:
                if 'error' not in response_text.lower():
                    speaker.state = SpeakerState.PLAYING
                    speaker.current_media = url
                    self._update_speaker(speaker)

                    logger.info(f"HEOS: {speaker.name} command sent (assuming success)")
                    return True
                else:
                    logger.error(f"HEOS error: {response_text}")
                    return False

        except asyncio.TimeoutError:
            logger.error(f"HEOS: Connection to {host} timed out")
            return False
        except ConnectionRefusedError:
            logger.error(f"HEOS: Connection to {host} refused")
            return False
        except Exception as e:
            logger.error(f"HEOS streaming error: {e}", exc_info=True)
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop HEOS playback."""
        try:
            conn = self._connections.get(speaker_id)

            if conn:
                # Check if it's a pyheos connection
                if hasattr(conn, 'disconnect'):
                    try:
                        await conn.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting pyheos: {e}")
                else:
                    # Raw telnet connection (reader, writer tuple)
                    try:
                        reader, writer = conn
                        writer.close()
                        await writer.wait_closed()
                    except Exception as e:
                        logger.warning(f"Error closing HEOS connection: {e}")

                del self._connections[speaker_id]

            # Update state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.IDLE
                speaker.current_media = None
                self._update_speaker(speaker)

            logger.info(f"Stopped HEOS {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping HEOS: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume on a HEOS device."""
        speaker = self.get_speaker(speaker_id)
        if not speaker:
            return False

        host = speaker.ip_address
        pid = speaker.extra.get('pid')

        if not pid:
            return False

        try:
            level = max(0.0, min(1.0, level))
            volume = int(level * 100)

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, self.HEOS_PORT),
                timeout=5
            )

            try:
                cmd = f"heos://player/set_volume?pid={pid}&level={volume}\r\n"
                writer.write(cmd.encode())
                await writer.drain()

                response = await asyncio.wait_for(reader.read(4096), timeout=5)

                speaker.volume = level
                self._update_speaker(speaker)

                logger.debug(f"Set HEOS {speaker_id} volume to {volume}%")
                return True

            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"Error setting HEOS volume: {e}")
            return False

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities."""
        return ["volume"]

    async def on_disable(self) -> None:
        """Clean up connections when disabled."""
        await super().on_disable()

        for speaker_id in list(self._connections.keys()):
            await self.stop(speaker_id)


# Plugin entry point
Plugin = HEOSPlugin
