# Shared Code Directory

This directory is the **SOURCE OF TRUTH** for code that must be identical across all deployment targets.

## Core Principle

**The CORE CODE is IDENTICAL across ALL platforms. ALWAYS.**

This includes:
- Audio engine (recording, mixing, playback)
- Theme management
- Track/layer handling
- Plugin framework
- Shared utilities

## Current State

**Currently synced from shared/:**
- `plugins/` - Plugin framework (base classes, manager, loader)
- `platform/` - Platform adapter interfaces

**Currently maintained in BOTH locations (must stay identical):**
- `recording.py` - Audio engine
- `theme.py` - Theme management
- `track.py` - Track/layer handling
- `utils.py` - Shared utilities
- `obs.py` - Logging

**Future:** Move core files here and sync automatically.

## Sync System

```
shared/plugins/     →  app/core/sonorium/plugins/
shared/plugins/     →  sonorium_addon/sonorium/plugins/

shared/platform/    →  app/core/sonorium/platform/
shared/platform/    →  sonorium_addon/sonorium/platform/

plugins/speakers/   →  app/core/sonorium/plugins/speakers/
plugins/speakers/   →  sonorium_addon/sonorium/plugins/speakers/
```

## Why Files Must Be Copied (Not Imported)

**Docker build context limitation:** When the HA addon builds, its Dockerfile can ONLY access files inside `sonorium_addon/`. It CANNOT import from `../shared/` or `../app/`.

Therefore, shared code must be **physically copied** into the addon folder.

## Workflow

```bash
# For plugin framework changes:
vim shared/plugins/base.py
python scripts/sync_shared.py
git add -A && git commit && git push sonobleedingedge main

# For core file changes (temporary - until extracted):
vim app/core/sonorium/recording.py
python scripts/sync_core.py  # Copies to HA addon
git add -A && git commit && git push sonobleedingedge main

# To verify core files are identical:
python scripts/sync_core.py --check
```

## Directory Structure

```
shared/
├── plugins/                    # Plugin framework (SYNCED)
│   ├── __init__.py
│   ├── base.py                 # SonoriumPlugin base class
│   ├── speaker_base.py         # SpeakerPlugin base class
│   ├── manager.py              # Plugin manager
│   ├── loader.py               # Plugin loader
│   ├── context.py              # PluginContext
│   └── events.py               # EventBus
│
├── platform/                   # Platform adapter interfaces (SYNCED)
│   ├── __init__.py
│   └── adapters.py
│
└── core/                       # (FUTURE) Core code to extract here
    ├── recording.py
    ├── theme.py
    ├── track.py
    └── utils.py
```
