# Sonorium Refactor Progress

## Status: IN PROGRESS
Started: 2025-01-20
Last Updated: 2025-01-20

---

## Current Architecture Problems

### Protocol References in Core (CRITICAL)

**network_speakers.py** (Discovery):
| Protocol | References | Methods |
|----------|------------|---------|
| Sonos | 20 | `_discover_sonos` |
| Chromecast | 22 | `_discover_chromecast` |
| AirPlay | 28 | `_discover_airplay`, `_discover_mdns` |
| DLNA | 22 | `_discover_dlna` |
| HEOS | 65 | `_discover_heos`, `_find_heos_hosts_*`, `_get_heos_players`, `_create_heos_speaker` |
| Linkplay | 21 | `_discover_linkplay` |
| **Total** | **~178** | |

**streaming.py** (Playback):
| Protocol | References | Methods |
|----------|------------|---------|
| Sonos | 19 | `_start_sonos`, `_stop_sonos` |
| Chromecast | 27 | `_start_chromecast`, `_stop_chromecast` |
| AirPlay | 66 | `_start_airplay`, `_stop_airplay` |
| DLNA | 28 | `_start_dlna`, `_stop_dlna`, `_create_didl_metadata` |
| HEOS | 55 | `_start_heos`, `_stop_heos` |
| Linkplay | 40 | `_start_linkplay_http`, `_stop_linkplay_http`, `_is_linkplay_device` |
| **Total** | **~235** | |

**COMBINED TOTAL: ~413 protocol references** (must become ZERO in core)

### Platform Detection Duplication
| File | Issue |
|------|-------|
| `paths.py` | `sys.platform`, hardcoded paths |
| `obs.py` | `SUPERVISOR_TOKEN` check |
| `context.py` | Platform detection logic |
| `config.py` | Environment variable checks |

### Environment Variable Contamination
Core files directly check: `SUPERVISOR_TOKEN`, `APPDATA`, `XDG_CONFIG_HOME`, `DOCKER_CONTAINER`, `SONORIUM_DATA_DIR`

---

## File Categories

### Category A: True Shared Code (Must Go in shared/)
Files that MUST be identical across platforms:

| File | Purpose | Current Location |
|------|---------|------------------|
| `plugins/` | Plugin system | `shared/plugins/` (DONE) |
| `core/channel.py` | Channel/layer logic | TBD |
| `core/theme_metadata.py` | Theme parsing | TBD |
| `core/cycle_manager.py` | Cycle timing | TBD |
| `recording.py` | Audio mixing engine | Needs extraction |
| `theme.py` | Theme management | Needs extraction |

### Category B: Same Purpose, Different Implementation
Files that serve same function but have platform-specific code:

| File | Standalone | HA Addon | Notes |
|------|------------|----------|-------|
| `paths.py` | Windows/Docker paths | HA `/config` paths | Need adapter pattern |
| `config.py` | JSON config | HA options.json | Need adapter pattern |
| `web_api.py` | FastAPI routes | Different HA routes | Different features |
| `app.js` | Different speaker UI | Different speaker UI | HA has hierarchy tree |

### Category C: Platform-Exclusive
Files that only exist on one platform:

| Standalone Only | HA Addon Only |
|-----------------|---------------|
| `update.py` | `ha/registry.py` |
| `audio_output.py` | `ha/mqtt_entities.py` |
| `local_stream_player.py` | `ha/media_controller.py` |
| `network_speakers.py` | `ha/sonos_player.py` |
| `streaming.py` | `ha/cast_player.py` |
| `pyatv_patches.py` | - |

---

## Completed Extractions
| Module | Source | Date | Status | Notes |
|--------|--------|------|--------|-------|
| plugins/ | app/core/sonorium/plugins/ | 2025-01-20 | SYNCED | Now in shared/plugins/ |

## Current Extraction
**Module**: Protocol analysis phase
**Source File(s)**: network_speakers.py, streaming.py
**Dependencies Identified**: See breakdown above
**Call Sites**: N/A
**Phase**: Analysis complete - ready for extraction planning

---

## Extraction Order (Per FOUNDATIONAL_CHANGES.md)

### Priority 1: True Plugin Extraction (Speaker Protocols)
Each protocol needs:
- Discovery component (from network_speakers.py)
- Streaming component (from streaming.py)
- Registration with core via SpeakerPlugin interface

| # | Protocol | Discovery LOC | Streaming LOC | Target |
|---|----------|---------------|---------------|--------|
| 1 | Sonos | ~50 | ~80 | `shared/plugins/builtin/sonos/` |
| 2 | AirPlay | ~100 | ~150 | `shared/plugins/builtin/airplay/` |
| 3 | Chromecast | ~40 | ~60 | `shared/plugins/builtin/chromecast/` |
| 4 | DLNA | ~60 | ~70 | `shared/plugins/builtin/dlna/` |
| 5 | HEOS | ~200 | ~100 | `shared/plugins/builtin/heos/` |
| 6 | Linkplay | ~80 | ~80 | `shared/plugins/builtin/linkplay/` |

### Priority 2: Platform Adapter Extraction
| # | Task | Notes |
|---|------|-------|
| 6 | Create `shared/platform/__init__.py` | RuntimeConfig interface |
| 7 | Split `paths.py` | Interface + Windows/Docker/HA implementations |
| 8 | Split `config.py` | Interface + platform implementations |
| 9 | Move `update.py` | `platform/windows/updater.py` |

### Priority 3: Core Module Extraction
| # | Task | Target |
|---|------|--------|
| 10 | Extract audio engine | `shared/core/audio.py` |
| 11 | Extract theme management | `shared/core/themes.py` |
| 12 | Extract session management | `shared/core/sessions.py` |

---

## Next Steps
1. ✅ Analyze `network_speakers.py` - DONE
2. ✅ Analyze `streaming.py` - DONE
3. ✅ Map file categories - DONE
4. **NEXT**: Create SpeakerPlugin interface in `shared/plugins/speaker_base.py`
5. Begin Sonos extraction (smallest protocol footprint)

## Blocked / Issues
(none yet)

## Archive Log
See: `_archive/ARCHIVE_LOG.md`

---

## Verification Checklist (Must All Pass When Complete)

```bash
# No platform checks in shared/
grep -r "sys.platform|SUPERVISOR_TOKEN|DOCKER_CONTAINER" shared/
# Expected: ZERO results

# No hardcoded paths in shared/
grep -r '"/config|"/data|APPDATA|\.sonorium' shared/
# Expected: ZERO results

# No speaker protocols in shared/core/
grep -r "sonos|chromecast|airplay|dlna|heos|pychromecast|soco|pyatv" shared/core/
# Expected: ZERO results

# No HA specifics in shared/
grep -r "SUPERVISOR|mqtt_entities|media_player\." shared/
# Expected: ZERO results
```
