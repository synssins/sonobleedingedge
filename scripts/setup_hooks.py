#!/usr/bin/env python3
"""
Set up git hooks for the Sonorium repository.

Run this once after cloning to enable automatic sync on commit.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def main():
    # Find repo root
    repo_root = Path(__file__).parent.parent

    # Source and destination for hooks
    hooks_src = repo_root / ".githooks"
    hooks_dst = repo_root / ".git" / "hooks"

    if not hooks_dst.exists():
        print(f"Error: {hooks_dst} not found. Are you in a git repository?")
        sys.exit(1)

    print("Setting up git hooks...")

    # Copy each hook
    for hook_file in hooks_src.glob("*"):
        if hook_file.is_file():
            dst = hooks_dst / hook_file.name
            shutil.copy2(hook_file, dst)

            # Make executable (Unix)
            if os.name != 'nt':
                st = os.stat(dst)
                os.chmod(dst, st.st_mode | stat.S_IEXEC)

            print(f"  Installed: {hook_file.name}")

    # Configure git to use our hooks directory (alternative method)
    try:
        subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=repo_root,
            check=True,
            capture_output=True
        )
        print("  Configured git to use .githooks/ directory")
    except subprocess.CalledProcessError:
        print("  Note: Could not set core.hooksPath, using copied hooks instead")

    print("\n✓ Git hooks installed successfully!")
    print("\nThe pre-commit hook will automatically sync shared/ before each commit.")
    print("To manually sync: python scripts/sync_shared.py")


if __name__ == "__main__":
    main()
