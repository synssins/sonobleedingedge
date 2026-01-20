"""
Sonos Speaker Plugin

Discovers and controls Sonos speakers on the local network using SoCo.

Requirements:
    pip install soco

Uses the native Sonos protocol for device discovery and control.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional, Dict

from sonorium.plugins.speaker_base import SpeakerPlugin, NetworkSpeaker, SpeakerState
from sonorium.obs import logger

# Try to import soco
try:
    import soco
    from soco.discovery import discover
    SOCO_AVAILABLE = True
except ImportError:
    SOCO_AVAILABLE = False
    soco = None


class SonosPlugin(SpeakerPlugin):
    """
    Sonos speaker plugin using SoCo library.

    Discovers Sonos devices on the network and streams audio to them.
    Supports:
    - All Sonos speakers (One, Beam, Arc, etc.)
    - Sonos groups
    - Volume control
    - Transport control
    """

    id = "sonos"
    name = "Sonos"
    version = "1.0.0"
    description = "Stream audio to Sonos speakers using the native SoCo protocol"
    author = "Sonorium"
    builtin = True

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Discovered Sonos devices (by UID)
        self._sonos_devices: Dict[str, 'soco.SoCo'] = {}

        # Discovery lock
        self._discovery_lock = asyncio.Lock()

    async def on_load(self) -> None:
        """Check for soco availability."""
        if not SOCO_AVAILABLE:
            logger.warning(
                f"{self.name}: soco not installed. "
                "Install with: pip install soco"
            )

    async def on_unload(self) -> None:
        """Clean up connections."""
        self._sonos_devices.clear()

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """Discover Sonos speakers on the network."""
        if not SOCO_AVAILABLE:
            return []

        async with self._discovery_lock:
            try:
                # Run discovery in thread pool (blocking operation)
                loop = asyncio.get_event_loop()
                speakers = await loop.run_in_executor(
                    None,
                    self._discover_sync
                )
                return speakers
            except Exception as e:
                logger.error(f"{self.name}: Discovery error: {e}")
                return []

    def _discover_sync(self) -> list[NetworkSpeaker]:
        """Synchronous discovery (runs in thread pool)."""
        speakers = []
        timeout = self.get_setting("discovery_timeout", 5)
        group_mode = self.get_setting("group_mode", "individual")

        try:
            # Discover Sonos devices
            devices = discover(timeout=timeout)
            if not devices:
                logger.debug(f"{self.name}: No devices found")
                return []

            for device in devices:
                try:
                    # In coordinator mode, skip non-coordinator speakers
                    if group_mode == "coordinator":
                        if device.group and device.group.coordinator != device:
                            continue

                    # Get device info
                    info = device.get_speaker_info()

                    speaker = NetworkSpeaker(
                        id=device.uid,
                        name=device.player_name or info.get("zone_name", "Sonos"),
                        model=info.get("model_name", "Sonos"),
                        manufacturer="Sonos",
                        ip_address=device.ip_address,
                        port=1400,  # Sonos control port
                        state=self._get_transport_state(device),
                        volume=device.volume / 100.0,
                        is_muted=device.mute,
                        capabilities=["volume", "mute", "pause", "resume"],
                        extra={
                            "uid": device.uid,
                            "zone_name": info.get("zone_name", ""),
                            "hardware_version": info.get("hardware_version", ""),
                            "software_version": info.get("software_version", ""),
                            "is_coordinator": device.group is None or device.group.coordinator == device,
                            "group_size": len(device.group.members) if device.group else 1,
                        }
                    )
                    speakers.append(speaker)

                    # Store device reference
                    self._sonos_devices[device.uid] = device

                except Exception as e:
                    logger.debug(f"Error processing Sonos device: {e}")

        except Exception as e:
            logger.error(f"Sonos discovery failed: {e}")

        return speakers

    def _get_transport_state(self, device: 'soco.SoCo') -> SpeakerState:
        """Get speaker state from transport info."""
        try:
            info = device.get_current_transport_info()
            state = info.get("current_transport_state", "").upper()

            if state == "PLAYING":
                return SpeakerState.PLAYING
            elif state == "PAUSED_PLAYBACK":
                return SpeakerState.PAUSED
            elif state == "TRANSITIONING":
                return SpeakerState.BUFFERING
            else:
                return SpeakerState.IDLE
        except Exception:
            return SpeakerState.IDLE

    def _get_sonos(self, speaker_id: str) -> Optional['soco.SoCo']:
        """Get a SoCo device by UID."""
        return self._sonos_devices.get(speaker_id)

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """Play a URL on a Sonos speaker."""
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            logger.error(f"{self.name}: Speaker {speaker_id} not found")
            return False

        try:
            # Run in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._play_sync,
                device,
                url
            )
            return True
        except Exception as e:
            logger.error(f"{self.name}: Play failed: {e}")
            return False

    def _play_sync(self, device: 'soco.SoCo', url: str) -> None:
        """Synchronous play (runs in thread pool)."""
        # Clear queue and play the URL
        device.clear_queue()
        device.play_uri(url, title="Sonorium")

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on a Sonos speaker."""
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.stop)
            return True
        except Exception as e:
            logger.error(f"{self.name}: Stop failed: {e}")
            return False

    async def pause(self, speaker_id: str) -> bool:
        """Pause playback."""
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.pause)
            return True
        except Exception as e:
            logger.error(f"{self.name}: Pause failed: {e}")
            return False

    async def resume(self, speaker_id: str) -> bool:
        """Resume playback."""
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.play)
            return True
        except Exception as e:
            logger.error(f"{self.name}: Resume failed: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume (0.0-1.0)."""
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            return False

        try:
            # Sonos uses 0-100 scale
            volume = int(max(0, min(100, level * 100)))
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: setattr(device, 'volume', volume)
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
        if not SOCO_AVAILABLE:
            return False

        device = self._get_sonos(speaker_id)
        if not device:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: setattr(device, 'mute', muted)
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
        if not SOCO_AVAILABLE:
            return None

        device = self._get_sonos(speaker_id)
        if not device:
            return SpeakerState.OFFLINE

        try:
            loop = asyncio.get_event_loop()
            state = await loop.run_in_executor(
                None,
                self._get_transport_state,
                device
            )
            return state
        except Exception:
            return SpeakerState.OFFLINE

    def get_capabilities(self) -> list[str]:
        """Sonos supports volume, mute, pause, resume."""
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
            "group_mode": {
                "type": "select",
                "default": "individual",
                "label": "Group Mode",
                "options": [
                    {"value": "individual", "label": "Control speakers individually"},
                    {"value": "coordinator", "label": "Control through group coordinators"}
                ]
            }
        }
