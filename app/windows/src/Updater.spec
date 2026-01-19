# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Sonorium Updater.

This builds a small standalone updater executable that:
- Force-closes Sonorium.exe if running
- Replaces the executable with the update
- Launches the updated application

Build command:
    cd app/windows/src && pyinstaller --distpath .. --workpath ../build Updater.spec

Output: app/windows/updater.exe
"""

import os
from pathlib import Path

# Get the spec file directory
spec_dir = Path(SPECPATH)

# Analysis - minimal dependencies
a = Analysis(
    [str(spec_dir / 'updater.py')],
    pathex=[str(spec_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt6',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show console for update progress
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
