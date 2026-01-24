# Sonorium

Multi-zone ambient soundscape mixer for Home Assistant and standalone deployment.

## Project Structure

```
sonobleedingedge/
├── VERSION                       # Single source of truth for version
├── repository.yaml               # HA addon repository manifest
│
├── shared/                       # SOURCE OF TRUTH - Edit HERE ONLY
│   ├── core/                     # Core audio engine, state management
│   ├── plugins/                  # Plugin framework
│   ├── platform/                 # Platform adapter interfaces
│   ├── models/                   # Data models
│   ├── web/                      # Web API and static files
│   └── modules/                  # Optional feature modules
│
├── plugins/                      # Plugin implementations
│   ├── speakers/                 # Speaker protocol plugins
│   │   ├── sonos/
│   │   ├── chromecast/
│   │   ├── airplay/
│   │   ├── dlna/
│   │   ├── linkplay/
│   │   └── heos/
│   └── sources/                  # Audio source plugins
│
├── sonorium_addon/               # Home Assistant Add-on
│   ├── config.yaml               # HA addon configuration
│   ├── Dockerfile
│   ├── run.sh
│   └── sonorium/                 # Python code (synced from shared/)
│       ├── core/                 # ← SYNCED
│       ├── plugins/              # ← SYNCED
│       ├── platform/             # ← SYNCED
│       ├── models/               # ← SYNCED
│       ├── web/                  # ← SYNCED
│       └── ha/                   # HA-SPECIFIC (NOT synced)
│
├── app/                          # Standalone Application
│   ├── core/sonorium/            # Python code (synced from shared/)
│   │   ├── core/                 # ← SYNCED
│   │   ├── plugins/              # ← SYNCED
│   │   ├── platform/             # ← SYNCED
│   │   ├── models/               # ← SYNCED
│   │   ├── web/                  # ← SYNCED
│   │   └── standalone/           # STANDALONE-SPECIFIC (NOT synced)
│   ├── windows/                  # Windows launcher (PyQt6)
│   └── docker/                   # Docker standalone container
│
├── scripts/
│   ├── sync_shared.py            # Sync shared/ to targets
│   └── bump_version.py           # Version management
│
├── docs/                         # Reference documentation
│   ├── FUNCTION_INDEX.md         # Complete function/class index
│   └── ...                       # Architecture and rules docs
│
└── tests/                        # Test suite
```

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

The bump_version.py script automatically updates:
- `VERSION` file
- `sonorium_addon/config.yaml` (for HA one-click updates)
- `pyproject.toml` (if exists)
- `package.json` (if exists)

## Sync System

**Source of truth: `shared/`**

```bash
# Sync shared/ to both platform targets
python scripts/sync_shared.py

# Preview changes without applying
python scripts/sync_shared.py --dry-run

# Show detailed file operations
python scripts/sync_shared.py --verbose
```

The sync script uses **REPLACE mode**: files in targets that don't exist in source are deleted. This prevents divergence.

## Development Workflow

1. **Edit shared code ONLY in `shared/`**
2. **Run sync before commit**: `python scripts/sync_shared.py`
3. **Bump version if needed**: `python scripts/bump_version.py --bump patch`
4. **Commit and push**: `git add -A && git commit -m "message" && git push`

## Platform-Specific Code

| Platform | Location | Purpose |
|----------|----------|---------|
| HA Addon | `sonorium_addon/sonorium/ha/` | MQTT entities, HA registry, Supervisor API |
| Standalone | `app/core/sonorium/standalone/` | Local audio, Windows tray, auto-update |
| Windows | `app/windows/` | PyQt6 launcher, Windows-specific |
| Docker | `app/docker/` | Docker standalone container |

## Git Rules

- **Only remote**: `sonobleedingedge` (https://github.com/synssins/sonobleedingedge)
- **No other remotes** should be used
