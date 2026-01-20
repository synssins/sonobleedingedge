# Sonorium Refactor Progress

## Status: PRIORITY 1 COMPLETE - TRUE PLUGINS EXTRACTED
Started: 2025-01-20
Last Updated: 2025-01-20

### Phase 1 Results: All 6 Speaker Protocol Plugins Created
All speaker protocols successfully extracted from core to TRUE plugins in `shared/plugins/builtin/`.

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
| **Sonos** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/sonos/` |
| **Chromecast** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/chromecast/` |
| **DLNA** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/dlna/` |
| **AirPlay** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/airplay/` |
| **HEOS** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/heos/` |
| **Linkplay** | network_speakers.py, streaming.py | 2025-01-20 | ✅ DONE | `shared/plugins/builtin/linkplay/` |

## Current Extraction
**Module**: Priority 1 COMPLETE
**Status**: All 6 speaker protocols extracted as TRUE plugins
**Next Phase**: Priority 2 - Platform Adapter Extraction

---

## Extraction Order (Per FOUNDATIONAL_CHANGES.md)

### Priority 1: True Plugin Extraction (Speaker Protocols) ✅ COMPLETE
Each protocol extracted as TRUE plugin with:
- `__init__.py` - Module exports with Plugin alias
- `manifest.json` - Dependencies, capabilities, settings schema
- `plugin.py` - Full SpeakerPlugin implementation

| # | Protocol | Status | Location | Commits |
|---|----------|--------|----------|---------|
| 1 | Sonos | ✅ DONE | `shared/plugins/builtin/sonos/` | `c12a550` |
| 2 | Chromecast | ✅ DONE | `shared/plugins/builtin/chromecast/` | `fbef2b3` |
| 3 | DLNA | ✅ DONE | `shared/plugins/builtin/dlna/` | `2f2220b` |
| 4 | AirPlay | ✅ DONE | `shared/plugins/builtin/airplay/` | `7e2e284` |
| 5 | HEOS | ✅ DONE | `shared/plugins/builtin/heos/` | `b42814c` |
| 6 | Linkplay | ✅ DONE | `shared/plugins/builtin/linkplay/` | `4dde00b` |

**TRUE Plugin Acid Test**: Delete any plugin folder → feature gone, no errors

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

### Phase 1 (COMPLETE) ✅
1. ✅ Analyze `network_speakers.py` - DONE
2. ✅ Analyze `streaming.py` - DONE
3. ✅ Map file categories - DONE
4. ✅ Create SpeakerPlugin interface in `shared/plugins/speaker_base.py` - DONE
5. ✅ Extract Sonos protocol - DONE
6. ✅ Extract Chromecast protocol - DONE
7. ✅ Extract DLNA protocol - DONE
8. ✅ Extract AirPlay protocol - DONE
9. ✅ Extract HEOS protocol - DONE
10. ✅ Extract Linkplay protocol - DONE

### Phase 2 (PENDING) - Platform Adapter Extraction
1. Create `shared/platform/__init__.py` with RuntimeConfig interface
2. Split `paths.py` into interface + platform implementations
3. Split `config.py` into interface + platform implementations
4. Move `update.py` to `platform/windows/updater.py`

### Phase 3 (PENDING) - Core Module Extraction
1. Extract audio engine to `shared/core/audio.py`
2. Extract theme management to `shared/core/themes.py`
3. Extract session management to `shared/core/sessions.py`

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
