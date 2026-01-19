# Shared Code Directory

This directory contains **Category A** files - code that is identical across all Sonorium deployment targets (standalone app, Docker container, Home Assistant addon).

## How It Works

1. **`shared/` is the source of truth** for all Category A code
2. **`scripts/sync_shared.py`** copies files to deployment targets:
   - `app/core/sonorium/` (standalone)
   - `sonorium_addon/sonorium/` (HA addon)
3. **GitHub Actions** automatically syncs to the HA addon repository

## Directory Structure

```
shared/
├── plugins/           # Plugin system (Stage 1 complete)
│   ├── __init__.py    # Module interface
│   ├── base.py        # SonoriumPlugin base class
│   ├── manager.py     # Plugin manager
│   ├── loader.py      # Plugin loader
│   ├── context.py     # PluginContext
│   ├── events.py      # EventBus
│   └── builtin/       # Built-in plugins
│
├── (future)
│   ├── recording.py   # Audio engine
│   ├── themes.py      # Theme management
│   ├── channel.py     # Broadcast model
│   └── streaming/     # Protocol implementations
```

## Usage

### Local Development

After modifying files in `shared/`, run the sync script:

```bash
# Sync to both targets
python scripts/sync_shared.py

# Sync to standalone only
python scripts/sync_shared.py --standalone

# Sync to HA addon only
python scripts/sync_shared.py --addon

# Dry run (see what would be synced)
python scripts/sync_shared.py --dry-run

# Verbose output
python scripts/sync_shared.py --verbose
```

### Automated Sync (CI)

The GitHub Actions workflow `.github/workflows/sync-ha-addon.yml`:
1. Triggers on pushes to `main` or `dev` that modify `shared/` or `sonorium_addon/`
2. Runs the sync script
3. Pushes the complete addon to the separate HA repository

## Rules

1. **NEVER edit synced files directly** in `app/core/sonorium/` or `sonorium_addon/sonorium/`
2. **ALWAYS edit in `shared/`** and run the sync script
3. **Run sync before committing** any changes to shared code
4. **The sync script overwrites** destination files - any local changes will be lost

## Adding New Shared Files

1. Add the file/directory to `shared/`
2. Update `SYNC_MAPPINGS` in `scripts/sync_shared.py`
3. Run the sync script
4. Test both deployments

## File Categories

| Category | Location | Description |
|----------|----------|-------------|
| **A (Shared)** | `shared/` | Identical across all platforms |
| **B (Adapters)** | Platform dirs | Same interface, different implementation |
| **C (Exclusive)** | Platform dirs | Platform-specific only |

See `docs/CODEBASE_RESTRUCTURING_PLAN.md` for the full categorization.
