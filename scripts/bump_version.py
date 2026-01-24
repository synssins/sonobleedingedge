#!/usr/bin/env python3
"""
Version management for Sonorium.

Single source of truth: VERSION file in project root.
This script propagates the version to all necessary locations.

Usage:
    python scripts/bump_version.py                    # Show current version
    python scripts/bump_version.py --bump patch      # 0.1.0 -> 0.1.1
    python scripts/bump_version.py --bump minor      # 0.1.0 -> 0.2.0
    python scripts/bump_version.py --bump major      # 0.1.0 -> 1.0.0
    python scripts/bump_version.py --set 1.2.3       # Set explicit version
    python scripts/bump_version.py --sync            # Sync VERSION to all targets
"""

import argparse
import re
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def read_version() -> str:
    """Read version from VERSION file."""
    version_file = get_project_root() / "VERSION"
    if not version_file.exists():
        raise FileNotFoundError("VERSION file not found in project root")
    return version_file.read_text().strip()


def write_version(version: str) -> None:
    """Write version to VERSION file."""
    version_file = get_project_root() / "VERSION"
    version_file.write_text(f"{version}\n")
    print(f"Updated VERSION file: {version}")


def bump_version(current: str, bump_type: str) -> str:
    """Bump version according to semver."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", current)
    if not match:
        raise ValueError(f"Invalid version format: {current}")

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    suffix = match.group(4)  # Preserve any suffix like -dev, -beta, etc.

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return f"{major}.{minor}.{patch}{suffix}"


def update_ha_addon_config(version: str) -> bool:
    """Update version in sonorium_addon/config.yaml."""
    config_file = get_project_root() / "sonorium_addon" / "config.yaml"

    if not config_file.exists():
        print(f"  [SKIP] {config_file.relative_to(get_project_root())} - file not found")
        return False

    content = config_file.read_text()

    # Match version line in YAML (version: "x.x.x" or version: x.x.x)
    pattern = r'^(version:\s*)["\']?[\d.]+["\']?\s*$'
    replacement = f'version: "{version}"'

    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

    if count > 0:
        config_file.write_text(new_content)
        print(f"  [OK] {config_file.relative_to(get_project_root())} -> {version}")
        return True
    else:
        print(f"  [WARN] {config_file.relative_to(get_project_root())} - version line not found")
        return False


def update_pyproject_toml(version: str) -> bool:
    """Update version in pyproject.toml if it exists."""
    pyproject_file = get_project_root() / "pyproject.toml"

    if not pyproject_file.exists():
        return False

    content = pyproject_file.read_text()

    # Match version in [project] or [tool.poetry] section
    pattern = r'^(version\s*=\s*)["\'][\d.]+["\']\s*$'
    replacement = f'version = "{version}"'

    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

    if count > 0:
        pyproject_file.write_text(new_content)
        print(f"  [OK] pyproject.toml -> {version}")
        return True

    return False


def update_package_json(version: str) -> bool:
    """Update version in package.json if it exists."""
    import json

    package_file = get_project_root() / "package.json"

    if not package_file.exists():
        return False

    try:
        data = json.loads(package_file.read_text())
        if "version" in data:
            data["version"] = version
            package_file.write_text(json.dumps(data, indent=2) + "\n")
            print(f"  [OK] package.json -> {version}")
            return True
    except json.JSONDecodeError:
        print(f"  [WARN] package.json - invalid JSON")

    return False


def sync_all(version: str) -> None:
    """Sync version to all target files."""
    print(f"\nSyncing version {version} to all targets:")

    # Required targets
    update_ha_addon_config(version)

    # Optional targets (may not exist)
    update_pyproject_toml(version)
    update_package_json(version)

    print("\nVersion sync complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Sonorium version management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--bump",
        choices=["major", "minor", "patch"],
        help="Bump version (major, minor, or patch)"
    )
    parser.add_argument(
        "--set",
        metavar="VERSION",
        help="Set explicit version (e.g., 1.2.3)"
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync current VERSION to all target files"
    )

    args = parser.parse_args()

    try:
        current_version = read_version()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    if args.bump:
        new_version = bump_version(current_version, args.bump)
        write_version(new_version)
        sync_all(new_version)
        print(f"\nVersion bumped: {current_version} -> {new_version}")
    elif args.set:
        # Validate version format
        if not re.match(r"^\d+\.\d+\.\d+", args.set):
            print(f"Error: Invalid version format: {args.set}")
            return 1
        write_version(args.set)
        sync_all(args.set)
        print(f"\nVersion set: {current_version} -> {args.set}")
    elif args.sync:
        sync_all(current_version)
    else:
        print(f"Current version: {current_version}")
        print("\nUse --bump, --set, or --sync to modify version.")

    return 0


if __name__ == "__main__":
    exit(main())
