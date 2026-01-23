# Sonorium Refactoring Changelog

This document summarizes the changes made during the platform unification refactoring effort (v0.0.48 - v0.0.60).

---

## Overview

The refactoring unified the codebase between the **Home Assistant Addon** and **Standalone Windows App**, ensuring feature parity and consistent UI across both platforms.

---

## v0.0.61 - Audio Distortion Fix (2026-01-23)

### Critical Bug Fix
- Fixed audio distortion on ALL speakers caused by excessive gain
- `DEFAULT_OUTPUT_GAIN` was set to 6.0 (6x amplification) causing severe clipping
- Changed to 1.0 (unity gain) in both `theme.py` and `channel.py`
- Audio now plays cleanly at all volume levels

---

## v0.0.60 - Speaker UI Polish (2026-01-23)

### Speaker Enable/Disable Fix
- Fixed enabled state not displaying correctly for network speakers
- Backend now tracks all original speaker IDs when merging duplicates
- Returns `enabled` field pre-calculated and `original_ids` array for proper toggling
- Toggling a unified speaker now affects all its protocol-specific entries

### Collapsible Sections
- Added collapsible sections to speaker settings view
- Click section header (Floor, Area, Network Discovered) to collapse/expand
- Chevron icon indicates expanded/collapsed state
- Collapse state persisted in localStorage across sessions
- Works on both standalone and HA addon

### UI Cleanup
- Removed redundant globe indicator from network speakers
- Cleaner speaker entry layout

---

## v0.0.59 - Speaker Deduplication (2026-01-23)

### Unified Speaker Deduplication
- Standalone `/api/speakers/unified` now uses `SpeakerDeduplicator` class
- Speakers discovered via multiple protocols (DLNA, AirPlay, Linkplay, etc.) merge into single entry
- Matching by IP address, MAC address, or UUID
- `found_by` field contains all discovery protocols as badges
- Standalone UI now matches addon UI format

---

## v0.0.58 - HA/MQTT Settings UI (2026-01-23)

### User-Friendly Labels
- Changed "Supervisor URL" to "Home Assistant URL"
- Added placeholder: `http://homeassistant.local:8123`
- Added hint with IP address example

### Layout Fixes
- Fixed toggle switch overlapping with text labels
- Added `.setting-item` and `.setting-value` CSS for proper form row layout

---

## v0.0.57 - Update System (2026-01-23)

### Check for Updates Button
- Added "Check for Updates" button to main launcher window
- Added "Check for Updates Now" in Settings > Updates tab
- Added periodic update check every 4 hours (silent, background)

### Web UI Status Page
- Added Software Updates section to Status page
- Shows current version and update status with icons
- Manual "Check for Updates" button

---

## v0.0.56 - Auto-Install Updates (2026-01-23)

### Streamlined Update Flow
- Removed extra click requirement after download finishes
- Update automatically installs when download completes
- Status shows "Download complete! Installing..."

---

## v0.0.55 - HA/MQTT Integration Page Redesign (2026-01-23)

### New Integration UI
- Inline status display with icons (Status: Connected ✓)
- Autodetect toggles for HA and MQTT (enabled by default)
- Manual configuration fields appear when autodetect disabled
- Save/Cancel buttons for manual configuration
- Renamed menu item from "Integration" to "HA/MQTT"

### Backend Updates
- Added handling for `ha_autodetect`, `mqtt_autodetect`, `ha_url`, `ha_token`
- New CSS styles for status display

---

## v0.0.54 - Integration & Persistence Fixes (2026-01-23)

### New Endpoints
- Added `/api/capabilities` endpoint to standalone
- Added `/api/settings/integration` endpoints for MQTT configuration
- Added MQTT fields to standalone AppConfig

### Bug Fixes
- Fixed network speakers not selectable (added toggle to `renderDirectOnlySpeaker`)
- Fixed speaker disable not persisting (initialize enabled list on first disable)
- Fixed session state path for HA addon (use `sonorium.paths` for persistent storage)

---

## v0.0.53 - Capabilities & Speaker Selection (2026-01-22)

### Capabilities Endpoint
- Added `/api/capabilities` to HA addon for proper HA/MQTT detection
- Moved to shared `api_v2.py` for sync compatibility

### Speaker Management
- Added Integration settings UI with HA/MQTT status display
- Fixed speaker enable/disable for network speakers in standalone
- Added `enable-all`/`disable-all` endpoints
- Include all discovered speakers in hierarchy (not just enabled)
- Added `enabled_speakers` list to hierarchy response

---

## v0.0.52 - Missing Endpoints (2026-01-22)

### New Endpoints
- Added `/api/speakers/scan-network` (alias for `network-speakers/refresh`)
- Added `/api/speakers/unified` for standalone

### Bug Fix
- Fixed plugin install error: `'AppConfig' object has no attribute 'settings'`
- Now uses unified settings manager

---

## v0.0.51 - Unified Platform Capabilities (2026-01-22)

### Platform Capabilities System
- Unified capability detection across platforms
- Consistent settings system for both standalone and addon

---

## v0.0.50 - Core Code Consolidation (2026-01-22)

### Shared Code Architecture
- Consolidated CORE code to `shared/` directory
- Platform parity between addon and standalone
- Sync script ensures identical core behavior

---

## v0.0.48-0.0.49 - Platform Extraction (2026-01-22)

### Architecture Foundation
- Extracted core modules to `shared/` for platform parity
- Established sync workflow between platforms
- Set up `scripts/sync_shared.py` for automated code propagation

---

## Known Issues

### Speaker Validation False Negatives
- **Symptom:** Speakers marked "unavailable" at startup even when online
- **Affected:** `network_speakers.py` validation code
- **Status:** Noted for future investigation
- **Impact:** Display only - doesn't affect functionality

---

## File Changes Summary

### New Files
- `shared/models/speaker_dedup.py` - Speaker deduplication logic
- `shared/models/speaker_model.py` - Unified speaker data model
- `shared/web/api_v2.py` - Shared API endpoints

### Modified Files (Key Changes)
| File | Changes |
|------|---------|
| `app/core/sonorium/web_api.py` | Unified speakers endpoint, capabilities, settings |
| `shared/web/static/js/app.js` | Collapsible sections, speaker toggle, dedup display |
| `shared/web/static/css/styles.css` | Collapsible UI, setting layout, speaker badges |
| `shared/web/templates/index.html` | HA/MQTT settings page, Status updates section |
| `app/windows/src/launcher.py` | Check for Updates button, periodic checking |

### Sync System
All changes to `shared/` are automatically propagated to:
- `app/core/sonorium/` (Standalone)
- `sonorium_addon/sonorium/` (HA Addon)

---

## Testing Checklist

- [x] Speaker deduplication shows single entry per device
- [x] Protocol badges display correctly (AIRPLAY, DLNA, LINKPLAY, etc.)
- [x] IP addresses shown on speaker entries
- [x] Enable/disable persists across sessions
- [x] Collapsible sections remember state
- [x] HA/MQTT settings save correctly
- [x] Update check works from UI
- [ ] Speaker validation accuracy (known issue)

---

*Generated: 2026-01-23*
