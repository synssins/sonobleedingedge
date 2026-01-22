#!/usr/bin/env python3
"""
Sync shared code and plugins to deployment targets.

This script copies files from shared/ and plugins/ to both:
- app/core/sonorium/ (standalone app)
- sonorium_addon/sonorium/ (HA addon)

Run this before committing changes to shared/ or plugins/ files.
"""

import argparse
import shutil
import sys
from pathlib import Path


# Sync from shared/ directory (plugin system, platform adapters, core modules)
SHARED_MAPPINGS = [
    # (source in shared/, destination subdirectory)
    ("plugins", "plugins"),           # Plugin system (base.py, speaker_base.py, etc.)
    ("platform", "platform"),         # Platform adapters (PathProvider, ConfigProvider)
    ("models", "models"),             # Platform-agnostic data models (UnifiedSpeaker, etc.)
    ("network", "network"),           # Network utilities (subnet detection, etc.)
    # Future extractions:
    ("modules", "modules"),           # Optional features (recording, etc.)
]

# Sync from root plugins/ directory (actual plugin packages)
PLUGIN_MAPPINGS = [
    # (source in plugins/, destination in plugins/)
    ("speakers", "speakers"),         # Speaker protocol plugins
    ("sources", "sources"),           # Audio source plugins
]


def sync_directory(src_path: Path, dst_path: Path, verbose: bool = False) -> int:
    """
    Sync a source directory to destination.
    Returns number of files synced.
    """
    if not src_path.exists():
        return 0

    # Remove destination if it exists
    if dst_path.exists():
        if dst_path.is_dir():
            shutil.rmtree(dst_path)
        else:
            dst_path.unlink()

    # Copy source to destination
    if src_path.is_dir():
        shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        count = sum(1 for _ in dst_path.rglob('*') if _.is_file())
        if verbose:
            print(f"  Synced directory: {src_path.name} -> {dst_path}")
        return count
    else:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        if verbose:
            print(f"  Synced file: {src_path.name} -> {dst_path}")
        return 1


def sync_to_target(repo_root: Path, target_dir: Path, verbose: bool = False) -> int:
    """
    Sync shared files and plugins to a target directory.
    Returns number of files synced.
    """
    files_synced = 0
    shared_dir = repo_root / "shared"
    plugins_dir = repo_root / "plugins"

    # Sync from shared/
    for src_name, dst_name in SHARED_MAPPINGS:
        src_path = shared_dir / src_name
        dst_path = target_dir / dst_name

        if not src_path.exists():
            if verbose:
                print(f"  Warning: Source {src_path} does not exist, skipping")
            continue

        files_synced += sync_directory(src_path, dst_path, verbose)

    # Sync plugins from root plugins/ to target plugins/
    for src_name, dst_name in PLUGIN_MAPPINGS:
        src_path = plugins_dir / src_name
        dst_path = target_dir / "plugins" / dst_name

        if not src_path.exists():
            if verbose:
                print(f"  Warning: Source {src_path} does not exist, skipping")
            continue

        files_synced += sync_directory(src_path, dst_path, verbose)

    return files_synced


def main():
    parser = argparse.ArgumentParser(description="Sync shared code and plugins to deployment targets")
    parser.add_argument("--standalone", action="store_true", help="Sync to standalone app only")
    parser.add_argument("--addon", action="store_true", help="Sync to HA addon only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    args = parser.parse_args()

    # Find repo root (where this script lives in scripts/)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    shared_dir = repo_root / "shared"
    plugins_dir = repo_root / "plugins"
    standalone_target = repo_root / "app" / "core" / "sonorium"
    addon_target = repo_root / "sonorium_addon" / "sonorium"

    # Validate paths
    if not shared_dir.exists():
        print(f"Error: shared/ directory not found at {shared_dir}")
        sys.exit(1)

    # Determine targets
    sync_standalone = args.standalone or (not args.standalone and not args.addon)
    sync_addon = args.addon or (not args.standalone and not args.addon)

    if args.dry_run:
        print("DRY RUN - No files will be modified")
        print(f"\nShared directory: {shared_dir}")
        print(f"Plugins directory: {plugins_dir}")
        print(f"\nShared mappings:")
        for src, dst in SHARED_MAPPINGS:
            print(f"  shared/{src} -> {dst}")
        print(f"\nPlugin mappings:")
        for src, dst in PLUGIN_MAPPINGS:
            print(f"  plugins/{src} -> plugins/{dst}")
        if sync_standalone:
            print(f"\nWould sync to standalone: {standalone_target}")
        if sync_addon:
            print(f"Would sync to HA addon: {addon_target}")
        return

    total_files = 0

    if sync_standalone:
        if not standalone_target.exists():
            print(f"Warning: Standalone target not found at {standalone_target}, skipping")
        else:
            print(f"Syncing to standalone app: {standalone_target}")
            count = sync_to_target(repo_root, standalone_target, args.verbose)
            print(f"  Synced {count} files")
            total_files += count

    if sync_addon:
        if not addon_target.exists():
            print(f"Warning: HA addon target not found at {addon_target}, skipping")
        else:
            print(f"Syncing to HA addon: {addon_target}")
            count = sync_to_target(repo_root, addon_target, args.verbose)
            print(f"  Synced {count} files")
            total_files += count

    print(f"\nTotal: {total_files} files synced")


if __name__ == "__main__":
    main()
