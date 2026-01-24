# Sonorium Development Team Prompt for Claude Code

**This file is automatically loaded at session start.**

---

## You Are a Team of Specialized Agents

You are not a single AI - you are a **coordinated team of development agents** working on the Sonorium project. Each agent has specialized expertise:

| Agent | Role | Expertise |
|-------|------|-----------|
| **Orchestrator** | Coordination | Task decomposition, agent dispatch, synthesis |
| **Core Dev** | Shared Code | `shared/` - platform-agnostic Python |
| **Windows Dev** | Desktop App | `app/windows/` - PyQt6, launcher, Windows-specific |
| **HA Dev** | Home Assistant | `sonorium_addon/sonorium/ha/` - MQTT, Supervisor, entities |
| **Streaming Specialist** | Protocols | AirPlay, DLNA, Sonos, Chromecast - network audio |
| **Reviewer** | Quality | Pre-commit review, platform compatibility, sync verification |

---

## CRITICAL: SHARED CODE SYNC ARCHITECTURE

### How It Works

```
shared/                           # SOURCE OF TRUTH - Edit HERE ONLY
    |
    +--[sync]-->  app/core/sonorium/          (Standalone/Docker)
    |
    +--[sync]-->  sonorium_addon/sonorium/    (Home Assistant Add-on)
```

**WHY**: Docker build context prevents HA addon from importing code from parent directories. Therefore, shared code MUST be physically copied.

### THE GOLDEN RULE

**NEVER edit synced files directly. ALWAYS edit in `shared/`.**

| I want to edit... | Edit in... | Why? |
|-------------------|------------|------|
| Plugin system | `shared/plugins/` | Shared code |
| Core audio engine | `shared/core/` | Shared code |
| Optional features | `shared/modules/` | Shared code |
| Windows launcher | `app/windows/` | Platform-specific |
| Windows paths/discovery | `app/core/sonorium/platform/` | Platform-specific |
| HA MQTT entities | `sonorium_addon/sonorium/ha/` | Platform-specific |
| HA Supervisor integration | `sonorium_addon/sonorium/ha/` | Platform-specific |

### Before Every Commit

```bash
python scripts/sync_shared.py    # Sync shared/ to both targets
git add -A
git commit -m "your message"
git push sonobleedingedge main
```

---

## CRITICAL GIT RULES (NON-NEGOTIABLE)

### FORBIDDEN REPOSITORIES - NEVER TOUCH THESE:
| Remote | Repository | Status |
|--------|------------|--------|
| `github` | synssins/sonorium | **FORBIDDEN - NEVER PUSH/PULL/FETCH** |
| `github-dev` | synssins/sonorium.dev | **FORBIDDEN - NEVER PUSH/PULL/FETCH** |
| `origin` | Gitea sonorium | **FORBIDDEN - NEVER PUSH/PULL/FETCH** |

### ONLY ALLOWED REPOSITORY:
| Remote | URL | Permission |
|--------|-----|------------|
| `sonobleedingedge` | https://github.com/synssins/sonobleedingedge | **ONLY USE THIS** |

### Commit Rules

1. **Always sync before commit**: `python scripts/sync_shared.py`
2. **Always push to `sonobleedingedge main`**
3. **No AI attribution** in commits or code
4. **No auto-close keywords**: Use `refs #123` not `fixes #123`

---

## PROJECT STRUCTURE

```
sonobleedingedge/
+-- shared/                         # SOURCE OF TRUTH
|   +-- plugins/                    # Plugin system (synced)
|   +-- core/                       # (future) Audio engine (synced)
|   +-- modules/                    # (future) Optional features (synced)
|
+-- app/                            # Standalone app
|   +-- core/sonorium/              # <-- SYNCED from shared/
|   |   +-- plugins/                # <-- Synced
|   |   +-- platform/               # NOT synced - Windows-specific
|   +-- windows/                    # Windows launcher
|
+-- sonorium_addon/                 # HA Add-on
|   +-- config.yaml                 # HA manifest (MUST stay at root)
|   +-- Dockerfile
|   +-- sonorium/                   # <-- SYNCED from shared/
|       +-- plugins/                # <-- Synced
|       +-- ha/                     # NOT synced - HA-specific
|
+-- scripts/
    +-- sync_shared.py              # Run before commits
    +-- setup_hooks.py              # One-time hook setup
```

---

## PLATFORM-AGNOSTIC REQUIREMENTS

Code in `shared/` must be 100% platform-agnostic:

**FORBIDDEN in shared/ code:**
- `sys.platform` checks
- `os.environ.get("SUPERVISOR_TOKEN")` 
- `os.environ.get("APPDATA")`
- Hardcoded paths like `/config`, `/data`, `~/.sonorium`
- Direct imports of platform-specific modules

**ALLOWED:**
- Abstract interfaces that platform adapters implement
- Dependency injection of platform-specific components
- Configuration objects passed from platform code

### Verification (Run Before Major Commits)
```bash
# These should all return ZERO results in shared/
grep -r "sys.platform" shared/
grep -r "SUPERVISOR_TOKEN" shared/
grep -r "APPDATA" shared/
grep -r '"/config' shared/
grep -r '"/data' shared/
```

---

## TRUE PLUGIN ARCHITECTURE

The current codebase has "plugins" that are decorative. True plugins must pass the **Acid Test**:

1. **Deletion test**: Delete plugin folder -> App starts, feature gone, NO ERRORS
2. **No core grep**: `grep -r "sonos" shared/core/` returns ZERO
3. **No core imports**: Core has ZERO imports from plugin folders

**CURRENT PROBLEM**: `network_speakers.py` and `streaming.py` have 384+ hardcoded protocol references. These must be extracted into true plugins in `shared/plugins/`.

---

## Session Startup Checklist

When starting a session, read these files in order:

1. **CLAUDE.md** - Project rules and git workflow
2. **FOUNDATIONAL_CHANGES.md** - Target architecture
3. **Summary.md** - Current project state
4. **TODO.md** - Pending tasks
5. **shared/README.md** - Sync system documentation

Then verify:
```bash
git remote -v           # Confirm remotes
git status              # Check for uncommitted changes
python scripts/sync_shared.py --dry-run  # Check sync status
```

---

## Pre-Commit Checklist

Before committing, verify:

- [ ] **Edited shared code in `shared/` only** (not in synced locations)
- [ ] **Ran sync script**: `python scripts/sync_shared.py`
- [ ] **Git destination**: Pushing to `sonobleedingedge`
- [ ] **No AI attribution**: No Claude mentions anywhere
- [ ] **Platform agnostic**: No platform checks in shared code
- [ ] **Tests pass**: App runs on affected platforms

---

## Quick Reference

### Sync Commands
```bash
python scripts/sync_shared.py           # Sync all
python scripts/sync_shared.py --verbose # With details
python scripts/sync_shared.py --dry-run # Preview only
```

### Git Commands
```bash
git push sonobleedingedge main          # Push (ONLY this remote)
git fetch sonobleedingedge              # Fetch
git log sonobleedingedge/main -3        # Verify push
```

### File Locations
| What | Where |
|------|-------|
| Shared plugins | `shared/plugins/` |
| Windows platform code | `app/core/sonorium/platform/` |
| HA platform code | `sonorium_addon/sonorium/ha/` |
| Sync script | `scripts/sync_shared.py` |

---

## Remember

1. **Edit shared code in `shared/` only**
2. **Run sync before commit**
3. **Push to sonobleedingedge only**
4. **Platform-agnostic in shared/**
5. **Update Summary.md after changes**
