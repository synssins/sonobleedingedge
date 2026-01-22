"""
Hybrid Speaker Discovery Manager

Combines speakers from Home Assistant registry with direct protocol discovery
via speaker plugins, providing a unified deduplicated speaker list.

This is HA-addon specific code that bridges:
- HARegistry (HA media_player entities)
- Speaker plugins (Sonos, Chromecast, DLNA, AirPlay, etc.)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from sonorium.models.speaker_model import (
    UnifiedSpeaker,
    DiscoverySource,
    ControlMethod,
)
from sonorium.models.speaker_dedup import SpeakerDeduplicator
from sonorium.obs import logger
from sonorium.core.log_collector import get_log_collector, LogCategory

if TYPE_CHECKING:
    from sonorium.ha.registry import HARegistry
    from sonorium.plugins.manager import PluginManager
    from sonorium.plugins.speaker_base import SpeakerPlugin, NetworkSpeaker


class HybridSpeakerManager:
    """
    Manages unified speaker discovery from multiple sources.

    Combines:
    1. Home Assistant media_player entities (via HARegistry)
    2. Direct network discovery (via speaker plugins)

    Deduplicates speakers found by multiple sources and provides
    a unified list with proper control routing.
    """

    def __init__(
        self,
        ha_registry: Optional["HARegistry"],
        plugin_manager: Optional["PluginManager"],
    ):
        """
        Initialize the hybrid speaker manager.

        Args:
            ha_registry: HARegistry instance for HA speakers
            plugin_manager: PluginManager instance for speaker plugins
        """
        self.ha_registry = ha_registry
        self.plugin_manager = plugin_manager
        self.deduplicator = SpeakerDeduplicator()
        self._discovery_running = False
        self._discovery_interval = 30.0
        self._log = get_log_collector()

        logger.info("HybridSpeakerManager initialized")
        self._log.info(LogCategory.DISCOVERY, "HybridSpeakerManager initialized")

    def _get_speaker_plugins(self) -> list["SpeakerPlugin"]:
        """Get all enabled speaker plugins."""
        if not self.plugin_manager:
            self._log.warning(LogCategory.DISCOVERY, "No plugin manager available")
            return []

        all_plugins = self.plugin_manager.get_plugins_by_type("speaker")
        self._log.debug(
            LogCategory.DISCOVERY,
            f"Found {len(all_plugins)} speaker plugins",
            {"plugins": [p.id for p in all_plugins]}
        )

        plugins = []
        for plugin in all_plugins:
            if plugin.enabled:
                plugins.append(plugin)
            else:
                self._log.debug(LogCategory.PLUGINS, f"Plugin '{plugin.id}' is not enabled")

        self._log.info(
            LogCategory.DISCOVERY,
            f"Active speaker plugins: {len(plugins)}",
            {"enabled": [p.id for p in plugins]}
        )
        return plugins

    def _network_speaker_to_unified(
        self,
        speaker: "NetworkSpeaker",
        source: DiscoverySource,
    ) -> UnifiedSpeaker:
        """
        Convert a NetworkSpeaker from a plugin to UnifiedSpeaker.

        Args:
            speaker: NetworkSpeaker from plugin discovery
            source: Which plugin/protocol discovered it

        Returns:
            UnifiedSpeaker representation
        """
        # Generate canonical_id from speaker's unique identifier
        if speaker.extra.get("mac_address"):
            mac = speaker.extra["mac_address"].replace(":", "").upper()
            canonical_id = f"unified_{mac}"
        elif speaker.id:
            canonical_id = f"unified_{speaker.id}"
        else:
            safe_ip = speaker.ip_address.replace(".", "_") if speaker.ip_address else "unknown"
            canonical_id = f"unified_{safe_ip}"

        return UnifiedSpeaker(
            canonical_id=canonical_id,
            name=speaker.name,
            ip_address=speaker.ip_address,
            mac_address=speaker.extra.get("mac_address"),
            uuid=speaker.id,
            found_by={source.value},
            preferred_control=ControlMethod.DIRECT,
            protocol=source.value,
            model=speaker.model,
            manufacturer=speaker.manufacturer,
            capabilities=speaker.capabilities,
            extra={
                "port": speaker.port,
                "state": speaker.state.value if speaker.state else None,
                "volume": speaker.volume,
                **speaker.extra,
            },
        )

    async def discover_all(self) -> list[UnifiedSpeaker]:
        """
        Run full discovery from all sources.

        1. Gets speakers from HA registry
        2. Runs discovery on all enabled speaker plugins
        3. Deduplicates and merges results

        Returns:
            List of unified, deduplicated speakers
        """
        self.deduplicator.clear()

        # 1. Add HA speakers first (they take priority for area/floor info)
        ha_count = 0
        if self.ha_registry:
            hierarchy = self.ha_registry.hierarchy
            for speaker in hierarchy.get_all_speakers():
                unified = speaker.to_unified_speaker()
                self.deduplicator.add_speaker(unified)
                ha_count += 1

        logger.info(f"HybridSpeakerManager: Added {ha_count} speakers from HA")

        # 2. Run plugin discovery in parallel
        plugins = self._get_speaker_plugins()
        plugin_count = 0

        if plugins:
            logger.info(f"HybridSpeakerManager: Running discovery on {len(plugins)} plugins")
            tasks = [plugin.refresh_speakers() for plugin in plugins]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for plugin, result in zip(plugins, results):
                if isinstance(result, Exception):
                    logger.error(f"Discovery failed for {plugin.name}: {result}")
                    continue

                # Map protocol names to DiscoverySource
                protocol_map = {
                    "sonos": DiscoverySource.SONOS,
                    "chromecast": DiscoverySource.CHROMECAST,
                    "airplay": DiscoverySource.AIRPLAY,
                    "dlna": DiscoverySource.DLNA,
                    "linkplay": DiscoverySource.LINKPLAY,
                    "heos": DiscoverySource.HEOS,
                }
                source = protocol_map.get(
                    getattr(plugin, 'protocol', plugin.id),
                    DiscoverySource.MANUAL
                )

                for network_speaker in result:
                    unified = self._network_speaker_to_unified(network_speaker, source)
                    self.deduplicator.add_speaker(unified)
                    plugin_count += 1

        logger.info(
            f"HybridSpeakerManager: Discovery complete - "
            f"{ha_count} HA + {plugin_count} direct = "
            f"{len(self.deduplicator.get_speakers())} unified speakers"
        )

        return self.deduplicator.get_speakers()

    async def refresh_from_ha(self) -> list[UnifiedSpeaker]:
        """
        Refresh only HA speakers (faster, no network discovery).

        Returns:
            Updated list of unified speakers
        """
        if self.ha_registry:
            self.ha_registry.refresh()

        # Re-run full dedup to update HA speakers
        return await self.discover_all()

    async def scan_network(self) -> dict:
        """
        Trigger direct network discovery only (no HA refresh).

        Useful for finding speakers not yet in Home Assistant.

        Returns:
            Dict with scan results including found, new, and merged counts
        """
        plugins = self._get_speaker_plugins()
        results_data = {
            "found": 0,        # Total speakers discovered on network
            "new": 0,          # Speakers not previously known
            "merged": 0,       # Speakers merged with existing (duplicates)
            "by_protocol": {}, # Count by protocol
            "speakers": [],    # List of discovered speaker summaries
        }

        if not plugins:
            self._log.warning(LogCategory.DISCOVERY, "No speaker plugins available for network scan")
            return results_data

        self._log.info(
            LogCategory.DISCOVERY,
            f"Scanning network with {len(plugins)} plugin(s)",
            {"plugins": [p.id for p in plugins]}
        )

        tasks = [plugin.refresh_speakers() for plugin in plugins]
        scan_results = await asyncio.gather(*tasks, return_exceptions=True)

        for plugin, result in zip(plugins, scan_results):
            if isinstance(result, Exception):
                self._log.error(
                    LogCategory.DISCOVERY,
                    f"Network scan failed for {plugin.name}: {result}"
                )
                continue

            protocol_map = {
                "sonos": DiscoverySource.SONOS,
                "chromecast": DiscoverySource.CHROMECAST,
                "airplay": DiscoverySource.AIRPLAY,
                "dlna": DiscoverySource.DLNA,
                "linkplay": DiscoverySource.LINKPLAY,
                "heos": DiscoverySource.HEOS,
            }
            protocol = getattr(plugin, 'protocol', plugin.id)
            source = protocol_map.get(protocol, DiscoverySource.MANUAL)

            protocol_count = 0
            for network_speaker in result:
                unified = self._network_speaker_to_unified(network_speaker, source)

                # Check if this is a new speaker or merge with existing
                existing = self.deduplicator.get_speaker(unified.canonical_id)
                was_new = existing is None

                # Add to deduplicator (will merge if already exists)
                merged = self.deduplicator.add_speaker(unified)

                results_data["found"] += 1
                protocol_count += 1

                if was_new:
                    results_data["new"] += 1
                else:
                    results_data["merged"] += 1

                results_data["speakers"].append({
                    "name": merged.name,
                    "ip": merged.ip_address,
                    "protocol": source.value,
                    "is_new": was_new,
                })

            results_data["by_protocol"][protocol] = protocol_count

        # Log summary
        self._log.info(
            LogCategory.DISCOVERY,
            f"Network scan complete: {results_data['found']} found, "
            f"{results_data['new']} new, {results_data['merged']} merged",
            results_data["by_protocol"]
        )

        logger.info(
            f"HybridSpeakerManager: Network scan - "
            f"{results_data['found']} found, {results_data['new']} new, "
            f"{results_data['merged']} merged with existing"
        )

        return results_data

    # --- Speaker Access ---

    def get_speakers(self) -> list[UnifiedSpeaker]:
        """Get all unified speakers."""
        return self.deduplicator.get_speakers()

    def get_speaker(self, canonical_id: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by canonical ID."""
        return self.deduplicator.get_speaker(canonical_id)

    def get_speaker_by_entity_id(self, entity_id: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by HA entity ID."""
        return self.deduplicator.get_speaker_by_entity_id(entity_id)

    def get_speaker_by_ip(self, ip_address: str) -> Optional[UnifiedSpeaker]:
        """Get a speaker by IP address."""
        return self.deduplicator.get_speaker_by_ip(ip_address)

    def get_ha_speakers(self) -> list[UnifiedSpeaker]:
        """Get speakers with HA entities."""
        return self.deduplicator.get_ha_speakers()

    def get_direct_only_speakers(self) -> list[UnifiedSpeaker]:
        """Get speakers found only by direct discovery (no HA entity)."""
        return self.deduplicator.get_direct_only_speakers()

    def get_speakers_by_source(self, source: str) -> list[UnifiedSpeaker]:
        """Get speakers found by a specific source."""
        return self.deduplicator.get_speakers_by_source(source)

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Serialize manager state for API."""
        speakers = self.get_speakers()
        sources = set()
        for s in speakers:
            sources.update(s.found_by)

        return {
            "speaker_count": len(speakers),
            "sources": sorted(sources),
            "ha_speaker_count": len(self.get_ha_speakers()),
            "direct_only_count": len(self.get_direct_only_speakers()),
            "speakers": [s.to_dict() for s in speakers],
        }

    def list_speakers(self) -> list[dict]:
        """Get all speakers as serialized dicts for API."""
        return [s.to_dict() for s in self.get_speakers()]


# Factory function
def create_hybrid_manager(
    ha_registry: Optional["HARegistry"] = None,
    plugin_manager: Optional["PluginManager"] = None,
) -> HybridSpeakerManager:
    """
    Create a HybridSpeakerManager instance.

    Args:
        ha_registry: HARegistry instance (optional)
        plugin_manager: PluginManager instance (optional)

    Returns:
        Configured HybridSpeakerManager
    """
    return HybridSpeakerManager(
        ha_registry=ha_registry,
        plugin_manager=plugin_manager,
    )
