# Shared Code Directory

This directory contains **shared code** - code that is identical across all Sonorium deployment targets (standalone app, Docker container, Home Assistant addon).

## Why This Exists

**Docker build context prevents imports from parent directories.** When the HA addon builds, its Dockerfile can ONLY access files inside `sonorium_addon/`. Therefore, shared code cannot be imported from a common location - it must be **physically copied** into each target.

## How It Works

```
shared/                           # SOURCE OF TRUTH - Edit HERE
    |
    +--[sync]-->  app/core/sonorium/          (Standalone/Docker)
    |
    +--[sync]-->  sonorium_addon/sonorium/    (Home Assistant Add-on)
```

1. **`shared/` is the source of truth** for all shared code
2. **Pre-commit hook** automatically syncs to deployment targets
3. **Both copies are committed** to git (required for HA one-click install)
4. **GitHub Actions** verifies sync is correct on every push/PR

## THE GOLDEN RULE

| I want to edit... | Edit in... | Why? |
|-------------------|------------|------|
| Plugin system | `shared/plugins/` | Shared code |
| Core audio engine | `shared/core/` | Shared code |
| Optional modules | `shared/modules/` | Shared code |
| Windows-specific | `app/core/sonorium/platform/` | Platform code |
| HA-specific | `sonorium_addon/sonorium/ha/` | Platform code |

**NEVER edit synced files directly. ALWAYS edit in `shared/`.**

## Directory Structure

```
shared/
+-- plugins/                    # Plugin system
|   +-- __init__.py             # Module interface
|   +-- base.py                 # SonoriumPlugin base class
|   +-- manager.py              # Plugin manager
|   +-- loader.py               # Plugin loader
|   +-- context.py              # PluginContext
|   +-- events.py               # EventBus
|   +-- speaker_base.py         # Speaker plugin base
|   +-- builtin/                # Built-in plugins
|       +-- sonos/              # (future) True Sonos plugin
|       +-- airplay/            # (future) True AirPlay plugin
|       +-- chromecast/         # (future) True Chromecast plugin
|
+-- core/                       # (future) Core audio engine
+-- modules/                    # (future) Optional features
```

## Usage

### First-Time Setup

After cloning, set up the pre-commit hook:

```bash
python scripts/setup_hooks.py
```

This ensures `shared/` is automatically synced before every commit.

### Development Workflow

```bash
# 1. Make changes in shared/
# 2. Sync to targets
python scripts/sync_shared.py

# 3. Test the app
# 4. Commit and push
git add -A
git commit -m "your message"
git push sonobleedingedge main
```

### Sync Commands

```bash
python scripts/sync_shared.py           # Sync all
python scripts/sync_shared.py --verbose # With details  
python scripts/sync_shared.py --dry-run # Preview only
```

## Platform-Agnostic Requirements

Code in `shared/` must be 100% platform-agnostic.

**FORBIDDEN:**
```python
import sys
if sys.platform == "win32":  # NO!

import os
os.environ.get("SUPERVISOR_TOKEN")  # NO!
os.environ.get("APPDATA")  # NO!

Path("/config/sonorium")  # NO hardcoded paths!
```

**USE DEPENDENCY INJECTION:**
```python
class MyPlugin:
    def __init__(self, config: RuntimeConfig):
        self.data_dir = config.data_dir  # Injected by platform adapter
```

## Verification

Run before major commits:

```bash
# Should return ZERO results
grep -r "sys.platform" shared/
grep -r "SUPERVISOR_TOKEN" shared/
grep -r "APPDATA" shared/
grep -r '"/config' shared/
grep -r '"/data' shared/
```

## CI Verification

GitHub Actions (`.github/workflows/verify-sync.yml`) runs on every push/PR to verify that `shared/` is correctly synced. If you commit without syncing, CI will fail.

## Adding New Shared Code

1. Add the file/directory to `shared/`
2. Update `SYNC_MAPPINGS` in `scripts/sync_shared.py`
3. Run `python scripts/sync_shared.py`
4. Test both deployments
5. Commit all changes
