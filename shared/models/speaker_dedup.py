"""
Speaker Deduplication

Merges speakers discovered from multiple sources (HA, direct plugins)
into a unified list, avoiding duplicates.

This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from sonorium.models.speaker_model import UnifiedSpeaker, DiscoverySource, ControlMethod
from sonorium.obs import logger


class SpeakerDeduplicator:
    """
    Deduplicates speakers found by multiple discovery sources.

    Priority for matching (highest to lowest):
    1. MAC address match (most reliable)
    2. UUID/UID match (protocol-specific unique IDs)
    3. IP address match (can change with DHCP, but usually stable)
    4. Fuzzy name match (fallback, least reliable)

    When speakers match, their information is merged, preferring HA data
    for area/floor organization and direct discovery for protocol details.
    """

    # Minimum similarity ratio for fuzzy name matching (0.0 - 1.0)
    NAME_MATCH_THRESHOLD = 0.85

    def __init__(self):
        """Initialize the deduplicator."""
        # Indexes for fast lookups
        self._by_mac: dict[str, UnifiedSpeaker] = {}
        self._by_uuid: dict[str, UnifiedSpeaker] = {}
        self._by_ip: dict[str, UnifiedSpeaker] = {}
        self._by_canonical_id: dict[str, UnifiedSpeaker] = {}

        # All speakers (canonical_id -> speaker)
        self._speakers: dict[str, UnifiedSpeaker] = {}

    def clear(self) -> None:
        """Clear all indexed speakers."""
        self._by_mac.clear()
        self._by_uuid.clear()
        self._by_ip.clear()
        self._by_canonical_id.clear()
        self._speakers.clear()

    def add_speaker(self, speaker: UnifiedSpeaker) -> UnifiedSpeaker:
        """
        Add a speaker, merging with existing if duplicate found.

        Args:
            speaker: Speaker to add

        Returns:
            The speaker (possibly merged with existing)
        """
        # Try to find existing speaker by various identifiers
        existing = self._find_match(speaker)

        if existing:
            # Merge and update
            merged = existing.merge_with(speaker)
            self._update_indexes(existing, merged)
            self._speakers[merged.canonical_id] = merged
            logger.debug(
                f"Merged speaker '{speaker.name}' with '{existing.name}' -> "
                f"found_by: {merged.found_by_list}"
            )
            return merged
        else:
            # New speaker - generate canonical ID if needed
            if not speaker.canonical_id:
                speaker = self._assign_canonical_id(speaker)

            self._index_speaker(speaker)
            self._speakers[speaker.canonical_id] = speaker
            logger.debug(f"Added new speaker '{speaker.name}' ({speaker.canonical_id})")
            return speaker

    def _find_match(self, speaker: UnifiedSpeaker) -> Optional[UnifiedSpeaker]:
        """
        Find an existing speaker that matches the given one.

        Priority: MAC > UUID > IP > fuzzy name

        Args:
            speaker: Speaker to match

        Returns:
            Matching speaker or None
        """
        # 1. MAC address match (most reliable)
        if speaker.mac_address:
            normalized_mac = self._normalize_mac(speaker.mac_address)
            if normalized_mac in self._by_mac:
                logger.debug(f"Dedup: Matched '{speaker.name}' by MAC {normalized_mac}")
                return self._by_mac[normalized_mac]

        # 2. UUID match
        if speaker.uuid:
            if speaker.uuid in self._by_uuid:
                logger.debug(f"Dedup: Matched '{speaker.name}' by UUID {speaker.uuid}")
                return self._by_uuid[speaker.uuid]

        # 3. IP address match
        if speaker.ip_address:
            if speaker.ip_address in self._by_ip:
                logger.debug(f"Dedup: Matched '{speaker.name}' by IP {speaker.ip_address}")
                return self._by_ip[speaker.ip_address]

        # 4. Fuzzy name match (fallback)
        # Use fuzzy matching if EITHER speaker has an HA entity (prevents false matches
        # with generic names between two direct-only speakers, but allows direct-discovered
        # speakers to match existing HA speakers)
        for existing in self._speakers.values():
            # Only fuzzy match if at least one side has an HA entity
            if not speaker.entity_id and not existing.entity_id:
                continue

            if self._names_match(speaker.name, existing.name):
                # Additional check: same network segment (if IPs known)
                if speaker.ip_address and existing.ip_address:
                    if self._same_subnet(speaker.ip_address, existing.ip_address):
                        logger.debug(
                            f"Dedup: Matched '{speaker.name}' to '{existing.name}' "
                            f"by fuzzy name + subnet"
                        )
                        return existing
                elif not speaker.ip_address or not existing.ip_address:
                    # Can't verify subnet, but names match well enough
                    logger.debug(
                        f"Dedup: Matched '{speaker.name}' to '{existing.name}' by fuzzy name"
                    )
                    return existing

        # No match found - log what we tried
        logger.debug(
            f"Dedup: No match for '{speaker.name}' "
            f"(IP={speaker.ip_address}, MAC={speaker.mac_address}, UUID={speaker.uuid})"
        )
        return None

    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Check if two speaker names likely refer to the same device.

        Uses fuzzy matching with some preprocessing to handle
        variations like "Living Room Sonos" vs "Sonos - Living Room".

        Args:
            name1: First name
            name2: Second name

        Returns:
            True if names likely match
        """
        # Normalize names
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)

        # Exact match after normalization
        if n1 == n2:
            return True

        # Fuzzy match
        ratio = SequenceMatcher(None, n1, n2).ratio()
        return ratio >= self.NAME_MATCH_THRESHOLD

    def _normalize_name(self, name: str) -> str:
        """Normalize a speaker name for comparison."""
        # Lowercase
        name = name.lower()

        # Remove common prefixes/suffixes
        patterns = [
            r'^media_player\.',  # HA entity prefix
            r'\s*\(.*\)\s*$',    # Parenthetical suffixes
            r'\s*-\s*',          # Dashes become spaces
            r'\s+',              # Multiple spaces become one
        ]

        for pattern in patterns:
            name = re.sub(pattern, ' ', name)

        return name.strip()

    def _normalize_mac(self, mac: str) -> str:
        """Normalize MAC address for comparison (uppercase, colon-separated)."""
        # Remove all separators and convert to uppercase
        mac = re.sub(r'[:\-\.]', '', mac).upper()
        # Re-add colons
        return ':'.join(mac[i:i+2] for i in range(0, len(mac), 2))

    def _same_subnet(self, ip1: str, ip2: str) -> bool:
        """
        Check if two IPs are on the same /24 subnet.

        Simple heuristic - assumes typical home network.
        """
        try:
            parts1 = ip1.split('.')[:3]
            parts2 = ip2.split('.')[:3]
            return parts1 == parts2
        except Exception:
            return False

    def _assign_canonical_id(self, speaker: UnifiedSpeaker) -> UnifiedSpeaker:
        """
        Assign a canonical ID to a speaker based on available identifiers.

        Priority: MAC > UUID > IP > entity_id > generated

        Returns a new speaker with the canonical_id set.
        """
        if speaker.mac_address:
            canonical_id = f"unified_{self._normalize_mac(speaker.mac_address).replace(':', '')}"
        elif speaker.uuid:
            canonical_id = f"unified_{speaker.uuid}"
        elif speaker.ip_address:
            canonical_id = f"unified_{speaker.ip_address.replace('.', '_')}"
        elif speaker.entity_id:
            canonical_id = f"unified_{speaker.entity_id.replace('.', '_')}"
        else:
            # Fallback: use sanitized name
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', speaker.name.lower())
            canonical_id = f"unified_{safe_name}"

        # Return new speaker with canonical_id
        return UnifiedSpeaker(
            canonical_id=canonical_id,
            name=speaker.name,
            ip_address=speaker.ip_address,
            mac_address=speaker.mac_address,
            uuid=speaker.uuid,
            entity_id=speaker.entity_id,
            area_id=speaker.area_id,
            area_name=speaker.area_name,
            floor_id=speaker.floor_id,
            floor_name=speaker.floor_name,
            found_by=speaker.found_by,
            preferred_control=speaker.preferred_control,
            protocol=speaker.protocol,
            model=speaker.model,
            manufacturer=speaker.manufacturer,
            capabilities=speaker.capabilities,
            extra=speaker.extra,
        )

    def _index_speaker(self, speaker: UnifiedSpeaker) -> None:
        """Add a speaker to all relevant indexes."""
        indexed_by = []

        if speaker.mac_address:
            normalized_mac = self._normalize_mac(speaker.mac_address)
            self._by_mac[normalized_mac] = speaker
            indexed_by.append(f"MAC:{normalized_mac}")

        if speaker.uuid:
            self._by_uuid[speaker.uuid] = speaker
            indexed_by.append(f"UUID:{speaker.uuid[:20]}...")

        if speaker.ip_address:
            self._by_ip[speaker.ip_address] = speaker
            indexed_by.append(f"IP:{speaker.ip_address}")

        self._by_canonical_id[speaker.canonical_id] = speaker

        logger.debug(
            f"Indexed speaker '{speaker.name}' - "
            f"found_by={speaker.found_by_list}, indexed_by=[{', '.join(indexed_by) or 'canonical_id only'}]"
        )

    def _update_indexes(self, old: UnifiedSpeaker, new: UnifiedSpeaker) -> None:
        """Update indexes when a speaker is merged/updated."""
        # Remove old from indexes
        if old.mac_address:
            normalized_mac = self._normalize_mac(old.mac_address)
            self._by_mac.pop(normalized_mac, None)

        if old.uuid:
            self._by_uuid.pop(old.uuid, None)

        if old.ip_address:
            self._by_ip.pop(old.ip_address, None)

        self._by_canonical_id.pop(old.canonical_id, None)

        # Add new to indexes
        self._index_speaker(new)

    def get_speakers(self) -> list[UnifiedSpeaker]:
        """Get all deduplicated speakers."""
        return list(self._speakers.values())

    def get_speaker(self, canonical_id: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by canonical ID."""
        return self._speakers.get(canonical_id)

    def get_speaker_by_entity_id(self, entity_id: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by HA entity ID."""
        for speaker in self._speakers.values():
            if speaker.entity_id == entity_id:
                return speaker
        return None

    def get_speaker_by_ip(self, ip_address: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by IP address."""
        return self._by_ip.get(ip_address)

    def get_speakers_by_source(self, source: DiscoverySource) -> list[UnifiedSpeaker]:
        """Get all speakers found by a specific source."""
        source_str = source.value if isinstance(source, DiscoverySource) else source
        return [s for s in self._speakers.values() if source_str in s.found_by]

    def get_direct_only_speakers(self) -> list[UnifiedSpeaker]:
        """Get speakers found only by direct discovery (no HA entity)."""
        return [s for s in self._speakers.values() if s.is_direct_only]

    def get_ha_speakers(self) -> list[UnifiedSpeaker]:
        """Get speakers that have HA entities."""
        return [s for s in self._speakers.values() if s.has_ha_entity]
