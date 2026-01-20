"""
Generate version info for PyInstaller Windows EXE.

This script creates a version.txt file that PyInstaller uses to embed
Windows version information into the EXE.

Usage: Run this script before building, or let the spec file call it.
"""

import re
import sys
from pathlib import Path


def get_version_from_launcher() -> str:
    """Extract APP_VERSION from launcher.py."""
    launcher_path = Path(__file__).parent / 'launcher.py'
    content = launcher_path.read_text(encoding='utf-8')
    match = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "0.0.0"


def parse_version(version_str: str) -> tuple:
    """Parse version string like '0.1.3-alpha' into (0, 1, 3, 0) for Windows."""
    # Remove 'v' prefix if present
    v = version_str.lstrip('v')

    # Split on '-' to separate prerelease tag
    parts = v.split('-')
    main_version = parts[0]

    # Parse main version numbers
    nums = main_version.split('.')
    while len(nums) < 4:
        nums.append('0')

    result = []
    for n in nums[:4]:
        try:
            result.append(int(n))
        except ValueError:
            result.append(0)

    return tuple(result)


def generate_version_info(version_str: str) -> str:
    """Generate Windows version info file content."""
    v = parse_version(version_str)
    version_tuple = f"({v[0]}, {v[1]}, {v[2]}, {v[3]})"
    version_string = version_str

    # Determine if prerelease
    # VS_FF_PRERELEASE = 0x2, VS_FF_DEBUG = 0x1
    is_prerelease = 'alpha' in version_str.lower() or 'beta' in version_str.lower()
    file_flags = "0x2" if is_prerelease else "0x0"

    return f'''# UTF-8
#
# Auto-generated version info for Sonorium
# Version: {version_str}
#

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags={file_flags},
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'Sonorium'),
            StringStruct(u'FileDescription', u'Sonorium - Ambient Soundscape Mixer'),
            StringStruct(u'FileVersion', u'{version_string}'),
            StringStruct(u'InternalName', u'Sonorium'),
            StringStruct(u'LegalCopyright', u'Copyright 2025 Sonorium'),
            StringStruct(u'OriginalFilename', u'Sonorium.exe'),
            StringStruct(u'ProductName', u'Sonorium'),
            StringStruct(u'ProductVersion', u'{version_string}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''


def main():
    """Generate version.txt file."""
    version = get_version_from_launcher()
    print(f"Detected version: {version}")

    content = generate_version_info(version)

    output_path = Path(__file__).parent / 'version.txt'
    output_path.write_text(content, encoding='utf-8')
    print(f"Generated: {output_path}")

    return version


if __name__ == '__main__':
    main()
