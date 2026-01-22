#!/usr/bin/env python3
"""
Sync core files between standalone and HA addon.

Core files that MUST be identical across all platforms:
- recording.py      - Audio engine
- theme.py          - Theme management
- track.py          - Track/layer handling
- utils.py          - Shared utilities
- obs.py            - Logging
- network_speakers.py - Direct speaker discovery
- streaming.py      - Direct speaker control

The HA Addon has the SAME capabilities as Standalone.
HA-specific code (ha/) is ADDITIONAL, not a replacement.
"""

import argparse
import shutil
import sys
from pathlib import Path
import filecmp

# Core files that must be identical
# These give both platforms the same feature set
CORE_FILES = [
    "recording.py",        # Audio engine
    "theme.py",            # Theme management
    "track.py",            # Track/layer handling
    "utils.py",            # Shared utilities
    "obs.py",              # Logging
    "network_speakers.py", # Direct speaker discovery (mDNS, SSDP, protocols)
    "streaming.py",        # Direct speaker control (pyatv, soco, pychromecast)
]


def main():
    parser = argparse.ArgumentParser(
        description="Sync core files between standalone and HA addon",
        epilog="The HA Addon has the SAME feature set as Standalone, plus HA integration."
    )
    parser.add_argument("--check", action="store_true", 
                        help="Only check if files are identical (don't sync)")
    parser.add_argument("--source", choices=["standalone", "addon"], default="standalone",
                        help="Which target to use as source (default: standalone)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show file sizes")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    
    standalone = repo_root / "app" / "core" / "sonorium"
    addon = repo_root / "sonorium_addon" / "sonorium"
    
    if args.source == "standalone":
        source_dir = standalone
        dest_dir = addon
        source_name = "Standalone"
        dest_name = "HA Addon"
    else:
        source_dir = addon
        dest_dir = standalone
        source_name = "HA Addon"
        dest_name = "Standalone"
    
    print(f"Source: {source_name} ({source_dir})")
    print(f"Destination: {dest_name} ({dest_dir})")
    print()
    
    all_identical = True
    synced_count = 0
    
    for filename in CORE_FILES:
        src_file = source_dir / filename
        dst_file = dest_dir / filename
        
        if not src_file.exists():
            print(f"[MISSING] {filename} not in {source_name}")
            all_identical = False
            continue
            
        if not dst_file.exists():
            print(f"[MISSING] {filename} not in {dest_name}")
            all_identical = False
            if not args.check:
                shutil.copy2(src_file, dst_file)
                print(f"  -> Copied from {source_name}")
                synced_count += 1
            continue
        
        if filecmp.cmp(src_file, dst_file, shallow=False):
            if args.verbose:
                size = src_file.stat().st_size
                print(f"[OK] {filename} ({size:,} bytes)")
            else:
                print(f"[OK] {filename}")
        else:
            src_size = src_file.stat().st_size
            dst_size = dst_file.stat().st_size
            print(f"[DIFFERENT] {filename} ({source_name}: {src_size:,}, {dest_name}: {dst_size:,})")
            all_identical = False
            if not args.check:
                shutil.copy2(src_file, dst_file)
                print(f"  -> Synced from {source_name}")
                synced_count += 1
    
    print()
    if all_identical:
        print("✓ All core files are identical!")
        print("  Both platforms have the same feature set.")
    elif args.check:
        print("✗ Files differ! Run without --check to sync.")
        sys.exit(1)
    else:
        print(f"✓ Synced {synced_count} core files.")
        print("  Both platforms now have the same feature set.")


if __name__ == "__main__":
    main()
