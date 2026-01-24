"""
HEOS Speaker Plugin

Provides discovery and playback control for HEOS devices (Denon, Marantz)
using the HEOS CLI protocol on port 1255.

This is a TRUE plugin - deleting this folder removes HEOS support entirely.
"""

from __future__ import annotations

import asyncio
import socket
import json
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

# HEOS CLI port
HEOS_PORT = 1255

# SSDP constants
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900


class HEOSPlugin(SpeakerPlugin):
    """
    HEOS speaker plugin for Denon/Marantz devices.

    Discovers HEOS devices via SSDP and mDNS, controls them using
    the HEOS CLI protocol (telnet on port 1255) or pyheos library.
    """

    def __init__(self):
        self._discovery_timeout = 10
        self._devices: dict[str, dict] = {}
        self._connections: dict[str, Any] = {}

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="heos",
            name="HEOS (Denon/Marantz)",
            type=PluginType.SPEAKER,
            version="1.0.0",
            description="Stream audio to HEOS devices",
            author="Sonorium",
            dependencies=[],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin."""
        logger.info("HEOS plugin initialized")
        return True

    async def shutdown(self) -> None:
        """Clean up resources."""
        # Close any open connections
        for speaker_id, conn in list(self._connections.items()):
            try:
                if hasattr(conn, 'disconnect'):
                    await conn.disconnect()
                elif hasattr(conn, 'close'):
                    conn.close()
            except Exception:
                pass
        self._connections.clear()
        self._devices.clear()

    def set_config(self, config: dict) -> None:
        """Apply plugin configuration."""
        self._discovery_timeout = config.get("discovery_timeout", 10)

    async def _find_heos_hosts_ssdp(self, timeout: float) -> list[str]:
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
            sock.settimeout(min(timeout / 2, 3))

            search_msg = (
                f"M-SEARCH * HTTP/1.1\r\n"
                f"HOST: {SSDP_ADDR}:{SSDP_PORT}\r\n"
                f"MAN: \"ssdp:discover\"\r\n"
                f"MX: 2\r\n"
                f"ST: {search_target}\r\n"
                f"\r\n"
            )

            try:
                sock.sendto(search_msg.encode(), (SSDP_ADDR, SSDP_PORT))

                while True:
                    try:
                        data, addr = sock.recvfrom(4096)
                        response = data.decode('utf-8', errors='ignore')

                        # Check for HEOS/Denon indicators
                        if 'denon' in response.lower() or 'heos' in response.lower() or 'marantz' in response.lower():
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

    async def _find_heos_hosts_mdns(self, timeout: float) -> list[str]:
        """Find HEOS device IPs via mDNS."""
        hosts = []

        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            import time

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
                    time.sleep(min(timeout, 3))
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

    async def _get_heos_players(self, host: str, timeout: float) -> list[dict]:
        """Get all HEOS players via CLI telnet connection."""
        players = []

        try:
            # Try pyheos first (if available)
            try:
                import pyheos
                heos = await pyheos.Heos.create_and_connect(
                    host,
                    timeout=min(timeout, 10),
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
                asyncio.open_connection(host, HEOS_PORT),
                timeout=min(timeout, 5)
            )

            try:
                # Send get_players command
                cmd = "heos://player/get_players\r\n"
                writer.write(cmd.encode())
                await writer.drain()

                # Read response (JSON)
                response = await asyncio.wait_for(reader.read(8192), timeout=5)
                response_text = response.decode('utf-8', errors='ignore')

                # Parse JSON response
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

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover HEOS devices (Denon/Marantz)."""
        discovered = []

        try:
            logger.info("Starting HEOS discovery...")

            # Find HEOS hosts via SSDP
            heos_hosts = await self._find_heos_hosts_ssdp(timeout)

            if not heos_hosts:
                # Fallback: try mDNS
                heos_hosts = await self._find_heos_hosts_mdns(timeout)

            if not heos_hosts:
                logger.info("No HEOS devices found via SSDP or mDNS")
                return discovered

            # Connect to one HEOS device and get all players
            for host in heos_hosts:
                try:
                    players = await self._get_heos_players(host, timeout)
                    if players:
                        for player in players:
                            pid = player.get('pid')
                            if not pid:
                                continue

                            ip = player.get('ip')
                            if not ip:
                                continue

                            speaker_id = f"heos_{pid}"
                            name = player.get('name', f"HEOS Device ({ip})")
                            model = player.get('model')

                            # Determine manufacturer from model
                            manufacturer = "Denon"
                            if model and 'marantz' in model.lower():
                                manufacturer = "Marantz"

                            # Skip duplicates
                            if any(s.id == speaker_id for s in discovered):
                                continue

                            # Store device info
                            self._devices[speaker_id] = {
                                'pid': pid,
                                'host': ip,
                                'port': HEOS_PORT,
                                'version': player.get('version'),
                            }

                            speaker = DiscoveredSpeaker(
                                id=speaker_id,
                                name=name,
                                host=ip,
                                port=HEOS_PORT,
                                model=model,
                                manufacturer=manufacturer,
                                extra={
                                    'pid': pid,
                                    'version': player.get('version'),
                                }
                            )
                            discovered.append(speaker)
                            logger.info(f"Found HEOS: {name} at {ip}")
                        break  # Got players from one host
                except Exception as e:
                    logger.debug(f"Failed to get HEOS players from {host}: {e}")
                    continue

            logger.info(f"HEOS discovery found {len(discovered)} devices")

        except Exception as e:
            logger.error(f"HEOS discovery error: {e}")

        return discovered

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Play a URL on a HEOS device."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                host = kwargs.get('host')
                pid = kwargs.get('pid') or kwargs.get('extra', {}).get('pid')
                if not host or not pid:
                    logger.error(f"HEOS: No device info for {speaker_id}")
                    return False
                device = {'host': host, 'pid': pid, 'port': HEOS_PORT}

            host = device['host']
            pid = device['pid']
            speaker_name = kwargs.get('name', host)

            logger.info(f"HEOS: Starting stream to {speaker_name} (pid={pid}) at {host}")

            # Try pyheos first
            try:
                import pyheos

                heos = await pyheos.Heos.create_and_connect(
                    host,
                    timeout=10,
                    heart_beat=False
                )

                self._connections[speaker_id] = heos

                # Get the player
                players = await heos.get_players(refresh=True)
                player = players.get(pid)

                if not player:
                    # Try to find by IP
                    for p in players.values():
                        if p.ip_address == host:
                            player = p
                            break

                if not player:
                    logger.error(f"HEOS player {pid} not found")
                    await heos.disconnect()
                    return False

                # Play the stream URL
                await player.play_url(url)

                logger.info(f"HEOS: {speaker_name} now playing {url}")
                return True

            except ImportError:
                logger.debug("pyheos not installed, using raw telnet")

            # Fallback to raw telnet
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, HEOS_PORT),
                timeout=10
            )

            self._connections[speaker_id] = writer

            # Send play_stream command
            cmd = f"heos://browse/play_stream?pid={pid}&url={url}\r\n"
            logger.debug(f"HEOS: Sending command: {cmd.strip()}")

            writer.write(cmd.encode())
            await writer.drain()

            # Read response
            response = await asyncio.wait_for(reader.read(4096), timeout=5)
            response_text = response.decode('utf-8', errors='ignore')
            logger.debug(f"HEOS: Response: {response_text}")

            # Check for success
            try:
                data = json.loads(response_text.strip())
                if data.get('heos', {}).get('result') == 'success':
                    logger.info(f"HEOS: {speaker_name} now playing {url}")
                    return True
                else:
                    error = data.get('heos', {}).get('message', 'Unknown error')
                    logger.error(f"HEOS: Command failed: {error}")
                    return False
            except json.JSONDecodeError:
                # Some devices return non-JSON, assume success if no error
                if 'error' not in response_text.lower():
                    logger.info(f"HEOS: {speaker_name} command sent (assuming success)")
                    return True
                else:
                    logger.error(f"HEOS error: {response_text}")
                    return False

        except asyncio.TimeoutError:
            logger.error(f"HEOS connection timed out")
            return False
        except ConnectionRefusedError:
            logger.error(f"HEOS connection refused")
            return False
        except Exception as e:
            logger.error(f"HEOS streaming error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop HEOS playback."""
        conn = self._connections.pop(speaker_id, None)
        if conn:
            try:
                if hasattr(conn, 'disconnect'):
                    await conn.disconnect()
                elif hasattr(conn, 'close'):
                    conn.close()
                    if hasattr(conn, 'wait_closed'):
                        await conn.wait_closed()
                logger.info(f"Stopped HEOS {speaker_id}")
                return True
            except Exception as e:
                logger.warning(f"Error stopping HEOS: {e}")
                return False
        return True

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set volume on a HEOS device."""
        # HEOS volume control requires active connection
        logger.warning("HEOS volume control not yet fully implemented")
        return False

    async def stop_all(self) -> int:
        """Stop all HEOS speakers."""
        count = 0
        for speaker_id in list(self._connections.keys()):
            if await self.stop(speaker_id):
                count += 1
        return count


# Plugin entry point
Plugin = HEOSPlugin
