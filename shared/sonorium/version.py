"""
Version utilities for Sonorium.

Separated module to avoid circular imports between app.py and api.py.
Exports both get_version() function and __version__ variable for compatibility.
"""

from pathlib import Path


def get_version() -> str:
    """Read version from VERSION file in sonorium core."""
    version_file = Path(__file__).parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


# Export __version__ for backward compatibility with BACKUP code
__version__ = get_version()
