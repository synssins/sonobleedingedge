#!/usr/bin/env python3
"""
Version bump script for Sonorium.

Updates version in all required locations:
- shared/sonorium/VERSION (source of truth)
- sonorium_addon/config.yaml (HA addon version)

Usage:
    python scripts/bump_version.py patch    # 0.1.7 -> 0.1.8
    python scripts/bump_version.py minor    # 0.1.7 -> 0.2.0
    python scripts/bump_version.py major    # 0.1.7 -> 1.0.0
    python scripts/bump_version.py 0.2.0    # Set specific version

After running, commit and push. GitHub Actions will NOT run since
this script updates all files. Use this for local development.

For CI/CD, just update shared/sonorium/VERSION and push - the GitHub
Action will sync to other files automatically.
"""

import sys
import re
from pathlib import Path


# Version file locations (relative to repo root)
VERSION_FILE = Path("shared/sonorium/VERSION")
CONFIG_YAML = Path("sonorium_addon/config.yaml")


def get_repo_root() -> Path:
    """Find repository root."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Not in a git repository")


def read_version(repo_root: Path) -> str:
    """Read current version from VERSION file."""
    version_path = repo_root / VERSION_FILE
    if not version_path.exists():
        raise FileNotFoundError(f"VERSION file not found: {version_path}")
    return version_path.read_text().strip()


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string to tuple."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    major, minor, patch = parse_version(current)

    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "major":
        return f"{major + 1}.0.0"
    else:
        # Assume it's a specific version
        parse_version(bump_type)  # Validate format
        return bump_type


def update_version_file(repo_root: Path, new_version: str) -> None:
    """Update the VERSION file."""
    version_path = repo_root / VERSION_FILE
    version_path.write_text(f"{new_version}\n")
    print(f"  Updated: {VERSION_FILE} -> {new_version}")


def update_config_yaml(repo_root: Path, new_version: str) -> None:
    """Update version in config.yaml."""
    config_path = repo_root / CONFIG_YAML
    if not config_path.exists():
        print(f"  Warning: {CONFIG_YAML} not found, skipping")
        return

    content = config_path.read_text()
    updated = re.sub(
        r'^version:\s*["\']?[\d.]+["\']?',
        f'version: "{new_version}"',
        content,
        flags=re.MULTILINE
    )
    config_path.write_text(updated)
    print(f"  Updated: {CONFIG_YAML} -> {new_version}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    bump_type = sys.argv[1].lower()

    try:
        repo_root = get_repo_root()
        current_version = read_version(repo_root)
        new_version = bump_version(current_version, bump_type)

        print(f"Bumping version: {current_version} -> {new_version}")
        print()

        update_version_file(repo_root, new_version)
        update_config_yaml(repo_root, new_version)

        print()
        print("Done! Now run:")
        print("  python scripts/sync_shared.py")
        print(f'  git add -A && git commit -m "chore: bump version to {new_version}"')
        print("  git push sonobleedingedge main")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
