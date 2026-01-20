"""
Sonorium Updater - Standalone update utility.

This small executable handles the update process:
1. Force-closes Sonorium.exe if running
2. Waits for the process to fully exit
3. Replaces the old executable with the new one
4. Launches the updated application
5. Cleans up temporary files

Usage:
    updater.exe --target "path/to/Sonorium.exe" --update "path/to/new_Sonorium.exe"
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def log(msg: str):
    """Print timestamped log message."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def find_and_kill_process(exe_name: str, max_wait: int = 10) -> bool:
    """
    Find and kill a process by executable name.

    Args:
        exe_name: Name of the executable (e.g., "Sonorium.exe")
        max_wait: Maximum seconds to wait for process to exit

    Returns:
        True if process was killed or wasn't running, False on failure
    """
    log(f"Looking for running {exe_name} processes...")

    try:
        # Use tasklist to find the process
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True
        )

        if exe_name.lower() not in result.stdout.lower():
            log(f"No {exe_name} process found")
            return True

        log(f"Found {exe_name} running, attempting to close...")

        # Try graceful termination first
        subprocess.run(
            ["taskkill", "/IM", exe_name],
            capture_output=True
        )

        # Wait for process to exit
        for i in range(max_wait):
            time.sleep(1)
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True
            )
            if exe_name.lower() not in result.stdout.lower():
                log(f"{exe_name} closed gracefully")
                return True
            log(f"Waiting for {exe_name} to close... ({i+1}/{max_wait})")

        # Force kill if still running
        log(f"{exe_name} didn't close gracefully, force killing...")
        subprocess.run(
            ["taskkill", "/F", "/IM", exe_name],
            capture_output=True
        )

        # Final check
        time.sleep(1)
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True
        )

        if exe_name.lower() not in result.stdout.lower():
            log(f"{exe_name} force killed successfully")
            return True
        else:
            log(f"ERROR: Could not kill {exe_name}")
            return False

    except Exception as e:
        log(f"ERROR: Exception while killing process: {e}")
        return False


def replace_executable(target: Path, update: Path) -> bool:
    """
    Replace the target executable with the update.

    Args:
        target: Path to the current executable to replace
        update: Path to the new executable

    Returns:
        True on success, False on failure
    """
    log(f"Replacing {target.name}...")

    # Create backup
    backup = target.with_suffix(".exe.bak")

    try:
        # Remove old backup if exists
        if backup.exists():
            backup.unlink()
            log("Removed old backup")

        # Rename current to backup
        if target.exists():
            target.rename(backup)
            log(f"Created backup: {backup.name}")

        # Move update to target
        shutil.move(str(update), str(target))
        log(f"Installed new version")

        # Remove backup on success
        if backup.exists():
            backup.unlink()
            log("Removed backup")

        return True

    except PermissionError as e:
        log(f"ERROR: Permission denied - {e}")
        # Try to restore backup
        if backup.exists() and not target.exists():
            backup.rename(target)
            log("Restored from backup")
        return False

    except Exception as e:
        log(f"ERROR: {e}")
        # Try to restore backup
        if backup.exists() and not target.exists():
            backup.rename(target)
            log("Restored from backup")
        return False


def launch_application(exe_path: Path) -> bool:
    """Launch the updated application."""
    log(f"Launching {exe_path.name}...")

    try:
        subprocess.Popen(
            [str(exe_path)],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            close_fds=True
        )
        log("Application launched")
        return True
    except Exception as e:
        log(f"ERROR: Could not launch application: {e}")
        return False


def cleanup(update_path: Path):
    """Clean up temporary files."""
    try:
        if update_path.exists():
            update_path.unlink()
            log(f"Cleaned up: {update_path.name}")
    except Exception as e:
        log(f"Warning: Could not clean up {update_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Sonorium Updater")
    parser.add_argument("--target", required=True, help="Path to Sonorium.exe to update")
    parser.add_argument("--update", required=True, help="Path to the new executable")
    parser.add_argument("--no-launch", action="store_true", help="Don't launch after update")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't delete update file")

    args = parser.parse_args()

    target = Path(args.target)
    update = Path(args.update)

    print("=" * 50)
    print("Sonorium Updater")
    print("=" * 50)
    log(f"Target: {target}")
    log(f"Update: {update}")
    print()

    # Validate paths
    if not update.exists():
        log(f"ERROR: Update file not found: {update}")
        input("Press Enter to exit...")
        sys.exit(1)

    # Step 1: Kill Sonorium if running
    if not find_and_kill_process("Sonorium.exe"):
        log("ERROR: Could not close Sonorium. Please close it manually and try again.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Small delay to ensure file handles are released
    time.sleep(1)

    # Step 2: Replace executable
    if not replace_executable(target, update):
        log("ERROR: Could not replace executable.")
        input("Press Enter to exit...")
        sys.exit(1)

    # Step 3: Launch updated application
    if not args.no_launch:
        if not launch_application(target):
            log("Warning: Could not auto-launch. Please start Sonorium manually.")

    # Step 4: Cleanup (update file already moved, but clean any temp files)
    if not args.no_cleanup:
        # The update file was moved, not copied, so nothing to clean
        pass

    print()
    log("Update completed successfully!")
    print("=" * 50)

    # Brief pause so user can see the result
    time.sleep(2)


if __name__ == "__main__":
    main()
