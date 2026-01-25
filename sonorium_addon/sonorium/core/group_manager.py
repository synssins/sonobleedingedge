"""
Speaker Group Manager

Handles CRUD operations for saved speaker group configurations.

CORE CODE: This module is shared across all platforms.
The speaker_registry is optional and can be provided by platform-specific
implementations (HA addon, standalone, etc.).
"""

from __future__ import annotations

import uuid
from typing import Optional, TYPE_CHECKING, Protocol

from .state import (
    SpeakerGroup,
    SpeakerSelection,
    StateStore,
)
from ..obs import logger

if TYPE_CHECKING:
    pass


class SpeakerRegistry(Protocol):
    """Protocol for speaker registry implementations."""

    def resolve_selection(
        self,
        include_floors: list[str] = None,
        include_areas: list[str] = None,
        include_speakers: list[str] = None,
        exclude_areas: list[str] = None,
        exclude_speakers: list[str] = None,
    ) -> list[str]:
        ...


class GroupManager:
    """
    Manages saved speaker group configurations.

    Speaker groups are reusable speaker selections that can be
    referenced by multiple sessions.

    The speaker_registry is optional - when not provided, speaker resolution
    returns empty lists.
    """

    def __init__(
        self,
        state_store: StateStore,
        speaker_registry: Optional[SpeakerRegistry] = None,
    ):
        self.state = state_store
        self.registry = speaker_registry

    def set_speaker_registry(self, registry: SpeakerRegistry):
        """Set the speaker registry (for deferred initialization)."""
        self.registry = registry

    # --- CRUD Operations ---

    def create(
        self,
        name: str,
        include_floors: list[str] = None,
        include_areas: list[str] = None,
        include_speakers: list[str] = None,
        exclude_areas: list[str] = None,
        exclude_speakers: list[str] = None,
        icon: str = "mdi:speaker-group",
    ) -> SpeakerGroup:
        """
        Create a new speaker group.

        Args:
            name: Display name for the group
            include_floors: Floor IDs to include
            include_areas: Area IDs to include
            include_speakers: Speaker entity_ids to include
            exclude_areas: Area IDs to exclude
            exclude_speakers: Speaker entity_ids to exclude
            icon: MDI icon name

        Returns:
            Created speaker group

        Raises:
            ValueError: If max groups exceeded or name already exists
        """
        # Check limits
        max_groups = self.state.settings.max_groups
        if len(self.state.speaker_groups) >= max_groups:
            raise ValueError(f"Maximum of {max_groups} speaker groups allowed")

        # Check for duplicate name
        for group in self.state.speaker_groups.values():
            if group.name.lower() == name.lower():
                raise ValueError(f"Speaker group '{name}' already exists")

        # Generate ID
        group_id = str(uuid.uuid4())[:8]

        # Create group
        group = SpeakerGroup(
            id=group_id,
            name=name,
            icon=icon,
            include_floors=include_floors or [],
            include_areas=include_areas or [],
            include_speakers=include_speakers or [],
            exclude_areas=exclude_areas or [],
            exclude_speakers=exclude_speakers or [],
        )

        # Store and save
        self.state.speaker_groups[group_id] = group
        self.state.save()

        resolved = self.resolve(group)
        logger.info(f"  Created group '{name}' with {len(resolved)} speakers")
        return group

    def create_from_selection(
        self,
        name: str,
        selection: SpeakerSelection,
        icon: str = "mdi:speaker-group",
    ) -> SpeakerGroup:
        """
        Create a group from an existing speaker selection.

        Args:
            name: Display name
            selection: Speaker selection to copy
            icon: MDI icon name

        Returns:
            Created speaker group
        """
        return self.create(
            name=name,
            include_floors=selection.include_floors,
            include_areas=selection.include_areas,
            include_speakers=selection.include_speakers,
            exclude_areas=selection.exclude_areas,
            exclude_speakers=selection.exclude_speakers,
            icon=icon,
        )

    def get(self, group_id: str) -> Optional[SpeakerGroup]:
        """Get a group by ID."""
        return self.state.speaker_groups.get(group_id)

    def list(self) -> list[SpeakerGroup]:
        """List all speaker groups."""
        return list(self.state.speaker_groups.values())

    def update(
        self,
        group_id: str,
        name: str = None,
        include_floors: list[str] = None,
        include_areas: list[str] = None,
        include_speakers: list[str] = None,
        exclude_areas: list[str] = None,
        exclude_speakers: list[str] = None,
        icon: str = None,
    ) -> Optional[SpeakerGroup]:
        """
        Update an existing group.

        Only provided fields are updated.

        Returns:
            Updated group or None if not found
        """
        group = self.state.speaker_groups.get(group_id)
        if not group:
            logger.warning(f"  Group {group_id} not found")
            return None

        if name is not None:
            # Check for duplicate name (excluding self)
            for g in self.state.speaker_groups.values():
                if g.id != group_id and g.name.lower() == name.lower():
                    raise ValueError(f"Speaker group '{name}' already exists")
            group.name = name

        if include_floors is not None:
            group.include_floors = include_floors

        if include_areas is not None:
            group.include_areas = include_areas

        if include_speakers is not None:
            group.include_speakers = include_speakers

        if exclude_areas is not None:
            group.exclude_areas = exclude_areas

        if exclude_speakers is not None:
            group.exclude_speakers = exclude_speakers

        if icon is not None:
            group.icon = icon

        self.state.save()
        logger.info(f"  Updated group '{group.name}'")
        return group

    def delete(self, group_id: str) -> bool:
        """
        Delete a speaker group.

        Returns:
            True if deleted, False if not found
        """
        if group_id not in self.state.speaker_groups:
            logger.warning(f"  Group {group_id} not found")
            return False

        group = self.state.speaker_groups.pop(group_id)
        self.state.save()

        logger.info(f"  Deleted group '{group.name}'")
        return True

    # --- Speaker Resolution ---

    def resolve(self, group: SpeakerGroup) -> list[str]:
        """
        Resolve a group to its list of speaker entity_ids.

        Returns:
            List of speaker entity_ids, or empty list if no registry
        """
        if not self.registry:
            return []

        return self.registry.resolve_selection(
            include_floors=group.include_floors,
            include_areas=group.include_areas,
            include_speakers=group.include_speakers,
            exclude_areas=group.exclude_areas,
            exclude_speakers=group.exclude_speakers,
        )

    def get_speaker_count(self, group: SpeakerGroup) -> int:
        """Get the number of resolved speakers in a group."""
        return len(self.resolve(group))

    def to_selection(self, group: SpeakerGroup) -> SpeakerSelection:
        """Convert a group to a SpeakerSelection."""
        return SpeakerSelection(
            include_floors=group.include_floors,
            include_areas=group.include_areas,
            include_speakers=group.include_speakers,
            exclude_areas=group.exclude_areas,
            exclude_speakers=group.exclude_speakers,
        )
