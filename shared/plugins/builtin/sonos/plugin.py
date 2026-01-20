"""
Sonos Speaker Plugin

Provides discovery and playback control for Sonos speakers using the soco library.
This is a TRUE plugin - deleting this folder removes Sonos support entirely.
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


class SonosPlugin(SpeakerPlugin):
    """
    Sonos speaker plugin.

    Discovers Sonos devices on the network and provides playback control
    using the soco (Sonos Controller) library.
    """

    plugin_type: str = "speaker"

    def __init__(self, plugin_dir: Path, settings: dict, audio_path: Optional[Path] = None):
        super().__init__(plugin_dir, settings, audio_path)

        # Settings
        self._discovery_timeout = settings.get("discovery_timeout", 5)
        self._use_groups = settings.get("use_groups", True)

        # Device cache for playback
        self._devices: dict[str, Any] = {}

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """
        Discover Sonos speakers on the network using soco.

        Returns:
            List of discovered NetworkSpeaker objects
        """
        discovered = []

        try:
            import soco

            logger.info("Starting Sonos discovery...")

            # Run the blocking discovery in a thread
            def _discover():
                return list(soco.discover(timeout=self._discovery_timeout) or [])

            loop = asyncio.get_event_loop()
            devices = await loop.run_in_executor(None, _discover)

            for device in devices:
                try:
                    speaker_id = f"sonos_{device.uid}"

                    # Determine state
                    state = SpeakerState.IDLE
                    try:
                        transport_info = device.get_current_transport_info()
                        current_state = transport_info.get('current_transport_state', '')
                        if current_state == 'PLAYING':
                            state = SpeakerState.PLAYING
                        elif current_state == 'PAUSED_PLAYBACK':
                            state = SpeakerState.PAUSED
                    except Exception:
                        pass

                    # Get volume
                    volume = 1.0
                    try:
                        volume = device.volume / 100.0
                    except Exception:
                        pass

                    # Get mute state
                    is_muted = False
                    try:
                        is_muted = device.mute
                    except Exception:
                        pass

                    # Check if this is a group coordinator
                    is_group = False
                    group_members = []
                    if self._use_groups and device.is_coordinator:
                        try:
                            members = list(device.group.members)
                            if len(members) > 1:
                                is_group = True
                                group_members = [m.uid for m in members]
                        except Exception:
                            pass

                    speaker = NetworkSpeaker(
                        id=speaker_id,
                        name=device.player_name,
                        model=device.speaker_info.get('model_name', 'Sonos'),
                        manufacturer="Sonos",
                        ip_address=device.ip_address,
                        port=1400,
                        state=state,
                        volume=volume,
                        is_muted=is_muted,
                        capabilities=["volume", "mute", "pause", "groups"] if self._use_groups else ["volume", "mute", "pause"],
                        extra={
                            'uid': device.uid,
                            'zone_name': device.speaker_info.get('zone_name'),
                            'is_coordinator': device.is_coordinator,
                            'is_group': is_group,
                            'group_members': group_members,
                        }
                    )

                    # Cache the device for playback
                    self._devices[speaker_id] = device
                    discovered.append(speaker)
                    logger.debug(f"Found Sonos: {speaker.name} at {speaker.ip_address}")

                except Exception as e:
                    logger.warning(f"Error processing Sonos device: {e}")

            logger.info(f"Sonos discovery found {len(discovered)} devices")

        except ImportError:
            logger.warning("soco not installed - Sonos discovery disabled")
        except Exception as e:
            logger.error(f"Sonos discovery error: {e}")

        return discovered

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """
        Play a URL on a Sonos speaker.

        Args:
            speaker_id: The speaker ID (sonos_{uid})
            url: The stream URL to play

        Returns:
            True if playback started successfully
        """
        try:
            import soco

            device = self._devices.get(speaker_id)
            if not device:
                # Try to find by IP from cached speaker
                speaker = self.get_speaker(speaker_id)
                if speaker:
                    device = soco.SoCo(speaker.ip_address)
                else:
                    logger.error(f"Sonos device not found: {speaker_id}")
                    return False

            logger.info(f"Starting Sonos playback on {speaker_id}...")

            loop = asyncio.get_event_loop()

            def connect_and_play():
                # Stop current playback
                device.stop()

                # Clear the queue
                device.clear_queue()

                # Play the URI directly
                # force_radio=True is required for live streams (Sonos 6.4.2+)
                device.play_uri(
                    uri=url,
                    title='Sonorium',
                    force_radio=True
                )
                return True

            result = await loop.run_in_executor(None, connect_and_play)

            if result:
                # Update speaker state
                speaker = self.get_speaker(speaker_id)
                if speaker:
                    speaker.state = SpeakerState.PLAYING
                    speaker.current_media = url
                    self._update_speaker(speaker)

                logger.info(f"Sonos {speaker_id} now playing {url}")

            return result

        except ImportError:
            logger.error("soco not installed")
            return False
        except Exception as e:
            logger.error(f"Sonos playback error: {e}")
            return False

    async def stop(self, speaker_id: str) -> bool:
        """
        Stop playback on a Sonos speaker.

        Args:
            speaker_id: The speaker ID

        Returns:
            True if stopped successfully
        """
        try:
            device = self._devices.get(speaker_id)
            if not device:
                logger.warning(f"Sonos device not found: {speaker_id}")
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.stop)

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.IDLE
                speaker.current_media = None
                self._update_speaker(speaker)

            logger.info(f"Stopped Sonos {speaker_id}")
            return True

        except Exception as e:
            logger.warning(f"Error stopping Sonos: {e}")
            return False

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """
        Set volume on a Sonos speaker.

        Args:
            speaker_id: The speaker ID
            level: Volume level 0.0-1.0

        Returns:
            True if volume was set
        """
        try:
            device = self._devices.get(speaker_id)
            if not device:
                logger.warning(f"Sonos device not found: {speaker_id}")
                return False

            # Convert 0.0-1.0 to 0-100
            volume = int(level * 100)
            volume = max(0, min(100, volume))

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: setattr(device, 'volume', volume))

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.volume = level
                self._update_speaker(speaker)

            logger.debug(f"Set Sonos {speaker_id} volume to {volume}%")
            return True

        except Exception as e:
            logger.warning(f"Error setting Sonos volume: {e}")
            return False

    async def pause(self, speaker_id: str) -> bool:
        """Pause playback on a Sonos speaker."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.pause)

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.PAUSED
                self._update_speaker(speaker)

            return True
        except Exception as e:
            logger.warning(f"Error pausing Sonos: {e}")
            return False

    async def resume(self, speaker_id: str) -> bool:
        """Resume playback on a Sonos speaker."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, device.play)

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.state = SpeakerState.PLAYING
                self._update_speaker(speaker)

            return True
        except Exception as e:
            logger.warning(f"Error resuming Sonos: {e}")
            return False

    async def mute(self, speaker_id: str, muted: bool) -> bool:
        """Mute/unmute a Sonos speaker."""
        try:
            device = self._devices.get(speaker_id)
            if not device:
                return False

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: setattr(device, 'mute', muted))

            # Update speaker state
            speaker = self.get_speaker(speaker_id)
            if speaker:
                speaker.is_muted = muted
                self._update_speaker(speaker)

            return True
        except Exception as e:
            logger.warning(f"Error muting Sonos: {e}")
            return False

    def get_capabilities(self) -> list[str]:
        """Get plugin capabilities."""
        caps = ["volume", "mute", "pause", "resume"]
        if self._use_groups:
            caps.append("groups")
        return caps


# Plugin entry point
Plugin = SonosPlugin
