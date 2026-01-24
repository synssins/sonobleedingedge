"""
Home Assistant Media Controller.

Controls media_player entities via HA services.
"""

from typing import Optional
from dataclasses import dataclass

from .supervisor import SupervisorAPI
from .registry import HAMediaPlayer


@dataclass
class PlaybackState:
    """Current playback state of a media player."""
    playing: bool = False
    volume: float = 0.5
    muted: bool = False
    media_title: Optional[str] = None


class HAMediaController:
    """Controls HA media_player entities."""

    def __init__(self, supervisor: SupervisorAPI):
        """Initialize controller with Supervisor API client."""
        self.supervisor = supervisor

    async def play_media(
        self,
        entity_id: str,
        media_url: str,
        media_type: str = "music",
    ) -> bool:
        """Play media on a specific entity."""
        if not self.supervisor.is_available:
            return False

        # Note: In a full implementation, we would call the HA service:
        # service: media_player.play_media
        # data:
        #   entity_id: media_player.living_room
        #   media_content_id: http://...
        #   media_content_type: music

        print(f"HAMediaController: play_media({entity_id}, {media_url}) - not yet implemented")
        return False

    async def stop(self, entity_id: str) -> bool:
        """Stop playback on a specific entity."""
        if not self.supervisor.is_available:
            return False

        print(f"HAMediaController: stop({entity_id}) - not yet implemented")
        return False

    async def set_volume(self, entity_id: str, volume: float) -> bool:
        """Set volume on a specific entity (0.0 to 1.0)."""
        if not self.supervisor.is_available:
            return False

        print(f"HAMediaController: set_volume({entity_id}, {volume}) - not yet implemented")
        return False

    async def mute(self, entity_id: str, muted: bool) -> bool:
        """Set mute state on a specific entity."""
        if not self.supervisor.is_available:
            return False

        print(f"HAMediaController: mute({entity_id}, {muted}) - not yet implemented")
        return False

    async def get_state(self, entity_id: str) -> Optional[PlaybackState]:
        """Get current playback state of an entity."""
        if not self.supervisor.is_available:
            return None

        print(f"HAMediaController: get_state({entity_id}) - not yet implemented")
        return None
