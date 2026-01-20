# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Sonorium Launcher.

This builds the native Windows launcher (Sonorium.exe) that:
- Provides a native PyQt6 UI
- Manages the Python core as a subprocess
- Handles system tray integration
- Manages settings and updates

Build command (from repo root):
    cd app/windows/src && pyinstaller --distpath .. --workpath ../build Sonorium.spec

Output: app/windows/Sonorium.exe
"""

import os
import subprocess
import sys
from pathlib import Path

# Get the spec file directory (app/windows/src/)
spec_dir = Path(SPECPATH)
windows_dir = spec_dir.parent  # app/windows/
app_dir = windows_dir.parent  # app/
project_dir = app_dir.parent  # sonobleedingedge/ or repo root

# Generate version info file before build
version_info_script = spec_dir / 'version_info.py'
version_file = spec_dir / 'version.txt'

if version_info_script.exists():
    print(f"Generating version info from {version_info_script}...")
    try:
        result = subprocess.run(
            [sys.executable, str(version_info_script)],
            cwd=str(spec_dir),
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"Warning: version_info.py failed: {result.stderr}")
    except Exception as e:
        print(f"Warning: Could not generate version info: {e}")

if not version_file.exists():
    print("Warning: No version file found, building without version info")
    version_file = None
else:
    print(f"Using version file: {version_file}")

# Icon paths - in app/core/
icon_png = app_dir / 'core' / 'icon.png'
icon_ico = app_dir / 'core' / 'icon.ico'
logo_path = app_dir / 'core' / 'logo.png'

# Collect data files - only include if they exist
datas_list = []
if icon_png.exists():
    datas_list.append((str(icon_png), '.'))
if logo_path.exists():
    datas_list.append((str(logo_path), '.'))

# EXE icon - use .ico if exists, otherwise None
exe_icon = str(icon_ico) if icon_ico.exists() else None

# Analysis - gather all dependencies
a = Analysis(
    [str(spec_dir / 'launcher.py')],
    pathex=[str(spec_dir)],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate binaries/datas
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Build the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Sonorium',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress executable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - this is a GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,  # Application icon (.ico format for Windows)
    version=str(version_file) if version_file and os.name == 'nt' else None,
)
