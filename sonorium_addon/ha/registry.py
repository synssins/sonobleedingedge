"""
Home Assistant Device Registry Integration.

Queries HA for media_player entities to use as additional speaker sources.
"""

import asyncio
from typing import Optional
from dataclasses import dataclass, field

from .supervisor import SupervisorAPI


@dataclass
class HAMediaPlayer:
    """Represents a media_player entity from HA."""
    entity_id: str
    friendly_name: str
    device_class: Optional[str] = None
    supported_features: int = 0
    state: str = "unknown"
    platform: Optional[str] = None
    area_id: Optional[str] = None
    area_name: Optional[str] = None

    @property
    def id(self) -> str:
        """Generate unique ID for this player."""
        return f"ha_{self.entity_id.replace('.', '_')}"

    @property
    def protocol(self) -> str:
        """Get the protocol/integration name."""
        if self.platform:
            return f"ha_{self.platform}"
        return "ha_media_player"


class HARegistry:
    """Queries Home Assistant for media_player entities."""

    def __init__(self, supervisor: SupervisorAPI):
        """Initialize registry with Supervisor API client."""
        self.supervisor = supervisor
        self._players: dict[str, HAMediaPlayer] = {}
        self._areas: dict[str, str] = {}  # area_id -> area_name

    async def refresh(self) -> list[HAMediaPlayer]:
        """Refresh the list of media_player entities from HA."""
        if not self.supervisor.is_available:
            return []

        # Note: In a full implementation, we would use the HA WebSocket API
        # or the Supervisor's proxy to query entities. For now, we return
        # an empty list as a placeholder.

        # This would typically involve:
        # 1. Connect to HA WebSocket API at ws://supervisor/core/websocket
        # 2. Authenticate with the long-lived access token
        # 3. Call get_states to retrieve all entities
        # 4. Filter for media_player.* entities
        # 5. Call areas to get area information

        print("HARegistry: Entity refresh not yet implemented")
        return []

    def get_players(self) -> list[HAMediaPlayer]:
        """Get cached list of media players."""
        return list(self._players.values())

    def get_player(self, entity_id: str) -> Optional[HAMediaPlayer]:
        """Get a specific player by entity_id."""
        return self._players.get(entity_id)

    def get_players_in_area(self, area_id: str) -> list[HAMediaPlayer]:
        """Get all players in a specific area."""
        return [p for p in self._players.values() if p.area_id == area_id]
