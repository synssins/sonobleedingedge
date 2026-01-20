"""
AirPlay Speaker Plugin

Discovers and controls AirPlay compatible speakers on the local network.

Requirements:
    pip install pyatv

Uses RAOP (Remote Audio Output Protocol) for streaming to AirPlay devices.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from sonorium.plugins.speaker_base import SpeakerPlugin, NetworkSpeaker, SpeakerState
from sonorium.obs import logger

# Try to import pyatv
try:
    import pyatv
    from pyatv.const import Protocol, DeviceState
    PYATV_AVAILABLE = True
except ImportError:
    PYATV_AVAILABLE = False
    pyatv = None


class AirPlayPlugin(SpeakerPlugin):
    """
    AirPlay speaker plugin using pyatv.

    Discovers AirPlay devices on the network and streams audio to them.
    Supports:
    - Apple TV
    - HomePod / HomePod mini
    - AirPlay-enabled speakers
    - AirPlay 1 and AirPlay 2 devices
    """

    id = "airplay"
    name = "AirPlay"
    version = "1.0.0"
    description = "Stream audio to AirPlay compatible speakers and devices"
    author = "Sonorium"
    builtin = True

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Connected AirPlay devices
        self._atv_devices: Dict[str, Any] = {}  # Stores pyatv.interface.AppleTV
        self._device_configs: Dict[str, Any] = {}  # Stores pyatv.conf.AppleTV

        # Discovery lock
        self._discovery_lock = asyncio.Lock()

    async def on_load(self) -> None:
        """Check for pyatv availability."""
        if not PYATV_AVAILABLE:
            logger.warning(
                f"{self.name}: pyatv not installed. "
                "Install with: pip install pyatv"
            )

    async def on_unload(self) -> None:
        """Clean up connections."""
        await self._disconnect_all()

    async def _disconnect_all(self) -> None:
        """Disconnect from all AirPlay devices."""
        for device in self._atv_devices.values():
            try:
                device.close()
            except Exception:
                pass
        self._atv_devices.clear()
        self._device_configs.clear()

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """Discover AirPlay speakers on the network."""
        if not PYATV_AVAILABLE:
            return []

        async with self._discovery_lock:
            speakers = []
            timeout = self.get_setting("discovery_timeout", 5)

            try:
                # Discover AirPlay devices
                atvs = await pyatv.scan(
                    asyncio.get_event_loop(),
                    timeout=timeout,
                    protocol=Protocol.AirPlay
                )

                for atv_config in atvs:
                    try:
                        # Get device identifier
                        identifier = atv_config.identifier or str(atv_config.address)

                        # Determine device capabilities
                        capabilities = ["volume"]
                        services = [str(s.protocol) for s in atv_config.services]

                        # Check for supported protocols
                        has_raop = any("raop" in s.lower() for s in services)
                        has_airplay = any("airplay" in s.lower() for s in services)

                        # Get device type/model from services
                        model = "AirPlay Speaker"
                        if has_raop and has_airplay:
                            model = "AirPlay 2 Speaker"
                        elif has_raop:
                            model = "AirPlay 1 Speaker"

                        speaker = NetworkSpeaker(
                            id=identifier,
                            name=atv_config.name or "AirPlay Device",
                            model=model,
                            manufacturer="Apple/Compatible",
                            ip_address=str(atv_config.address),
                            port=7000,  # Default AirPlay port
                            state=SpeakerState.IDLE,
                            capabilities=capabilities,
                            extra={
                                "identifier": identifier,
                                "services": services,
                                "device_info": atv_config.device_info.__dict__ if hasattr(atv_config, 'device_info') else {},
                            }
                        )
                        speakers.append(speaker)

                        # Store config for later connection
                        self._device_configs[identifier] = atv_config

                    except Exception as e:
                        logger.debug(f"Error processing AirPlay device: {e}")

            except Exception as e:
                logger.error(f"{self.name}: Discovery error: {e}")

            return speakers

    async def _get_device(self, speaker_id: str) -> Optional[Any]:
        """Get or connect to an AirPlay device."""
        # Check if already connected
        if speaker_id in self._atv_devices:
            return self._atv_devices[speaker_id]

        # Get config
        config = self._device_configs.get(speaker_id)
        if not config:
            # Try to refresh discovery
            await self.refresh_speakers()
            config = self._device_configs.get(speaker_id)
            if not config:
                return None

        try:
            # Connect to device
            atv = await pyatv.connect(config, asyncio.get_event_loop())
            self._atv_devices[speaker_id] = atv
            return atv
        except Exception as e:
            logger.error(f"{self.name}: Failed to connect to {speaker_id}: {e}")
            return None

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """Play a URL on an AirPlay device."""
        if not PYATV_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            logger.error(f"{self.name}: Speaker {speaker_id} not found")
            return False

        try:
            # Check if device has stream_url method (AirPlay 2)
            if hasattr(device, 'stream') and hasattr(device.stream, 'stream_url'):
                await device.stream.stream_url(url)
                logger.info(f"{self.name}: Streaming URL to {speaker_id}")
                return True

            # For AirPlay 1, we need to use the audio interface
            if hasattr(device, 'audio'):
                # Note: pyatv's audio interface is limited for URL streaming
                # Full implementation would require RAOP streaming
                logger.warning(f"{self.name}: URL streaming not fully supported for this device")
                return False

            logger.error(f"{self.name}: No compatible streaming interface found")
            return False

        except Exception as e:
            logger.error(f"{self.name}: Play failed: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on an AirPlay device."""
        if not PYATV_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            if hasattr(device, 'remote_control'):
                await device.remote_control.stop()
            return True
        except Exception as e:
            logger.error(f"{self.name}: Stop failed: {e}")
            return False

    async def pause(self, speaker_id: str) -> bool:
        """Pause playback."""
        if not PYATV_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            if hasattr(device, 'remote_control'):
                await device.remote_control.pause()
            return True
        except Exception as e:
            logger.error(f"{self.name}: Pause failed: {e}")
            return False

    async def resume(self, speaker_id: str) -> bool:
        """Resume playback."""
        if not PYATV_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            if hasattr(device, 'remote_control'):
                await device.remote_control.play()
            return True
        except Exception as e:
            logger.error(f"{self.name}: Resume failed: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume (0.0-1.0)."""
        if not PYATV_AVAILABLE:
            return False

        device = await self._get_device(speaker_id)
        if not device:
            return False

        try:
            if hasattr(device, 'audio'):
                # pyatv uses 0-100 scale
                await device.audio.set_volume(level * 100)

                # Update cached speaker
                speaker = self.get_speaker(speaker_id)
                if speaker:
                    speaker.volume = level
                    self._update_speaker(speaker)

                return True
            return False
        except Exception as e:
            logger.error(f"{self.name}: Volume failed: {e}")
            return False

    async def get_speaker_state(self, speaker_id: str) -> Optional[SpeakerState]:
        """Get current speaker state."""
        if not PYATV_AVAILABLE:
            return None

        device = await self._get_device(speaker_id)
        if not device:
            return SpeakerState.OFFLINE

        try:
            if hasattr(device, 'playing'):
                playing = await device.playing()
                if playing:
                    state = playing.device_state
                    if state == DeviceState.Playing:
                        return SpeakerState.PLAYING
                    elif state == DeviceState.Paused:
                        return SpeakerState.PAUSED
                    elif state == DeviceState.Loading:
                        return SpeakerState.BUFFERING
            return SpeakerState.IDLE
        except Exception:
            return SpeakerState.OFFLINE

    def get_capabilities(self) -> list[str]:
        """AirPlay supports volume, pause (varies by device)."""
        return ["volume", "pause", "resume"]

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
            "audio_format": {
                "type": "select",
                "default": "wav",
                "label": "Audio Format",
                "options": [
                    {"value": "wav", "label": "WAV (Best compatibility)"},
                    {"value": "mp3", "label": "MP3 (Compressed)"}
                ]
            }
        }
