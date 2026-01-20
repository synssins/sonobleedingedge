# Claude Code Prompt: Sonorium Code Deconstruction - CAUTIOUS INCREMENTAL REFACTOR

## CRITICAL SAFETY PRINCIPLES

You are about to begin a major code refactoring of Sonorium. This is a SURGICAL operation, not demolition. The app must remain functional at EVERY step.

---

## MANDATORY: Read These Files First

1. `CLAUDE.md` - Project rules and sync architecture
2. `FOUNDATIONAL_CHANGES.md` - Target architecture and true plugin requirements
3. `CLAUDE_GIT_SAFETY.md` - Git safety rules (never push to production)
4. `shared/README.md` - Sync system documentation
5. `docs/sonorium-plugin-architecture.md` - Plugin system specification

Confirm you understand:
1. **Sync architecture**: Edit in `shared/`, sync to targets, commit
2. **Git safety**: ONLY push to sonobleedingedge
3. **True plugin architecture**: Core has ZERO protocol knowledge
4. **Platform agnostic**: No platform checks in shared code

---

## THE GOLDEN RULES

### Rule 1: NEVER Break Functionality
- The app MUST work after every single change
- If a refactor breaks something, STOP and fix it before continuing
- Test after each file extraction

### Rule 2: One File At A Time
- Extract ONE module at a time
- Complete the full cycle (extract -> test -> archive) before moving to the next
- Never have multiple half-finished extractions in progress

### Rule 3: Archive, Don't Delete
- Old files go to `_archive/` with timestamps
- NEVER delete original files until the new version is proven working
- Archive format: `_archive/YYYY-MM-DD/original_filename.py`

### Rule 4: Edit Shared Code in shared/ ONLY
- **NEVER edit synced files** in `app/core/sonorium/plugins/` or `sonorium_addon/sonorium/plugins/`
- **ALWAYS edit in `shared/`** and run sync before commit
- The sync script overwrites destination files

### Rule 5: Document Every Change
- Update REFACTOR_PROGRESS.md after each extraction
- Note what was moved, what depends on it, what was tested

### Rule 6: Commit Frequently
- Run `python scripts/sync_shared.py` before EVERY commit
- Commit after each successful extraction
- Small, atomic commits that can be reverted individually

---

## ARCHIVE STRUCTURE

Create this structure before starting:

```
sonobleedingedge/
+-- _archive/                      # Archived old code (NEVER delete)
|   +-- 2026-01-20/               # Date-stamped folders
|       +-- original_file.py      # Original files before refactor
|       +-- ARCHIVE_LOG.md        # What was archived and why
+-- _refactor_log/                 # Refactoring documentation
    +-- REFACTOR_PROGRESS.md      # Track what's done, what's next
```

---

## THE EXTRACTION CYCLE

For EACH module extraction, follow this EXACT sequence:

### Phase 1: ANALYZE (Do NOT write code yet)
```
1. Identify the target functionality to extract
2. Map ALL dependencies (what imports it, what it imports)
3. Identify ALL call sites in the codebase
4. Document the extraction plan in REFACTOR_PROGRESS.md
5. ASK USER: "I plan to extract [X] from [Y]. Dependencies: [list]. Proceed?"
```

### Phase 2: SCAFFOLD (Create empty structure)
```
1. Create the new module file IN shared/ (not in synced locations)
2. Add the module metadata (__feature_name__, __required__, etc.)
3. Create stub functions that call back to original code
4. Run sync: python scripts/sync_shared.py
5. Verify app still works with stubs in place
6. COMMIT: "scaffold: add [module] structure with stubs"
```

### Phase 3: MIGRATE (Move code incrementally)
```
1. Move ONE function/class at a time from old to new (in shared/)
2. Update imports in old file to use new module
3. Run sync: python scripts/sync_shared.py
4. Test after EACH function move
5. Continue until all target code is in new module
6. COMMIT after each working state: "migrate: move [function] to [module]"
```

### Phase 4: VERIFY (Thorough testing)
```
1. Run the standalone application
2. Test the specific functionality that was moved
3. Test the HA addon (if possible)
4. Check for import errors, runtime errors
5. Document test results in REFACTOR_PROGRESS.md
```

### Phase 5: ARCHIVE (Clean up old code)
```
1. Create dated archive folder if not exists
2. Copy original file to archive (DO NOT move yet)
3. Remove migrated code from original file
4. If original file is now empty/obsolete, move entire file to archive
5. Update ARCHIVE_LOG.md with what was archived
6. COMMIT: "archive: move obsolete [file] to _archive"
```

### Phase 6: CHECKPOINT
```
1. Verify app runs correctly
2. Run platform-agnostic verification:
   grep -r "sys.platform" shared/
   grep -r "SUPERVISOR_TOKEN" shared/
   (both should return nothing)
3. Update REFACTOR_PROGRESS.md with completion status
4. ASK USER: "[Module] extraction complete. Ready for next module?"
```

---

## CRITICAL: WHAT GOES WHERE

### Code that belongs in `shared/`
- Plugin system base classes and manager
- True speaker plugins (Sonos, AirPlay, Chromecast, DLNA, HEOS)
- Core audio engine (themes, channels, sessions)
- Web API endpoints (platform-agnostic parts)
- Optional feature modules

### Code that stays in platform directories
- Windows: `app/core/sonorium/platform/` - Windows paths, updater, tray
- HA: `sonorium_addon/sonorium/ha/` - MQTT entities, Supervisor API, HA registry

### Platform-Agnostic Requirements for shared/

**FORBIDDEN in shared/ code:**
```python
# These are NOT allowed in shared/
import sys
if sys.platform == "win32":  # NO!

import os
os.environ.get("SUPERVISOR_TOKEN")  # NO!
os.environ.get("APPDATA")  # NO!

Path("/config/sonorium")  # NO hardcoded paths!
Path("/data")  # NO!
```

**ALLOWED pattern:**
```python
# Use dependency injection instead
class SpeakerPlugin:
    def __init__(self, config: RuntimeConfig):
        self.data_dir = config.data_dir  # Injected by platform adapter
```

---

## EXTRACTION ORDER

### Priority 1: Plugin System (In Progress)
Already partially done in `shared/plugins/`. Complete the extraction of speaker protocols.

### Priority 2: Speaker Protocol Extraction (CRITICAL)
The 384 protocol references in `network_speakers.py` and `streaming.py` must become TRUE plugins:

1. `shared/plugins/speakers/sonos/` - Sonos discovery + streaming
2. `shared/plugins/speakers/airplay/` - AirPlay discovery + streaming  
3. `shared/plugins/speakers/chromecast/` - Chromecast discovery + streaming
4. `shared/plugins/speakers/dlna/` - DLNA discovery + streaming
5. `shared/plugins/speakers/heos/` - HEOS discovery + streaming

**Acid Test**: After extraction, these commands should return ZERO:
```bash
grep -r "sonos" shared/core/
grep -r "chromecast" shared/core/
grep -r "airplay" shared/core/
grep -r "pychromecast\|soco\|pyatv" shared/core/
```

### Priority 3: Core Modules
3. `shared/core/audio.py` - Audio mixing, channel management
4. `shared/core/themes.py` - Theme loading, asset management
5. `shared/core/sessions.py` - Session management

### Priority 4: Optional Modules
6. `shared/modules/api.py` - REST API
7. `shared/modules/websocket.py` - Real-time updates
8. `shared/modules/scheduler.py` - Automation

---

## COMMIT WORKFLOW

```bash
# After making changes in shared/
python scripts/sync_shared.py    # MANDATORY before commit
git add -A
git commit -m "refactor: extract [X] - tested working"
git push sonobleedingedge main
```

---

## FORBIDDEN ACTIONS

- DO NOT edit synced files directly (edit in shared/ only)
- DO NOT delete any file without archiving first
- DO NOT extract multiple modules simultaneously
- DO NOT skip the sync step before commits
- DO NOT commit broken code
- DO NOT add platform checks to shared/ code
- DO NOT add hardcoded paths to shared/ code
- DO NOT push to any repo except sonobleedingedge

---

## VERIFICATION COMMANDS

Run these to verify platform-agnostic compliance:

```bash
# Should all return ZERO results for shared/ directory
grep -r "sys.platform" shared/
grep -r "SUPERVISOR_TOKEN" shared/
grep -r "DOCKER_CONTAINER" shared/
grep -r "APPDATA" shared/
grep -r '"/config' shared/
grep -r '"/data' shared/

# After speaker protocol extraction, should return ZERO for shared/core/
grep -r "sonos\|chromecast\|airplay\|dlna\|heos" shared/core/
```

---

## SUCCESS CRITERIA

The refactor is successful when:

- All shared code is in `shared/` and synced to both targets
- Each plugin passes the Acid Test (delete folder = feature gone, no errors)
- `shared/` contains ZERO platform-specific code
- `shared/core/` contains ZERO speaker protocol references
- All original functionality is preserved
- Sync verification passes in CI
- Both standalone and HA addon work correctly
