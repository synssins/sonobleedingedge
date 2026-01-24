#!/usr/bin/env python3
"""
Sync shared code to platform targets.

Source of truth: shared/
Targets:
  - app/core/sonorium/ (Standalone)
  - sonorium_addon/sonorium/ (HA Addon)

IMPORTANT: This script uses REPLACE mode for all directories.
Files in target directories that don't exist in source are DELETED.
This prevents divergence caused by obsolete files.

Usage:
    python scripts/sync_shared.py              # Sync all
    python scripts/sync_shared.py --dry-run    # Preview without changes
    python scripts/sync_shared.py --verbose    # Show all file operations
"""

import argparse
import shutil
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


# Directories to sync from shared/ to targets
# Format: (source_subdir, target_subdir_in_sonorium)
SYNC_DIRS = [
    "core",
    "plugins",
    "platform",
    "models",
    "web",
    "modules",
]

# Target locations relative to project root
TARGETS = [
    "app/core/sonorium",
    "sonorium_addon/sonorium",
]


def sync_directory(
    source: Path,
    target: Path,
    dry_run: bool = False,
    verbose: bool = False
) -> tuple[int, int, int]:
    """
    Sync source directory to target using REPLACE mode.

    Returns: (files_copied, files_deleted, files_unchanged)
    """
    copied = 0
    deleted = 0
    unchanged = 0

    # Create target if it doesn't exist
    if not target.exists():
        if not dry_run:
            target.mkdir(parents=True)
        if verbose:
            print(f"  CREATE {target}")

    # Get all files in source
    source_files = set()
    if source.exists():
        for src_file in source.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(source)
                source_files.add(rel_path)

    # Get all files in target
    target_files = set()
    if target.exists():
        for tgt_file in target.rglob("*"):
            if tgt_file.is_file():
                rel_path = tgt_file.relative_to(target)
                target_files.add(rel_path)

    # Copy/update files from source to target
    for rel_path in source_files:
        src_file = source / rel_path
        tgt_file = target / rel_path

        should_copy = False

        if not tgt_file.exists():
            should_copy = True
            if verbose:
                print(f"  ADD {rel_path}")
        else:
            # Compare content
            if src_file.read_bytes() != tgt_file.read_bytes():
                should_copy = True
                if verbose:
                    print(f"  UPDATE {rel_path}")
            else:
                unchanged += 1

        if should_copy:
            if not dry_run:
                tgt_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, tgt_file)
            copied += 1

    # Delete files in target that don't exist in source (REPLACE mode)
    for rel_path in target_files:
        if rel_path not in source_files:
            tgt_file = target / rel_path
            if verbose:
                print(f"  DELETE {rel_path}")
            if not dry_run:
                tgt_file.unlink()
            deleted += 1

    # Clean up empty directories in target
    if not dry_run and target.exists():
        for dir_path in sorted(target.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                if verbose:
                    print(f"  RMDIR {dir_path.relative_to(target)}")

    return copied, deleted, unchanged


def sync_plugins(dry_run: bool = False, verbose: bool = False) -> tuple[int, int, int]:
    """Sync plugins/ directory to targets."""
    root = get_project_root()
    source = root / "plugins"

    total_copied = 0
    total_deleted = 0
    total_unchanged = 0

    if not source.exists():
        return 0, 0, 0

    for target_base in TARGETS:
        target = root / target_base / "plugins"
        if verbose:
            print(f"\n  Syncing plugins to {target_base}/plugins")
        copied, deleted, unchanged = sync_directory(source, target, dry_run, verbose)
        total_copied += copied
        total_deleted += deleted
        total_unchanged += unchanged

    return total_copied, total_deleted, total_unchanged


def main():
    parser = argparse.ArgumentParser(
        description="Sync shared code to platform targets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show all file operations"
    )

    args = parser.parse_args()

    root = get_project_root()
    source_base = root / "shared"

    if args.dry_run:
        print("DRY RUN - no changes will be made\n")

    total_copied = 0
    total_deleted = 0
    total_unchanged = 0

    # Sync each directory in shared/ to each target
    for sync_dir in SYNC_DIRS:
        source = source_base / sync_dir

        if not source.exists():
            continue

        print(f"Syncing shared/{sync_dir}/")

        for target_base in TARGETS:
            target = root / target_base / sync_dir

            if args.verbose:
                print(f"  -> {target_base}/{sync_dir}")

            copied, deleted, unchanged = sync_directory(
                source, target, args.dry_run, args.verbose
            )

            total_copied += copied
            total_deleted += deleted
            total_unchanged += unchanged

    # Sync plugins separately (from plugins/, not shared/plugins/)
    plugins_source = root / "plugins"
    if plugins_source.exists():
        print(f"\nSyncing plugins/")
        for target_base in TARGETS:
            target = root / target_base / "plugins"
            if args.verbose:
                print(f"  -> {target_base}/plugins")
            copied, deleted, unchanged = sync_directory(
                plugins_source, target, args.dry_run, args.verbose
            )
            total_copied += copied
            total_deleted += deleted
            total_unchanged += unchanged

    # Summary
    print(f"\n{'DRY RUN ' if args.dry_run else ''}Summary:")
    print(f"  Files copied/updated: {total_copied}")
    print(f"  Files deleted: {total_deleted}")
    print(f"  Files unchanged: {total_unchanged}")

    if total_deleted > 0:
        print("\n  Note: Files were deleted because they no longer exist in source.")
        print("  This is expected behavior (REPLACE mode).")

    return 0


if __name__ == "__main__":
    exit(main())
