# Sonorium Codebase Restructuring Plan

> **Version:** 1.0
> **Date:** 2026-01-19
> **Status:** DRAFT - Pending Review

This document outlines the comprehensive plan to restructure Sonorium into a unified, modular codebase following the architecture defined in `FOUNDATIONAL_CHANGES.md`.

---

## Executive Summary

### Current State
- **Two separate codebases** with significant duplication
- Standalone: ~10,457 lines across 19 core files
- HA Addon: ~18,915 lines with HA-specific integrations
- Frontend: 88% similar, 12% platform-specific differences
- Shared audio core but divergent discovery/control layers

### Target State
- **Unified core** with platform adapters
- Category A files: Identical across all platforms
- Category B files: Same interface, platform-specific implementation
- Modular architecture with optional features
- Plugin system as foundation for extensibility

---

## Current Codebase Analysis

### Standalone App (`app/core/sonorium/`)

| File | Lines | Category | Purpose |
|------|-------|----------|---------|
| `web_api.py` | 2,984 | B | REST API (platform-specific endpoints) |
| `network_speakers.py` | 1,533 | B | Direct network discovery |
| `recording.py` | 982 | A | Audio recording/playback engine |
| `streaming.py` | 967 | B | Network streaming manager |
| `app_device.py` | 536 | B | Main app controller |
| `audio_output.py` | 550 | A | Local audio device output |
| `raop_streamer.py` | 442 | A | AirPlay 1 streaming |
| `update.py` | 353 | C | Windows auto-update (standalone only) |
| `theme.py` | 350 | A | Theme definitions |
| `local_stream_player.py` | 296 | A | Low-latency local playback |
| `config.py` | 298 | B | Configuration management |
| `core/channel.py` | 503 | A | Broadcast channel model |
| `pyatv_patches.py` | 320 | A | pyatv compatibility |
| `main.py` | 218 | B | Server startup |
| `obs.py` | 101 | A | Logging |

### HA Addon (`sonorium_addon/sonorium/`)

| File | Lines | Category | Purpose |
|------|-------|----------|---------|
| `ha/registry.py` | 853 | C | HA device registry (HA only) |
| `ha/media_controller.py` | 386 | C | HA media control (HA only) |
| `ha/mqtt_entities.py` | 1,223 | C | MQTT discovery (HA only) |
| `ha/sonos_player.py` | 761 | A* | Direct Sonos (shared potential) |
| `ha/cast_player.py` | 738 | A* | Direct Chromecast (shared potential) |
| `core/session_manager.py` | 884 | B | Session management |
| `core/state.py` | 422 | B | Data models |
| `core/channel.py` | 455 | A | Audio channels |
| `recording.py` | 872 | A | Audio engine |
| `theme.py` | 190 | A | Theme definitions |
| `web/api_v2.py` | 2,065 | B | HA-specific API routes |
| `settings.py` | 236 | B | HA addon configuration |
| `client.py` | 275 | C | MQTT client (HA only) |

**Categories:**
- **A** = Copy-identical across platforms
- **B** = Same interface, different implementation
- **C** = Platform-exclusive (only exists on one platform)

---

## Proposed Module Architecture

Following `FOUNDATIONAL_CHANGES.md`, here is the proposed modular structure:

### REQUIRED Modules (App will not start without these)

| Module | File | Functionality |
|--------|------|---------------|
| **Core Engine** | `core.py` | Audio mixing, channel management |
| **Web UI** | `ui.py` | Web interface server |
| **Theme Manager** | `themes.py` | Theme loading, switching |
| **Discovery** | `discovery.py` | Device discovery (Category B) |

### OPTIONAL Modules (Graceful degradation if missing)

| Module | File | Functionality |
|--------|------|---------------|
| **REST API** | `api.py` | HTTP API endpoints |
| **Plugin System** | `plugins.py` | Plugin loading/management |
| **WebSocket** | `websocket.py` | Real-time UI updates |
| **Sonos** | `sonos.py` | Sonos speaker support |
| **AirPlay** | `airplay.py` | AirPlay streaming |
| **Chromecast** | `chromecast.py` | Chromecast support |
| **DLNA** | `dlna.py` | DLNA/UPnP support |
| **HEOS** | `heos.py` | Denon/Marantz HEOS |
| **Scheduler** | `scheduler.py` | Timed actions |
| **MQTT** | `mqtt.py` | MQTT integration (HA addon) |
| **HA Integration** | `ha_integration.py` | Home Assistant specifics |

---

## Proposed Directory Structure

```
sonobleedingedge/
├── shared/                          # CATEGORY A - Copy-identical core
│   ├── __init__.py
│   ├── core.py                      # Audio mixing engine
│   ├── themes.py                    # Theme management
│   ├── recording.py                 # Audio playback engine
│   ├── channel.py                   # Broadcast channel model
│   ├── audio_output.py              # Local audio I/O
│   ├── obs.py                       # Logging
│   │
│   ├── streaming/                   # Protocol implementations
│   │   ├── __init__.py
│   │   ├── base.py                  # Base streaming interface
│   │   ├── sonos.py                 # Sonos via SoCo
│   │   ├── chromecast.py            # Chromecast via pychromecast
│   │   ├── airplay.py               # AirPlay via pyatv
│   │   ├── raop.py                  # AirPlay 1 via libraop
│   │   ├── dlna.py                  # DLNA/UPnP
│   │   └── heos.py                  # HEOS protocol
│   │
│   ├── plugins/                     # Plugin system
│   │   ├── __init__.py
│   │   ├── base.py                  # SonoriumPlugin base class
│   │   ├── manager.py               # Plugin manager
│   │   ├── loader.py                # Plugin loader
│   │   ├── context.py               # PluginContext
│   │   ├── events.py                # EventBus
│   │   └── builtin/                 # Built-in plugins
│   │       ├── ambient_mixer/
│   │       └── theme_merge/
│   │
│   └── web/                         # Shared web assets
│       ├── static/
│       │   ├── css/
│       │   │   └── styles.css       # Shared CSS
│       │   └── js/
│       │       ├── api.js           # API client (identical)
│       │       └── app-core.js      # Shared JS functions
│       └── templates/
│           └── components/          # Shared HTML components
│
├── app/                             # STANDALONE DEPLOYMENT
│   ├── core/                        # Standalone-specific code
│   │   └── sonorium/
│   │       ├── __init__.py
│   │       ├── main.py              # Standalone entry point
│   │       ├── config.py            # Standalone config (Category B)
│   │       ├── paths.py             # Standalone paths (Category B)
│   │       ├── discovery.py         # Network discovery (Category B)
│   │       ├── app_device.py        # Desktop app controller
│   │       ├── web_api.py           # Standalone API routes (Category B)
│   │       ├── update.py            # Auto-update (Category C - standalone only)
│   │       └── web/
│   │           └── static/js/
│   │               └── app-standalone.js  # Standalone-specific JS
│   │
│   ├── windows/                     # Windows launcher
│   │   └── src/
│   │       ├── launcher.py
│   │       └── updater.py
│   │
│   └── docker/                      # Docker deployment
│       ├── Dockerfile
│       └── docker-compose.yml
│
├── sonorium_addon/                  # HOME ASSISTANT DEPLOYMENT
│   ├── config.yaml                  # HA addon manifest (Category C)
│   ├── Dockerfile                   # HA addon container (Category C)
│   ├── run.sh                       # HA startup (Category C)
│   │
│   └── sonorium/
│       ├── __init__.py
│       ├── entrypoint.py            # HA entry point
│       ├── config.py                # HA config (Category B)
│       ├── paths.py                 # HA paths (Category B)
│       ├── discovery.py             # HA registry discovery (Category B)
│       ├── web_api.py               # HA API routes (Category B)
│       │
│       ├── ha/                      # HA-exclusive modules (Category C)
│       │   ├── __init__.py
│       │   ├── registry.py          # HA device registry
│       │   ├── media_controller.py  # HA media control
│       │   ├── mqtt_entities.py     # MQTT entity management
│       │   └── mqtt_client.py       # MQTT client
│       │
│       └── web/
│           └── static/js/
│               └── app-ha.js        # HA-specific JS
│
├── docs/                            # Documentation
│   ├── ARCHITECTURE.md
│   ├── CODEBASE_RESTRUCTURING_PLAN.md
│   └── ...
│
└── tests/                           # Test suite
    ├── shared/                      # Tests for shared code
    ├── standalone/                  # Standalone-specific tests
    └── ha_addon/                    # HA addon-specific tests
```

---

## Module Interface Specifications

### Standard Module Pattern

Every module must follow this interface:

```python
"""Module docstring."""

__feature_name__ = "Feature Name"
__required__ = False  # True if app can't start without this
__depends_on__ = []   # List of required modules

async def init(app_context) -> bool:
    """Initialize the module. Return True if successful."""
    pass

async def shutdown() -> None:
    """Clean up resources."""
    pass

def health_check() -> dict:
    """Return module health status."""
    return {"status": "healthy", "details": {}}

def is_available() -> bool:
    """Return True if module can be used."""
    return True
```

### Discovery Module Interface (Category B)

Both standalone and HA addon must implement:

```python
# discovery.py interface

async def init(app_context) -> bool:
    """Initialize discovery subsystem."""

async def discover_speakers() -> List[Speaker]:
    """Return list of discovered speakers."""

def get_speaker(speaker_id: str) -> Optional[Speaker]:
    """Get a specific speaker by ID."""

async def refresh() -> None:
    """Force a re-scan."""

def get_discovery_methods() -> List[str]:
    """Return list of active discovery methods."""
```

**Standalone implementation:** Direct mDNS, SSDP, Zeroconf scanning
**HA addon implementation:** HA device registry + optional direct discovery

---

## Code Migration Map

### Files to Move to `shared/`

| Current Location | New Location | Notes |
|-----------------|--------------|-------|
| `app/core/sonorium/recording.py` | `shared/recording.py` | Core audio engine |
| `app/core/sonorium/theme.py` | `shared/themes.py` | Theme management |
| `app/core/sonorium/core/channel.py` | `shared/channel.py` | Broadcast model |
| `app/core/sonorium/audio_output.py` | `shared/audio_output.py` | Local audio |
| `app/core/sonorium/obs.py` | `shared/obs.py` | Logging |
| `app/core/sonorium/local_stream_player.py` | `shared/local_player.py` | Local playback |
| `app/core/sonorium/pyatv_patches.py` | `shared/streaming/pyatv_patches.py` | AirPlay patches |
| `app/core/sonorium/raop_streamer.py` | `shared/streaming/raop.py` | AirPlay 1 |
| `app/core/sonorium/plugins/*` | `shared/plugins/` | Plugin system |
| `sonorium_addon/sonorium/ha/sonos_player.py` | `shared/streaming/sonos.py` | Sonos support |
| `sonorium_addon/sonorium/ha/cast_player.py` | `shared/streaming/chromecast.py` | Cast support |

### Files to Keep Platform-Specific

| Platform | File | Reason |
|----------|------|--------|
| Standalone | `app/core/sonorium/network_speakers.py` | Direct network discovery |
| Standalone | `app/core/sonorium/streaming.py` | Direct speaker control |
| Standalone | `app/core/sonorium/update.py` | Windows auto-update |
| HA Addon | `sonorium_addon/sonorium/ha/registry.py` | HA WebSocket API |
| HA Addon | `sonorium_addon/sonorium/ha/media_controller.py` | HA service calls |
| HA Addon | `sonorium_addon/sonorium/ha/mqtt_entities.py` | MQTT discovery |

### Frontend Migration

| Component | Action | Notes |
|-----------|--------|-------|
| `api.js` | Keep identical | Already unified |
| `styles.css` | Keep identical | Already unified |
| Shared functions | Extract to `app-core.js` | ~2000 lines |
| Speaker settings | Keep separate | Fundamental model difference |
| Plugin catalog | Keep in HA only | HA-specific feature |

---

## Implementation Phases

### Phase 1: Create Shared Directory (Non-Breaking)

1. Create `shared/` directory structure
2. Copy Category A files to `shared/`
3. Update imports in both codebases to use `shared/`
4. Verify both deployments still work

**Risk:** Low - additive changes only
**Deliverable:** Working builds with shared core

### Phase 2: Extract Streaming Protocols

1. Create `shared/streaming/` module
2. Extract Sonos, Chromecast, AirPlay, DLNA to separate files
3. Create `StreamingProtocol` base class
4. Update both codebases to use new structure

**Risk:** Medium - protocol code refactoring
**Deliverable:** Unified streaming layer

### Phase 3: Implement Module Interface

1. Add `__feature_name__`, `__required__`, `__depends_on__` to all modules
2. Implement `init()`, `shutdown()`, `health_check()`, `is_available()`
3. Create module loader with graceful degradation
4. Test optional module disable/enable

**Risk:** Medium - structural changes
**Deliverable:** Modular architecture with optional features

### Phase 4: Unify Discovery Interface

1. Define abstract `DiscoveryProvider` interface
2. Implement standalone discovery provider
3. Implement HA registry discovery provider
4. Allow both to coexist (HA can use both sources)

**Risk:** High - core functionality change
**Deliverable:** Unified discovery abstraction

### Phase 5: Frontend Modularization

1. Extract shared JS to `app-core.js`
2. Create platform-specific `app-standalone.js` and `app-ha.js`
3. Build process combines core + platform-specific
4. Test both UIs thoroughly

**Risk:** Medium - UI regression potential
**Deliverable:** Maintainable frontend codebase

### Phase 6: Plugin System Enhancement (Stage 2)

1. Implement API route registration
2. Implement plugin discovery/loading
3. Add plugin management API
4. Add frontend plugin settings UI

**Risk:** Low - additive feature
**Deliverable:** Functional plugin system

---

## File Count Summary

### Current State

| Location | Python Files | JS Files | Total Lines |
|----------|-------------|----------|-------------|
| Standalone | 19 | 1 | ~14,500 |
| HA Addon | 25+ | 1 | ~23,400 |
| **Total** | 44+ | 2 | ~37,900 |
| **Duplicated** | ~8 | 0 | ~5,000 |

### Target State

| Location | Python Files | JS Files | Notes |
|----------|-------------|----------|-------|
| `shared/` | 15 | 1 | Core engine, streaming, plugins |
| `app/core/` | 8 | 1 | Standalone-specific |
| `sonorium_addon/` | 12 | 1 | HA-specific |
| **Total** | 35 | 3 | Reduced duplication |
| **Duplicated** | 0 | 0 | Zero duplication |

---

## Success Criteria

1. **Zero functionality loss** - All features work after restructuring
2. **Zero duplication** - No identical code in multiple locations
3. **Clean interfaces** - All Category B files share the same interface
4. **Graceful degradation** - Optional modules can be disabled
5. **Build success** - Both standalone and HA addon build and run
6. **Test coverage** - Shared code has unit tests

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking HA addon during refactor | HIGH | Incremental changes, extensive testing |
| Import path changes break plugins | MEDIUM | Maintain backwards-compatible imports |
| Performance regression | MEDIUM | Benchmark before/after |
| Missing edge cases | MEDIUM | Comprehensive test suite |
| Git history complexity | LOW | Use merge commits, document changes |

---

## Open Questions

1. **Symlinks vs Copies:** Should `shared/` files be symlinked or copied during build?
2. **Plugin Isolation:** Should plugins have their own virtual environments?
3. **Version Alignment:** How to handle version mismatches between platforms?
4. **CI/CD Updates:** How should the build pipeline change?

---

## Next Steps

1. **Review this document** with stakeholders
2. **Create feature branch** `feature/codebase-restructure`
3. **Begin Phase 1** - Create shared directory
4. **Iterate** through phases with testing at each step
5. **Document** changes for plugin developers

---

## Appendix: Current Function Inventory

### Shared Functions (Move to `shared/`)

**Audio Core:**
- `ExclusionGroupCoordinator` - Exclusive track scheduling
- `RecordingMetadata` - Track metadata
- `RecordingThemeInstance` - Per-theme recording
- `RecordingThemeStream` - Active playback stream
- `CrossfadeRecordingStream` - Crossfade handling
- `SparsePlaybackStream` - Sparse playback
- `PresenceMixingStream` - Presence-based mixing

**Theme Management:**
- `ThemeDefinition` - Theme data model
- `ThemeStream` - Theme audio stream
- `IndexList` - Indexed list utility

**Channel System:**
- `Channel` - Broadcast audio channel
- `ChannelStream` - Client stream view
- `ChannelManager` - Channel lifecycle

**Plugin System:**
- `SonoriumPlugin` - Plugin base class
- `PluginContext` - Plugin execution context
- `PluginState` - Plugin lifecycle state
- `EventBus` - Pub/sub messaging
- `PluginManager` - Plugin discovery/loading

### Platform-Specific Functions

**Standalone Only:**
- `NetworkSpeakerDiscovery` - Direct network scanning
- `discover_dlna()`, `discover_chromecast()`, etc.
- `SonoriumApp` - Desktop app controller
- `check_for_updates()` - Auto-update

**HA Addon Only:**
- `HARegistry` - HA device registry
- `HAMediaController` - HA service calls
- `SonoriumMQTTManager` - MQTT entities
- `SessionMQTTEntities` - Per-session MQTT
- `get_host_ip_from_supervisor()` - Supervisor API
