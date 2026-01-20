# Speaker Protocol Plugin Architecture

## Overview

This document outlines the architecture for converting network speaker protocols (AirPlay, Chromecast, Sonos, DLNA) into installable/removable plugins.

## Goals

1. **Modularity** - Each protocol is self-contained and can be installed/removed independently
2. **Optional Dependencies** - Core app doesn't require pyatv, pychromecast, soco, etc.
3. **Feature Parity** - Same plugins work on all platforms (Windows, Docker, HA Addon)
4. **Extensibility** - Easy to add new protocols without touching core code
5. **Uniform Interface** - All speaker types exposed through common API

---

## Architecture

### Core Components

```
sonorium/
  core/
    speaker_manager.py     # NEW: Aggregates speakers from all plugins
    discovery_service.py   # NEW: Shared mDNS/SSDP scanning
  plugins/
    speaker_base.py        # ENHANCE: Full speaker plugin interface
    manager.py             # EXISTS: Plugin lifecycle management
```

### Plugin Structure

```
plugins/builtin/
  airplay/
    __init__.py
    manifest.json
    plugin.py              # AirPlaySpeakerPlugin
    discovery.py           # mDNS discovery for _raop._tcp, _airplay._tcp
    streamer.py            # RAOP streaming via pyatv

  chromecast/
    __init__.py
    manifest.json
    plugin.py              # ChromecastSpeakerPlugin (enhance existing)
    discovery.py           # mDNS discovery for _googlecast._tcp
    streamer.py            # pychromecast streaming

  sonos/
    __init__.py
    manifest.json
    plugin.py              # SonosSpeakerPlugin
    discovery.py           # SoCo/SSDP discovery
    streamer.py            # SoCo streaming

  dlna/
    __init__.py
    manifest.json
    plugin.py              # DLNASpeakerPlugin
    discovery.py           # SSDP discovery for MediaRenderer
    streamer.py            # UPnP AV Transport
```

---

## Plugin Interface

### speaker_base.py

```python
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from sonorium.plugins.base import PluginBase


class SpeakerState(str, Enum):
    """Speaker connection state."""
    DISCOVERED = "discovered"      # Found on network
    CONNECTING = "connecting"      # Connection in progress
    CONNECTED = "connected"        # Ready to stream
    STREAMING = "streaming"        # Currently streaming
    ERROR = "error"                # Connection/streaming error
    OFFLINE = "offline"            # No longer responding


@dataclass
class Speaker:
    """Represents a network speaker."""
    id: str                        # Unique identifier
    name: str                      # Display name
    protocol: str                  # "airplay", "chromecast", "sonos", "dlna"
    host: str                      # IP address or hostname
    port: int                      # Service port
    state: SpeakerState = SpeakerState.DISCOVERED

    # Optional capabilities
    supports_volume: bool = True
    supports_grouping: bool = False
    supports_pause: bool = False

    # Protocol-specific metadata
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SpeakerPlugin(PluginBase):
    """
    Base class for speaker protocol plugins.

    Each speaker protocol (AirPlay, Chromecast, Sonos, DLNA) implements
    this interface to provide discovery and streaming capabilities.
    """

    # Plugin type identifier
    plugin_type = "speaker"

    # Protocol identifier (e.g., "airplay", "chromecast")
    protocol: str = None

    @abstractmethod
    async def discover(self) -> list[Speaker]:
        """
        Discover speakers on the network using this protocol.

        Returns:
            List of discovered Speaker objects
        """
        raise NotImplementedError

    @abstractmethod
    async def connect(self, speaker: Speaker) -> bool:
        """
        Establish connection to a speaker.

        Args:
            speaker: Speaker to connect to

        Returns:
            True if connection successful
        """
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self, speaker: Speaker) -> bool:
        """
        Disconnect from a speaker.

        Args:
            speaker: Speaker to disconnect from

        Returns:
            True if disconnection successful
        """
        raise NotImplementedError

    @abstractmethod
    async def stream(self, speaker: Speaker, stream_url: str) -> bool:
        """
        Start streaming audio to a speaker.

        Args:
            speaker: Target speaker
            stream_url: URL of the audio stream

        Returns:
            True if streaming started successfully
        """
        raise NotImplementedError

    @abstractmethod
    async def stop(self, speaker: Speaker) -> bool:
        """
        Stop streaming to a speaker.

        Args:
            speaker: Speaker to stop

        Returns:
            True if stopped successfully
        """
        raise NotImplementedError

    async def set_volume(self, speaker: Speaker, volume: float) -> bool:
        """
        Set speaker volume (0.0 to 1.0).

        Override if protocol supports volume control.
        """
        return False

    async def get_volume(self, speaker: Speaker) -> Optional[float]:
        """
        Get current speaker volume.

        Override if protocol supports volume control.
        """
        return None

    def get_discovery_identifiers(self) -> list[str]:
        """
        Return mDNS service types or SSDP URNs this plugin discovers.

        Used by core discovery service to route discoveries to plugins.

        Examples:
            AirPlay: ["_raop._tcp.local.", "_airplay._tcp.local."]
            Chromecast: ["_googlecast._tcp.local."]
            DLNA: ["urn:schemas-upnp-org:device:MediaRenderer:1"]
        """
        return []
```

---

## Manifest Format

### manifest.json

```json
{
  "id": "airplay",
  "name": "AirPlay Speaker Support",
  "version": "1.0.0",
  "type": "speaker",
  "protocol": "airplay",
  "description": "Adds AirPlay 1 and AirPlay 2 speaker discovery and streaming",

  "author": "Sonorium",
  "homepage": "https://github.com/synssins/sonorium",

  "dependencies": {
    "pip": [
      "pyatv>=0.14.0",
      "zeroconf>=0.80.0"
    ]
  },

  "discovery": {
    "mdns": [
      "_raop._tcp.local.",
      "_airplay._tcp.local."
    ]
  },

  "capabilities": {
    "volume_control": true,
    "grouping": false,
    "pause_resume": true
  },

  "platforms": ["windows", "linux", "macos", "docker", "ha_addon"]
}
```

---

## Core Services

### SpeakerManager

Aggregates speakers from all enabled speaker plugins.

```python
class SpeakerManager:
    """
    Central manager for all network speakers.

    Aggregates speakers discovered by all enabled speaker plugins
    and provides a unified interface for the UI and API.
    """

    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self._speakers: dict[str, Speaker] = {}
        self._plugin_map: dict[str, SpeakerPlugin] = {}  # speaker_id -> plugin

    async def discover_all(self) -> list[Speaker]:
        """Run discovery on all enabled speaker plugins."""
        speakers = []
        for plugin in self.plugin_manager.get_plugins_by_type("speaker"):
            if plugin.enabled:
                discovered = await plugin.discover()
                for speaker in discovered:
                    self._speakers[speaker.id] = speaker
                    self._plugin_map[speaker.id] = plugin
                speakers.extend(discovered)
        return speakers

    async def stream_to(self, speaker_id: str, stream_url: str) -> bool:
        """Stream to a speaker by ID."""
        if speaker_id not in self._speakers:
            return False
        speaker = self._speakers[speaker_id]
        plugin = self._plugin_map[speaker_id]
        return await plugin.stream(speaker, stream_url)

    async def stop(self, speaker_id: str) -> bool:
        """Stop streaming to a speaker."""
        if speaker_id not in self._speakers:
            return False
        speaker = self._speakers[speaker_id]
        plugin = self._plugin_map[speaker_id]
        return await plugin.stop(speaker)

    def get_speakers(self) -> list[Speaker]:
        """Get all discovered speakers."""
        return list(self._speakers.values())

    def get_speakers_by_protocol(self, protocol: str) -> list[Speaker]:
        """Get speakers filtered by protocol."""
        return [s for s in self._speakers.values() if s.protocol == protocol]
```

### DiscoveryService

Shared network discovery to avoid duplicate scanning.

```python
class DiscoveryService:
    """
    Shared network discovery service.

    Runs mDNS and SSDP discovery once and routes results
    to appropriate speaker plugins based on their registered
    discovery identifiers.
    """

    def __init__(self):
        self._mdns_handlers: dict[str, list[callable]] = {}
        self._ssdp_handlers: dict[str, list[callable]] = {}
        self._zeroconf = None
        self._browser = None

    def register_mdns_handler(self, service_type: str, handler: callable):
        """Register a handler for an mDNS service type."""
        if service_type not in self._mdns_handlers:
            self._mdns_handlers[service_type] = []
        self._mdns_handlers[service_type].append(handler)

    def register_ssdp_handler(self, urn: str, handler: callable):
        """Register a handler for an SSDP URN."""
        if urn not in self._ssdp_handlers:
            self._ssdp_handlers[urn] = []
        self._ssdp_handlers[urn].append(handler)

    async def start(self):
        """Start discovery services."""
        # Start mDNS browser for all registered service types
        # Start SSDP listener for all registered URNs
        pass

    async def stop(self):
        """Stop discovery services."""
        pass

    async def scan_now(self) -> dict:
        """Trigger immediate scan and return results."""
        pass
```

---

## Implementation Plan

### Phase 1: Core Infrastructure

1. **Create `core/speaker_manager.py`**
   - Speaker aggregation from plugins
   - Unified streaming interface
   - Speaker state management

2. **Create `core/discovery_service.py`**
   - Shared mDNS browser (zeroconf)
   - Shared SSDP listener
   - Route discoveries to plugins

3. **Enhance `plugins/speaker_base.py`**
   - Full interface as documented above
   - Speaker dataclass
   - SpeakerState enum

### Phase 2: Refactor Existing Code

4. **Migrate Chromecast plugin**
   - Move discovery from `network_speakers.py`
   - Move streaming from `streaming.py`
   - Update manifest with dependencies

5. **Extract from `network_speakers.py`**
   - Identify protocol-specific discovery code
   - Create shared discovery utilities
   - Deprecate monolithic file

6. **Extract from `streaming.py`**
   - Identify protocol-specific streaming code
   - Move to respective plugins
   - Deprecate monolithic file

### Phase 3: Create New Plugins

7. **AirPlay plugin**
   - mDNS discovery (_raop._tcp, _airplay._tcp)
   - pyatv integration for streaming
   - AirPlay 1 and AirPlay 2 support

8. **Sonos plugin**
   - SoCo discovery
   - SoCo streaming
   - Group management (future)

9. **DLNA plugin**
   - SSDP discovery (MediaRenderer)
   - UPnP AV Transport streaming
   - async-upnp-client integration

### Phase 4: UI and API

10. **Update Web API**
    - `/speakers` endpoint uses SpeakerManager
    - `/speakers/{id}/stream` unified interface
    - Protocol-agnostic responses

11. **Update Web UI**
    - Display speakers from all plugins
    - Show protocol badge/icon
    - Plugin enable/disable in settings

---

## Dependency Management

### Per-Plugin Dependencies

Each plugin declares its pip dependencies in manifest.json:

| Plugin | Dependencies |
|--------|--------------|
| AirPlay | `pyatv>=0.14.0`, `zeroconf>=0.80.0` |
| Chromecast | `pychromecast>=13.0.0`, `zeroconf>=0.80.0` |
| Sonos | `soco>=0.30.0` |
| DLNA | `async-upnp-client>=0.36.0` |

### Shared Dependencies

Move to core requirements:
- `zeroconf` - shared by AirPlay, Chromecast (mDNS)

### Installation Flow

1. User enables plugin in UI
2. Plugin manager checks manifest dependencies
3. If missing, prompt user or auto-install
4. Load plugin after dependencies satisfied

```python
async def enable_plugin(self, plugin_id: str):
    plugin = self.get_plugin(plugin_id)
    manifest = plugin.get_manifest()

    # Check dependencies
    missing = self._check_pip_dependencies(manifest.get("dependencies", {}).get("pip", []))

    if missing:
        # Option 1: Auto-install
        await self._install_dependencies(missing)

        # Option 2: Prompt user
        # raise DependencyMissingError(missing)

    plugin.enabled = True
    await plugin.on_enable()
```

---

## Migration Path

### Backward Compatibility

During migration, maintain backward compatibility:

1. Keep `network_speakers.py` functional but deprecated
2. New `SpeakerManager` checks for both old and new systems
3. Gradual migration per protocol

### Deprecation Timeline

| Phase | Action |
|-------|--------|
| v1.3.0 | Introduce plugin architecture, both systems active |
| v1.4.0 | Deprecation warnings for old system |
| v1.5.0 | Remove `network_speakers.py` and `streaming.py` |

---

## Testing Strategy

### Unit Tests

- Each plugin has isolated unit tests
- Mock network responses
- Test discovery parsing
- Test streaming commands

### Integration Tests

- Test with real devices (CI/CD challenge)
- Docker-based test environment
- Protocol simulators where available

### Test Devices

| Protocol | Test Device |
|----------|-------------|
| AirPlay | Arylic Office_C97a (192.168.1.74) |
| Chromecast | Test Cast device |
| Sonos | Sonos Era 300 (192.168.1.185) |
| DLNA | Various renderers |

---

## Future Enhancements

1. **Speaker Groups** - Group speakers across protocols
2. **Sync Playback** - Synchronized multi-room audio
3. **Protocol Auto-Detection** - Suggest plugins based on network scan
4. **Plugin Marketplace** - Community-contributed protocols
5. **Bluetooth Plugin** - Local Bluetooth speaker support
