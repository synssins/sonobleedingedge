# File Alignment Status

This document tracks alignment between the standalone app (`app/core/sonorium/`) and the HA addon (`sonorium_addon/sonorium/`).

## Architecture Vision

| Category | Description | Alignment |
|----------|-------------|-----------|
| **Core** | All application logic - audio, discovery, streaming, plugins, API | Identical across all platforms |
| **Enhancements** | Optional features - speaker protocols, integrations | Platform-agnostic, same code everywhere |
| **Platform Wrappers** | Thin execution layer - launchers, path resolution | Expected to differ per OS/environment |

### Key Principles

1. **Feature Parity**: Every feature available on one platform should be available on all platforms
   - HA addon should support direct device discovery (mDNS/SSDP), not just HA registry
   - Standalone should support HA registration and MQTT server connection

2. **Platform Wrappers = Execution Only**: Platform-specific code should be minimal wrappers for:
   - How the app launches (PyQt6, Docker entrypoint, HA Supervisor)
   - Where files are stored (bundled paths vs mounted volumes)

3. **Settings/File Structure = Identical**: Runtime configuration should be the same everywhere
   - Exception: Media paths (HA/Docker need mount specification, Windows bundles into program folders)

---

## Core Files (Required, Identical)

These files contain all application logic. They must be platform-agnostic and byte-for-byte identical.

### Audio Engine

| File | Purpose | Status |
|------|---------|--------|
| `track.py` | Audio track classes, playback modes, crossfade, streaming | ✓ Identical |
| `theme.py` | Theme definitions, metadata, presets, audio mixing | ✓ Identical |
| `recording.py` | Backward-compat stub (re-exports from `track.py`) | ✓ Identical |

### Foundation

| File | Purpose | Status |
|------|---------|--------|
| `utils.py` | Shared utilities (`IndexList`, `sanitize`, `safe_filename`) | ✓ Identical |
| `obs.py` | Logging with `InstrumentedLogger` | ✓ Identical |
| `paths.py` | Platform-aware path management | ✓ Identical |

### Plugin Infrastructure

| File | Purpose | Status |
|------|---------|--------|
| `plugins/base.py` | Plugin base class | ✓ Identical |
| `plugins/manager.py` | Plugin manager | ✓ Identical |
| `plugins/loader.py` | Plugin loader | ✓ Identical |
| `plugins/context.py` | Plugin context | ✓ Identical |
| `plugins/events.py` | Plugin events | ✓ Identical |
| `plugins/speaker_base.py` | Speaker plugin base | ✓ Identical |

### Needs Migration to Core

These currently exist in only one codebase but should be Core (available everywhere):

| File | Currently In | Should Be | Purpose |
|------|--------------|-----------|---------|
| `network_speakers.py` | Standalone | Core | Direct mDNS/SSDP device discovery |
| `streaming.py` | Standalone | Core | Direct streaming (pyatv, pychromecast) |
| `ha/registry.py` | HA Addon | Core | HA device registry integration |
| `ha/mqtt_entities.py` | HA Addon | Core | MQTT entity exposure |
| `web_api.py` | Standalone | Core | REST API endpoints |
| `config.py` | Standalone | Core | Configuration management |

### Channel System

| File | Purpose | Status |
|------|---------|--------|
| `core/channel.py` | Broadcast audio channels with crossfade, output gain | ✓ Identical |
| `core/speaker_manager.py` | Aggregates speakers from all plugins | ✓ Identical |
| `core/__init__.py` | Core exports (Channel, SpeakerManager) | ✓ Core exports identical |

**Note:** HA addon's `core/__init__.py` also exports HA-specific managers (SessionManager, GroupManager, etc.) which are platform-specific extensions.

### Speaker Plugin Infrastructure

| File | Purpose | Status |
|------|---------|--------|
| `plugins/speaker_base.py` | Base class for speaker protocol plugins | ✓ Identical |

The speaker plugin infrastructure supports:
- Protocol identifier (chromecast, airplay, sonos, dlna)
- Discovery identifiers for mDNS/SSDP service types
- Unified speaker state management
- Volume, mute, play/stop controls

---

## Enhancements (Optional, Platform-Agnostic)

Optional functionality that should work identically on all platforms.

### Builtin Plugins

| Plugin | Purpose | Status |
|--------|---------|--------|
| `plugins/builtin/ambient_mixer/` | Ambient Mixer integration | ✓ Identical |
| `plugins/builtin/theme_merge/` | Theme merging functionality | ✓ Identical |
| `plugins/builtin/mynoise/` | MyNoise integration | ✓ Identical |
| `plugins/builtin/chromecast/` | Chromecast speaker support | ✓ Identical |

### Future Speaker Plugins (Platform-Agnostic)

| Enhancement | Purpose | Status |
|-------------|---------|--------|
| Sonos plugin | Sonos speaker support via SoCo | Planned |
| AirPlay plugin | AirPlay speaker support via pyatv | Planned |
| DLNA plugin | DLNA speaker support | Planned |

---

## Platform Wrappers (Execution Layer Only)

Thin wrappers that handle platform-specific execution. These are the ONLY files expected to differ.

### Windows (`app/windows/`)

| File | Purpose |
|------|---------|
| `launcher.py` | PyQt6 GUI launcher |
| `updater.py` | Windows auto-update |
| `version_info.py` | Windows version metadata |
| `Sonorium.spec` | PyInstaller spec |

### Docker (`app/docker/`)

| File | Purpose |
|------|---------|
| `Dockerfile` | Container build |
| `docker-compose.yml` | Compose configuration |
| `entrypoint.sh` | Container entry point |

### HA Addon (`sonorium_addon/`)

| File | Purpose |
|------|---------|
| `config.yaml` | HA addon configuration schema |
| `Dockerfile` | Addon container build |
| `run.sh` | Addon entry point |

### Legitimate Platform Differences

| Difference | Reason |
|------------|--------|
| Media path resolution | HA/Docker use mounted volumes, Windows bundles into program folders |
| Entry point | Each platform has different launch mechanism |
| Path defaults | OS-specific default locations |

---

## Current State vs Target State

### Currently Platform-Specific (Should Be Core)

These are currently only in one codebase but should be shared Core functionality:

| Feature | Standalone Has | HA Addon Has | Target |
|---------|---------------|--------------|--------|
| Direct mDNS discovery | ✓ | ✗ | Both |
| Direct streaming (pyatv) | ✓ | ✗ | Both |
| HA registry integration | ✗ | ✓ | Both |
| MQTT integration | ✗ | ✓ | Both |
| Local audio output | ✓ | ✗ | Both (where hardware exists) |

### Migration Priority

1. **High**: Device discovery and streaming should work identically
2. **Medium**: HA/MQTT integration available to standalone
3. **Low**: Local audio output (hardware-dependent)

---

## Alignment History

- [x] Batch 1: Foundation (`utils.py`, `obs.py`, `paths.py`)
- [x] Batch 2: Audio Core (`recording.py` → `track.py` rename)
- [x] Batch 3: Theme Core (`theme.py` - merged with metadata/presets)
- [x] Batch 4: Track Core (`track.py` - merged with error handling, random_start)
- [x] Plugin system verification (all identical)
- [x] Batch 5: Channel System (`core/channel.py` - output gain, stereo, BytesIO encoding)
- [x] Core exports alignment (`core/__init__.py` - both export Channel classes)
- [x] Batch 6: Speaker Infrastructure (`speaker_base.py`, `speaker_manager.py`)

## Future Work

1. **Device discovery**: Make `network_speakers.py` available to HA addon
2. **HA integration**: Make registry/MQTT available to standalone
3. **Streaming**: Unify streaming code as Core
4. **Import migration**: Update imports to use `track.py` directly
5. **Speaker plugins**: Convert protocols (AirPlay, Chromecast, Sonos, DLNA) to plugins

## Speaker Plugin Architecture

See `docs/SPEAKER_PLUGIN_ARCHITECTURE.md` for detailed implementation plan.

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Core infrastructure (SpeakerManager, DiscoveryService) | **In Progress** - SpeakerManager done |
| Phase 2 | Refactor existing code (Chromecast, network_speakers.py) | Planned |
| Phase 3 | Create new plugins (AirPlay, Sonos, DLNA) | Planned |
| Phase 4 | UI and API updates | Planned |

### Completed Infrastructure

- `plugins/speaker_base.py` - Enhanced with protocol field and discovery identifiers
- `core/speaker_manager.py` - Aggregates speakers from all enabled speaker plugins
