# Sonorium Refactor Progress

## Status: IN PROGRESS
Started: 2025-01-20
Last Updated: 2025-01-20

## Current Architecture Problems

### Protocol References in Core (CRITICAL)
| File | Protocol Matches | Status |
|------|------------------|--------|
| `network_speakers.py` | 176 | TO BE EXTRACTED |
| `streaming.py` | 208 | TO BE EXTRACTED |
| **Total** | **384** | Core must have ZERO |

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

## Completed Extractions
| Module | Source | Date | Status | Notes |
|--------|--------|------|--------|-------|
| plugins/ | app/core/sonorium/plugins/ | 2025-01-20 | SYNCED | Now in shared/plugins/ |

## Current Extraction
**Module**: (Analysis phase)
**Source File(s)**: N/A
**Dependencies Identified**: N/A
**Call Sites**: N/A
**Phase**: Pre-analysis - mapping codebase

## Extraction Order (Per FOUNDATIONAL_CHANGES.md)

### Priority 1: True Plugin Extraction
1. Extract Sonos protocol code from core -> `shared/plugins/builtin/sonos/`
2. Extract AirPlay protocol code from core -> `shared/plugins/builtin/airplay/`
3. Extract Chromecast protocol code from core -> `shared/plugins/builtin/chromecast/`
4. Extract DLNA protocol code from core -> `shared/plugins/builtin/dlna/`
5. Extract HEOS protocol code from core -> `shared/plugins/builtin/heos/`

### Priority 2: Platform Adapter Extraction
6. Create `platform/__init__.py` with centralized detection
7. Split `paths.py` -> interface + platform implementations
8. Split `config.py` -> interface + platform implementations
9. Move `update.py` -> `platform/windows/updater.py`

### Priority 3: Core Module Extraction
10. Extract `core/audio.py` - Pure audio mixing
11. Extract `core/themes.py` - Theme management
12. Extract `core/sessions.py` - Session management

## Next Up
1. Analyze `network_speakers.py` - identify all protocol-specific code blocks
2. Analyze `streaming.py` - identify all protocol-specific code blocks
3. Map dependencies between protocol code and core

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
