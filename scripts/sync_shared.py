#!/usr/bin/env python3
"""
Sync shared code to deployment targets.

This script copies files from shared/ to both:
- app/core/sonorium/ (standalone app)
- sonorium_addon/sonorium/ (HA addon)

Run this before committing changes to shared/ files.
GitHub Actions also runs this to sync to the HA addon repo.
"""

import argparse
import shutil
import sys
from pathlib import Path


# Define what gets synced from shared/ to each target
# Only directories/files that EXIST in shared/ will be synced.
# Missing sources are skipped with a warning.
SYNC_MAPPINGS = [
    # (source in shared/, destination subdirectory)
    # Currently active:
    ("plugins", "plugins"),
    ("platform", "platform"),   # Platform adapters (PathProvider, ConfigProvider)
    # Future extractions (will activate as we create them):
    ("core", "core"),           # Pure audio engine, themes, sessions
    ("modules", "modules"),     # Optional features (recording, etc.)
]


def sync_to_target(shared_dir: Path, target_dir: Path, verbose: bool = False) -> int:
    """
    Sync shared files to a target directory.

    Returns number of files synced.
    """
    files_synced = 0

    for src_name, dst_name in SYNC_MAPPINGS:
        src_path = shared_dir / src_name
        dst_path = target_dir / dst_name

        if not src_path.exists():
            print(f"  Warning: Source {src_path} does not exist, skipping")
            continue

        # Remove destination if it exists
        if dst_path.exists():
            if dst_path.is_dir():
                shutil.rmtree(dst_path)
            else:
                dst_path.unlink()

        # Copy source to destination
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            # Count files
            files_synced += sum(1 for _ in dst_path.rglob('*') if _.is_file())
            if verbose:
                print(f"  Synced directory: {src_name} -> {dst_path}")
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            files_synced += 1
            if verbose:
                print(f"  Synced file: {src_name} -> {dst_path}")

    return files_synced


def main():
    parser = argparse.ArgumentParser(description="Sync shared code to deployment targets")
    parser.add_argument("--standalone", action="store_true", help="Sync to standalone app only")
    parser.add_argument("--addon", action="store_true", help="Sync to HA addon only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be synced")
    args = parser.parse_args()

    # Find repo root (where this script lives in scripts/)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    shared_dir = repo_root / "shared"
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
        print(f"Mappings to sync:")
        for src, dst in SYNC_MAPPINGS:
            print(f"  {src} -> {dst}")
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
            count = sync_to_target(shared_dir, standalone_target, args.verbose)
            print(f"  Synced {count} files")
            total_files += count

    if sync_addon:
        if not addon_target.exists():
            print(f"Warning: HA addon target not found at {addon_target}, skipping")
        else:
            print(f"Syncing to HA addon: {addon_target}")
            count = sync_to_target(shared_dir, addon_target, args.verbose)
            print(f"  Synced {count} files")
            total_files += count

    print(f"\nTotal: {total_files} files synced")


if __name__ == "__main__":
    main()
