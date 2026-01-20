"""
DLNA/UPnP Speaker Plugin

Discovers and controls DLNA/UPnP media renderers on the local network.

Requirements:
    pip install async-upnp-client

Uses UPnP SSDP for discovery and AVTransport service for playback control.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from sonorium.plugins.speaker_base import SpeakerPlugin, NetworkSpeaker, SpeakerState
from sonorium.obs import logger

# Try to import async_upnp_client
try:
    from async_upnp_client.aiohttp import AiohttpRequester
    from async_upnp_client.client_factory import UpnpFactory
    from async_upnp_client.search import async_search
    from async_upnp_client.const import SsdpSource
    UPNP_AVAILABLE = True
except ImportError:
    UPNP_AVAILABLE = False


class DLNAPlugin(SpeakerPlugin):
    """
    DLNA/UPnP speaker plugin.

    Discovers media renderers on the network and streams audio to them.
    Supports any UPnP AVTransport compatible device:
    - DLNA speakers
    - Network receivers (Denon, Marantz, etc.)
    - Smart TVs
    - Media players
    """

    id = "dlna"
    name = "DLNA/UPnP"
    version = "1.0.0"
    description = "Stream audio to DLNA/UPnP compatible speakers and media renderers"
    author = "Sonorium"
    builtin = True

    # DLNA service type for media renderers
    MEDIA_RENDERER_URN = "urn:schemas-upnp-org:device:MediaRenderer:1"
    AV_TRANSPORT_URN = "urn:schemas-upnp-org:service:AVTransport:1"
    RENDERING_CONTROL_URN = "urn:schemas-upnp-org:service:RenderingControl:1"

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # UPnP factory for creating device proxies
        self._factory: Optional[UpnpFactory] = None
        self._requester = None

        # Connected devices
        self._devices: Dict[str, Any] = {}

        # Discovery lock
        self._discovery_lock = asyncio.Lock()

    async def on_load(self) -> None:
        """Initialize UPnP client."""
        if not UPNP_AVAILABLE:
            logger.warning(
                f"{self.name}: async-upnp-client not installed. "
                "Install with: pip install async-upnp-client"
            )
            return

        try:
            self._requester = AiohttpRequester()
            self._factory = UpnpFactory(self._requester)
            logger.debug(f"{self.name}: UPnP client initialized")
        except Exception as e:
            logger.error(f"{self.name}: Failed to initialize UPnP client: {e}")

    async def on_unload(self) -> None:
        """Clean up connections."""
        self._devices.clear()
        if self._requester:
            await self._requester.async_close()
            self._requester = None
        self._factory = None

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """Discover DLNA media renderers on the network."""
        if not UPNP_AVAILABLE or not self._factory:
            return []

        async with self._discovery_lock:
            speakers = []
            timeout = self.get_setting("discovery_timeout", 5)

            try:
                # Search for media renderers
                async def on_device(headers):
                    try:
                        location = headers.get("location")
                        if not location:
                            return

                        # Create device from location
                        device = await self._factory.async_create_device(location)

                        # Check if it's a media renderer
                        if device.device_type != self.MEDIA_RENDERER_URN:
                            return

                        # Get device info
                        udn = device.udn
                        friendly_name = device.friendly_name or "DLNA Speaker"
                        manufacturer = device.manufacturer or "Unknown"
                        model = device.model_name or "Media Renderer"

                        # Extract IP from location
                        from urllib.parse import urlparse
                        parsed = urlparse(location)
                        ip_address = parsed.hostname or ""

                        speaker = NetworkSpeaker(
                            id=udn,
                            name=friendly_name,
                            model=model,
                            manufacturer=manufacturer,
                            ip_address=ip_address,
                            port=parsed.port or 0,
                            state=SpeakerState.IDLE,
                            capabilities=self._get_device_capabilities(device),
                            extra={
                                "location": location,
                                "udn": udn,
                            }
                        )
                        speakers.append(speaker)

                        # Store device for later use
                        self._devices[udn] = device

                    except Exception as e:
                        logger.debug(f"Error processing DLNA device: {e}")

                # Run SSDP search
                await async_search(
                    async_callback=on_device,
                    timeout=timeout,
                    service_type=self.MEDIA_RENDERER_URN,
                )

            except Exception as e:
                logger.error(f"{self.name}: Discovery error: {e}")

            return speakers

    def _get_device_capabilities(self, device) -> list[str]:
        """Get capabilities from device services."""
        capabilities = []

        # Check for AVTransport (basic playback)
        if device.has_service(self.AV_TRANSPORT_URN):
            capabilities.extend(["play", "stop", "pause"])

        # Check for RenderingControl (volume)
        if device.has_service(self.RENDERING_CONTROL_URN):
            capabilities.extend(["volume", "mute"])

        return capabilities

    async def _get_device(self, speaker_id: str) -> Optional[Any]:
        """Get a device by ID, reconnecting if needed."""
        if speaker_id in self._devices:
            return self._devices[speaker_id]

        # Try to refresh speakers to find the device
        await self.refresh_speakers()
        return self._devices.get(speaker_id)

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """Play a URL on a DLNA renderer."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            logger.error(f"{self.name}: Speaker {speaker_id} not found")
            return False

        try:
            # Get AVTransport service
            av_transport = device.service(self.AV_TRANSPORT_URN)
            if not av_transport:
                logger.error(f"{self.name}: No AVTransport service")
                return False

            # Set the transport URI
            await av_transport.action("SetAVTransportURI").async_call(
                InstanceID=0,
                CurrentURI=url,
                CurrentURIMetaData=""
            )

            # Start playback
            await av_transport.action("Play").async_call(
                InstanceID=0,
                Speed="1"
            )

            logger.info(f"{self.name}: Playing {url} on {speaker_id}")
            return True

        except Exception as e:
            logger.error(f"{self.name}: Play failed: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a DLNA renderer."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            av_transport = device.service(self.AV_TRANSPORT_URN)
            if not av_transport:
                return False

            await av_transport.action("Stop").async_call(InstanceID=0)
            return True

        except Exception as e:
            logger.error(f"{self.name}: Stop failed: {e}")
            return False

    async def pause(self, speaker_id: str) -> bool:
        """Pause playback."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            av_transport = device.service(self.AV_TRANSPORT_URN)
            if not av_transport:
                return False

            await av_transport.action("Pause").async_call(InstanceID=0)
            return True

        except Exception as e:
            logger.error(f"{self.name}: Pause failed: {e}")
            return False

    async def resume(self, speaker_id: str) -> bool:
        """Resume playback."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            av_transport = device.service(self.AV_TRANSPORT_URN)
            if not av_transport:
                return False

            await av_transport.action("Play").async_call(
                InstanceID=0,
                Speed="1"
            )
            return True

        except Exception as e:
            logger.error(f"{self.name}: Resume failed: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume (0.0-1.0)."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            rendering_control = device.service(self.RENDERING_CONTROL_URN)
            if not rendering_control:
                return False

            # DLNA uses 0-100 scale
            volume = int(max(0, min(100, level * 100)))
            await rendering_control.action("SetVolume").async_call(
                InstanceID=0,
                Channel="Master",
                DesiredVolume=volume
            )

            # Update cached speaker
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.volume = level
                self._update_speaker(speaker)

            return True

        except Exception as e:
            logger.error(f"{self.name}: Volume failed: {e}")
            return False

    async def mute(self, speaker_id: str, muted: bool) -> bool:
        """Mute/unmute."""
        if not UPNP_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            rendering_control = device.service(self.RENDERING_CONTROL_URN)
            if not rendering_control:
                return False

            await rendering_control.action("SetMute").async_call(
                InstanceID=0,
                Channel="Master",
                DesiredMute=muted
            )

            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.is_muted = muted
                self._update_speaker(speaker)

            return True

        except Exception as e:
            logger.error(f"{self.name}: Mute failed: {e}")
            return False

    async def get_speaker_state(self, speaker_id: str) -> Optional[SpeakerState]:
        """Get current speaker state."""
        if not UPNP_AVAILABLE:
            return None

        device = await self._get_device(speaker_id)
        if not device:
            return SpeakerState.OFFLINE

        try:
            av_transport = device.service(self.AV_TRANSPORT_URN)
            if not av_transport:
                return SpeakerState.OFFLINE

            result = await av_transport.action("GetTransportInfo").async_call(
                InstanceID=0
            )

            state = result.get("CurrentTransportState", "").upper()
            if state in ("PLAYING", "TRANSITIONING"):
                return SpeakerState.PLAYING
            elif state == "PAUSED_PLAYBACK":
                return SpeakerState.PAUSED
            elif state == "NO_MEDIA_PRESENT":
                return SpeakerState.IDLE
            else:
                return SpeakerState.IDLE

        except Exception:
            return SpeakerState.OFFLINE

    def get_capabilities(self) -> list[str]:
        """DLNA supports volume, mute, pause, resume."""
        return ["volume", "mute", "pause", "resume"]

    def get_settings_schema(self) -> dict:
        """Plugin settings."""
        return {
            "discovery_timeout": {
                "type": "number",
                "default": 5,
                "label": "Discovery Timeout (seconds)",
                "min": 1,
                "max": 30
            },
            "auto_reconnect": {
                "type": "boolean",
                "default": True,
                "label": "Auto-reconnect on disconnect"
            }
        }
