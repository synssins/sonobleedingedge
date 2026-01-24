# Sonorium

Multi-zone ambient soundscape mixer for Home Assistant and standalone deployment.

## Project Structure

```
sonobleedingedge/
├── VERSION                       # Single source of truth for version
├── repository.yaml               # HA addon repository manifest
│
├── shared/
│   ├── sonorium/                 # SOURCE OF TRUTH - Edit HERE ONLY
│   │   ├── __init__.py
│   │   ├── core/                 # State, streaming, themes, MQTT, mixer
│   │   ├── models/               # Data models (Speaker, Theme, Session, etc.)
│   │   ├── plugins/              # Plugin system and base classes
│   │   ├── web/                  # FastAPI app and static UI files
│   │   ├── modules/              # Optional feature modules
│   │   └── platform/             # Platform adapter interfaces
│   └── ARCHITECTURE.md           # Architecture documentation
│
├── sonorium_addon/               # Home Assistant Add-on
│   ├── config.yaml               # HA addon configuration
│   ├── Dockerfile
│   ├── run.sh
│   ├── main.py                   # Entry point
│   ├── sonorium/                 # ← SYNCED from shared/sonorium/
│   │   ├── core/
│   │   ├── models/
│   │   ├── plugins/
│   │   ├── web/
│   │   └── ...
│   └── ha/                       # HA-SPECIFIC wrapper (NOT synced)
│       ├── __init__.py
│       ├── settings.py           # Load from HA options
│       ├── supervisor.py         # Supervisor API client
│       ├── registry.py           # HA device registry
│       ├── media_controller.py   # HA media_player control
│       └── mqtt_entities.py      # MQTT Discovery for HA
│
├── standalone_app/               # Standalone Applications
│   ├── windows/
│   │   ├── sonorium/             # ← SYNCED from shared/sonorium/
│   │   ├── wrapper/              # Windows-specific (NOT synced)
│   │   └── main.py               # Entry point
│   └── docker/
│       ├── sonorium/             # ← SYNCED from shared/sonorium/
│       ├── wrapper/              # Docker-specific (NOT synced)
│       ├── main.py               # Entry point
│       ├── Dockerfile
│       └── requirements.txt
│
├── scripts/
│   ├── sync_shared.py            # Sync shared/sonorium/ to all targets
│   └── bump_version.py           # Version management
│
└── tests/                        # Test suite
```

## Sync Architecture

```
shared/sonorium/                      # SOURCE OF TRUTH
    │
    ├──[sync]──> standalone_app/windows/sonorium/
    │
    ├──[sync]──> standalone_app/docker/sonorium/
    │
    └──[sync]──> sonorium_addon/sonorium/
```

**Key principle**: The `sonorium/` folders in each target are **identical copies** of `shared/sonorium/`. Platform-specific wrapper code lives **outside** the `sonorium/` folder and is never synced.

## Version Management

**Single source of truth: `VERSION` file**

```bash
# Show current version
python scripts/bump_version.py

# Bump version
python scripts/bump_version.py --bump patch   # 0.1.0 -> 0.1.1
python scripts/bump_version.py --bump minor   # 0.1.0 -> 0.2.0
python scripts/bump_version.py --bump major   # 0.1.0 -> 1.0.0

# Set explicit version
python scripts/bump_version.py --set 1.2.3

# Sync VERSION to all targets (config.yaml, etc.)
python scripts/bump_version.py --sync
```

## Sync System

**Source of truth: `shared/sonorium/`**

```bash
# Sync to all 3 targets
python scripts/sync_shared.py

# Preview changes without applying
python scripts/sync_shared.py --dry-run

# Show detailed file operations
python scripts/sync_shared.py --verbose
```

The sync script uses **REPLACE mode**: files in targets that don't exist in source are deleted. This prevents divergence.

## Development Workflow

1. **Edit shared code ONLY in `shared/sonorium/`**
2. **Run sync before commit**: `python scripts/sync_shared.py`
3. **Bump version if needed**: `python scripts/bump_version.py --bump patch`
4. **Commit and push**: `git add -A && git commit -m "message" && git push sonobleedingedge main`

## Platform-Specific Code

| Platform | Wrapper Location | Purpose |
|----------|------------------|---------|
| HA Addon | `sonorium_addon/ha/` | MQTT entities, HA registry, Supervisor API |
| Windows | `standalone_app/windows/wrapper/` | Windows-specific features |
| Docker | `standalone_app/docker/wrapper/` | Docker-specific features |

**Important**: Wrapper code must **never** be placed inside `sonorium/` folders. Those are synced and will be overwritten.

## Git Rules

- **Only remote**: `sonobleedingedge` (https://github.com/synssins/sonobleedingedge)
- **No other remotes** should be used
- Run `python scripts/sync_shared.py` before every commit

## Features

- **Multi-zone audio**: Stream ambient soundscapes to multiple network speakers
- **Theme system**: Layered audio themes with presets and track mixing
- **Plugin architecture**: Self-contained ZIP plugins for speaker protocols
- **MQTT control**: Full control via MQTT topics for Node-RED/HA integration
- **Web UI**: Modern web interface for theme selection and speaker management
- **Cross-platform**: Runs on Windows, Linux, Docker, and Home Assistant
