#!/usr/bin/env python3
"""
Single-source version management for Sonorium.

Usage:
    python scripts/bump_version.py patch          # 0.0.7 -> 0.0.8
    python scripts/bump_version.py minor          # 0.0.7 -> 0.1.0
    python scripts/bump_version.py major          # 0.0.7 -> 1.0.0
    python scripts/bump_version.py 1.2.3          # Set exact version
    python scripts/bump_version.py --check        # Verify all files match
    python scripts/bump_version.py patch --dry-run # Preview changes
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Repository root
REPO_ROOT = Path(__file__).parent.parent

# All version file locations
VERSION_FILES = {
    "root": REPO_ROOT / "VERSION",
    "standalone": REPO_ROOT / "app" / "core" / "sonorium" / "version",
    "addon": REPO_ROOT / "sonorium_addon" / "sonorium" / "version",
    "addon_config": REPO_ROOT / "sonorium_addon" / "config.yaml",
    "version_json": REPO_ROOT / "app" / "core" / "version.json",
    "launcher": REPO_ROOT / "app" / "windows" / "src" / "launcher.py",
}


def get_current_version() -> str:
    """Get current version from the root VERSION file (or standalone if root doesn't exist)."""
    if VERSION_FILES["root"].exists():
        return VERSION_FILES["root"].read_text(encoding='utf-8').strip()
    elif VERSION_FILES["standalone"].exists():
        return VERSION_FILES["standalone"].read_text(encoding='utf-8').strip()
    else:
        return "0.0.0"


def parse_version(version: str) -> tuple:
    """Parse version string into (major, minor, patch, prerelease)."""
    # Remove 'v' prefix if present
    v = version.lstrip('v')
    
    # Split prerelease
    if '-' in v:
        main, prerelease = v.split('-', 1)
    else:
        main, prerelease = v, None
    
    parts = main.split('.')
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    
    return major, minor, patch, prerelease


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type (major, minor, patch)."""
    major, minor, patch, _ = parse_version(current)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        # Assume it's an exact version
        return bump_type.lstrip('v')


def update_plain_version_file(path: Path, version: str, dry_run: bool = False) -> bool:
    """Update a plain text version file."""
    if not path.parent.exists():
        print(f"  [SKIP] {path} (directory doesn't exist)")
        return False

    if dry_run:
        print(f"  [DRY-RUN] Would write '{version}' to {path}")
        return True

    path.write_text(version + "\n", encoding='utf-8')
    print(f"  [OK] {path}")
    return True


def update_config_yaml(path: Path, version: str, dry_run: bool = False) -> bool:
    """Update version in HA addon config.yaml."""
    if not path.exists():
        print(f"  [SKIP] {path} (doesn't exist)")
        return False
    
    content = path.read_text(encoding='utf-8')
    new_content = re.sub(
        r'^version:\s*.*$',
        f'version: "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    if dry_run:
        if new_content != content:
            print(f"  [DRY-RUN] Would update {path}")
        else:
            print(f"  [DRY-RUN] {path} already at {version}")
        return True
    
    if new_content != content:
        path.write_text(new_content, encoding='utf-8')
        print(f"  [OK] {path}")
    else:
        print(f"  [OK] {path} (already at {version})")
    return True


def update_version_json(path: Path, version: str, dry_run: bool = False) -> bool:
    """Update version in version.json."""
    if not path.exists():
        print(f"  [SKIP] {path} (doesn't exist)")
        return False
    
    content = path.read_text(encoding='utf-8')
    data = json.loads(content)
    old_version = data.get("version", "0.0.0")
    data["version"] = version
    
    if dry_run:
        if old_version != version:
            print(f"  [DRY-RUN] Would update {path}: {old_version} -> {version}")
        else:
            print(f"  [DRY-RUN] {path} already at {version}")
        return True
    
    path.write_text(json.dumps(data, indent=2) + "\n", encoding='utf-8')
    print(f"  [OK] {path}")
    return True


def update_launcher_py(path: Path, version: str, dry_run: bool = False) -> bool:
    """Update APP_VERSION in launcher.py."""
    if not path.exists():
        print(f"  [SKIP] {path} (doesn't exist)")
        return False
    
    content = path.read_text(encoding='utf-8')
    new_content = re.sub(
        r'APP_VERSION\s*=\s*["\'][^"\']+["\']',
        f'APP_VERSION = "{version}"',
        content
    )
    
    if dry_run:
        if new_content != content:
            print(f"  [DRY-RUN] Would update {path}")
        else:
            print(f"  [DRY-RUN] {path} already at {version}")
        return True
    
    if new_content != content:
        path.write_text(new_content, encoding='utf-8')
        print(f"  [OK] {path}")
    else:
        print(f"  [OK] {path} (already at {version})")
    return True


def check_versions() -> bool:
    """Check if all version files are in sync."""
    versions = {}
    
    # Read all versions
    for name, path in VERSION_FILES.items():
        if not path.exists():
            continue
            
        if name in ["root", "standalone", "addon"]:
            versions[name] = path.read_text(encoding='utf-8').strip()
        elif name == "addon_config":
            content = path.read_text(encoding='utf-8')
            match = re.search(r'^version:\s*"?([^"\n]+)"?', content, re.MULTILINE)
            if match:
                versions[name] = match.group(1)
        elif name == "version_json":
            data = json.loads(path.read_text(encoding='utf-8'))
            versions[name] = data.get("version", "unknown")
        elif name == "launcher":
            content = path.read_text(encoding='utf-8')
            match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                versions[name] = match.group(1)
    
    # Check if all match
    unique_versions = set(versions.values())
    
    print("Version file status:")
    for name, version in versions.items():
        print(f"  {name}: {version}")
    
    if len(unique_versions) == 1:
        print(f"\n[OK] All versions in sync: {unique_versions.pop()}")
        return True
    else:
        print(f"\n[ERROR] Version mismatch detected!")
        print(f"  Found versions: {unique_versions}")
        return False


def update_all_versions(version: str, dry_run: bool = False) -> None:
    """Update all version files to the specified version."""
    print(f"Updating all files to version: {version}")
    if dry_run:
        print("(DRY RUN - no files will be modified)\n")
    else:
        print()
    
    # Root VERSION file (create if doesn't exist)
    update_plain_version_file(VERSION_FILES["root"], version, dry_run)
    
    # Standalone version
    update_plain_version_file(VERSION_FILES["standalone"], version, dry_run)
    
    # HA addon version
    update_plain_version_file(VERSION_FILES["addon"], version, dry_run)
    
    # HA addon config.yaml
    update_config_yaml(VERSION_FILES["addon_config"], version, dry_run)
    
    # version.json
    update_version_json(VERSION_FILES["version_json"], version, dry_run)
    
    # launcher.py
    update_launcher_py(VERSION_FILES["launcher"], version, dry_run)
    
    if not dry_run:
        print(f"\nDone! All files updated to {version}")
        print("Don't forget to commit: git add -A && git commit -m 'chore: bump version to {}'".format(version))


def main():
    parser = argparse.ArgumentParser(description="Sonorium version manager")
    parser.add_argument("version", nargs="?", help="Version to set (major/minor/patch or exact version)")
    parser.add_argument("--check", action="store_true", help="Check if all versions are in sync")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    
    args = parser.parse_args()
    
    if args.check:
        sys.exit(0 if check_versions() else 1)
    
    if not args.version:
        # No version specified, show current and check
        current = get_current_version()
        print(f"Current version: {current}\n")
        check_versions()
        return
    
    current = get_current_version()
    
    if args.version in ["major", "minor", "patch"]:
        new_version = bump_version(current, args.version)
        print(f"Bumping {args.version}: {current} -> {new_version}\n")
    else:
        new_version = args.version.lstrip('v')
        print(f"Setting version: {current} -> {new_version}\n")
    
    update_all_versions(new_version, args.dry_run)


if __name__ == "__main__":
    main()
