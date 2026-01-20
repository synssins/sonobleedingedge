# Windows EXE Build Workflow Documentation

This document describes the GitHub Actions workflow used to build the Sonorium Windows standalone application. Use this as a reference to recreate the build workflow in another repository.

---

## Overview

The workflow builds a portable Windows application consisting of:
1. **Sonorium.exe** - Native PyQt6 launcher (~37 MB)
2. **updater.exe** - Small update helper executable
3. **core.zip** - Embedded Python 3.11 + all dependencies + source code (~100+ MB)

The launcher downloads `core.zip` on first run, or users can manually extract it alongside the exe.

---

## Workflow Trigger

```yaml
on:
  push:
    tags:
      - 'v*'  # Triggers on version tags like v0.1.0-alpha, v1.0.0, etc.
```

- **Alpha/beta tags** (containing "alpha" or "beta"): Build from `dev` branch, marked as prerelease
- **Stable tags**: Build from `main` branch

---

## Prerequisites

### Repository Structure Required

```
your-repo/
├── .github/
│   └── workflows/
│       └── release.yml          # The workflow file
├── app/
│   ├── core/
│   │   ├── icon.png             # App icon (PNG format, will be converted to ICO)
│   │   ├── logo.png             # Logo for splash screen (optional)
│   │   ├── requirements.txt     # Python dependencies for core
│   │   ├── sonorium/            # Your Python application source code
│   │   └── web/                 # Web UI static files
│   ├── themes/                  # Default themes/data (optional)
│   └── windows/
│       └── src/
│           ├── launcher.py      # PyQt6 launcher application
│           ├── updater.py       # Update helper script
│           ├── version_info.py  # Generates Windows version info
│           ├── Sonorium.spec    # PyInstaller spec for main app
│           └── Updater.spec     # PyInstaller spec for updater
```

### GitHub Repository Settings

1. **Permissions**: Workflow needs `contents: write` permission for creating releases
2. **Secrets**: Uses built-in `GITHUB_TOKEN` (no custom secrets required)

---

## Build Dependencies

### Build-time Dependencies (installed by workflow)

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.11 | Build environment |
| PyQt6 | latest | GUI framework for launcher |
| pyinstaller | latest | Creates standalone executables |
| pillow | latest | Converts PNG icon to ICO format |

### Runtime Dependencies (in core.zip)

These are installed into the embedded Python and defined in `app/core/requirements.txt`:

```
# Core web framework
fastapi>=0.100.0
uvicorn>=0.23.0
python-multipart>=0.0.6

# Audio processing
av>=10.0.0
numpy>=1.24.0
sounddevice>=0.4.6

# HTTP client
httpx>=0.24.0
aiohttp>=3.9.0

# Data validation
pydantic>=2.0.0

# Async support
aiofiles>=23.0.0

# Network speaker discovery
async-upnp-client>=0.38.0
zeroconf>=0.131.0

# Protocol support
pyatv>=0.14.0      # AirPlay
soco>=0.30.0       # Sonos
```

---

## Workflow Steps Explained

### 1. Determine Source Branch

```yaml
- name: Determine source branch
  id: branch
  run: |
    if [[ "${{ github.ref }}" == *"alpha"* ]] || [[ "${{ github.ref }}" == *"beta"* ]]; then
      echo "SOURCE_BRANCH=dev" >> $GITHUB_OUTPUT
    else
      echo "SOURCE_BRANCH=main" >> $GITHUB_OUTPUT
    fi
  shell: bash
```

Routes alpha/beta builds to `dev` branch, stable builds to `main`.

### 2. Checkout and Setup

```yaml
- name: Checkout repository
  uses: actions/checkout@v4
  with:
    ref: ${{ steps.branch.outputs.SOURCE_BRANCH }}
    fetch-depth: 0  # Full history for tags

- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
```

### 3. Install Build Dependencies

```yaml
- name: Install build dependencies
  run: |
    python -m pip install --upgrade pip
    pip install PyQt6 pyinstaller pillow
```

### 4. Create Icon

```yaml
- name: Create icon.ico from PNG
  run: |
    python -c "from PIL import Image; img = Image.open('app/core/icon.png'); img.save('app/core/icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])"
```

Converts PNG to multi-resolution ICO for Windows executable.

### 5. Build Executables with PyInstaller

```yaml
- name: Build Sonorium.exe
  run: |
    cd app/windows/src
    pyinstaller --distpath .. --workpath ../build --clean Sonorium.spec

- name: Build updater.exe
  run: |
    cd app/windows/src
    pyinstaller --distpath .. --workpath ../build --clean Updater.spec
```

### 6. Download and Configure Embedded Python

```powershell
# Download Python 3.11 embeddable package (64-bit)
$pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
Invoke-WebRequest -Uri $pythonUrl -OutFile "python_embed.zip"
Expand-Archive -Path "python_embed.zip" -DestinationPath "python_embed" -Force

# Enable pip by modifying python311._pth
$pthFile = "python_embed/python311._pth"
$pthContent = Get-Content $pthFile
$newContent = $pthContent -replace '#import site', 'import site'
$newContent += "`nLib\site-packages"
Set-Content -Path $pthFile -Value $newContent

# Install pip
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "python_embed/get-pip.py"
& "python_embed/python.exe" "python_embed/get-pip.py" --no-warn-script-location
```

Key insight: The embeddable Python has pip disabled by default. Must modify the `._pth` file to enable `import site` and add `Lib\site-packages`.

### 7. Install Runtime Dependencies

```powershell
& "python_embed/python.exe" -m pip install --no-warn-script-location -r app/core/requirements.txt
```

### 8. Create core.zip

```powershell
Rename-Item -Path "python_embed" -NewName "python"
Compress-Archive -Path "app/core", "app/themes", "python" -DestinationPath core.zip -Force
```

The zip structure expected by the launcher:
```
core.zip
├── core/           # Application source code (renamed from app/core)
│   ├── sonorium/   # Python package
│   ├── web/        # Static web files
│   └── ...
├── themes/         # Default themes (renamed from app/themes)
└── python/         # Embedded Python with all dependencies
    ├── python.exe
    ├── python311.dll
    ├── Lib/
    │   └── site-packages/  # All pip-installed packages
    └── ...
```

### 9. Create GitHub Release

```yaml
- name: Create Release
  uses: softprops/action-gh-release@v1
  with:
    name: Sonorium ${{ steps.get_version.outputs.VERSION }}
    draft: false
    prerelease: ${{ contains(github.ref, 'alpha') || contains(github.ref, 'beta') }}
    files: |
      app/windows/Sonorium.exe
      app/windows/updater.exe
      core.zip
```

---

## PyInstaller Spec Files

### Sonorium.spec (Main Launcher)

Key configuration:
- **Entry point**: `launcher.py`
- **Hidden imports**: PyQt6 modules
- **Excluded modules**: tkinter, matplotlib, numpy, etc. (reduces size)
- **UPX compression**: Enabled
- **Console**: Disabled (GUI app)
- **Icon**: Uses generated `.ico` file
- **Version info**: Generated from `version_info.py`

```python
exe = EXE(
    ...
    name='Sonorium',
    console=False,      # No console window
    upx=True,           # Compress executable
    icon=exe_icon,      # Windows icon
    version=version_file,  # Windows version info
)
```

### Updater.spec (Update Helper)

Key configuration:
- **Entry point**: `updater.py`
- **Minimal dependencies**: No PyQt6
- **Console**: Enabled (shows update progress)
- **UPX compression**: Enabled

```python
exe = EXE(
    ...
    name='updater',
    console=True,       # Show console for progress
    upx=True,
)
```

---

## Complete Workflow File

Save as `.github/workflows/release.yml`:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest

    steps:
      - name: Determine source branch
        id: branch
        run: |
          if [[ "${{ github.ref }}" == *"alpha"* ]] || [[ "${{ github.ref }}" == *"beta"* ]]; then
            echo "SOURCE_BRANCH=dev" >> $GITHUB_OUTPUT
            echo "Building alpha/beta release from dev branch"
          else
            echo "SOURCE_BRANCH=main" >> $GITHUB_OUTPUT
            echo "Building stable release from main branch"
          fi
        shell: bash

      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: ${{ steps.branch.outputs.SOURCE_BRANCH }}
          fetch-depth: 0

      - name: Fetch tag annotations
        run: git fetch --tags --force
        shell: bash

      - name: Verify branch
        run: |
          echo "Building from branch: ${{ steps.branch.outputs.SOURCE_BRANCH }}"
          echo "Current HEAD: $(git rev-parse HEAD)"
          echo "Tag: ${{ github.ref }}"
        shell: bash

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install PyQt6 pyinstaller pillow

      - name: Create icon.ico from PNG
        run: |
          python -c "from PIL import Image; img = Image.open('app/core/icon.png'); img.save('app/core/icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])"

      - name: Build Sonorium.exe
        run: |
          cd app/windows/src
          pyinstaller --distpath .. --workpath ../build --clean Sonorium.spec

      - name: Build updater.exe
        run: |
          cd app/windows/src
          pyinstaller --distpath .. --workpath ../build --clean Updater.spec

      - name: Download Python embeddable
        run: |
          $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
          $pipUrl = "https://bootstrap.pypa.io/get-pip.py"

          New-Item -ItemType Directory -Force -Path "python_embed"

          Write-Host "Downloading Python embeddable..."
          Invoke-WebRequest -Uri $pythonUrl -OutFile "python_embed.zip"
          Expand-Archive -Path "python_embed.zip" -DestinationPath "python_embed" -Force
          Remove-Item "python_embed.zip"

          Write-Host "Enabling pip in embedded Python..."
          $pthFile = "python_embed/python311._pth"
          $pthContent = Get-Content $pthFile
          $newContent = $pthContent -replace '#import site', 'import site'
          $newContent += "`nLib\site-packages"
          Set-Content -Path $pthFile -Value $newContent

          Write-Host "Installing pip..."
          Invoke-WebRequest -Uri $pipUrl -OutFile "python_embed/get-pip.py"
          & "python_embed/python.exe" "python_embed/get-pip.py" --no-warn-script-location
          Remove-Item "python_embed/get-pip.py"
        shell: pwsh

      - name: Install core dependencies into embedded Python
        run: |
          Write-Host "Installing core dependencies..."
          & "python_embed/python.exe" -m pip install --no-warn-script-location -r app/core/requirements.txt

          Write-Host "Installed packages:"
          & "python_embed/python.exe" -m pip list
        shell: pwsh

      - name: Create core.zip with embedded Python
        run: |
          Rename-Item -Path "python_embed" -NewName "python"
          Compress-Archive -Path "app/core", "app/themes", "python" -DestinationPath core.zip -Force

          Write-Host "core.zip created with embedded Python"
          $zipSize = (Get-Item "core.zip").Length / 1MB
          Write-Host "Size: $([math]::Round($zipSize, 2)) MB"
        shell: pwsh

      - name: Get version from tag
        id: get_version
        run: echo "VERSION=${GITHUB_REF#refs/tags/}" >> $GITHUB_OUTPUT
        shell: bash

      - name: Get tag message (changelog)
        id: get_changelog
        run: |
          TAG_MESSAGE=$(git tag -l --format='%(contents)' ${GITHUB_REF#refs/tags/})
          echo "CHANGELOG<<EOF" >> $GITHUB_OUTPUT
          echo "$TAG_MESSAGE" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
        shell: bash

      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          name: YourApp ${{ steps.get_version.outputs.VERSION }}
          draft: false
          prerelease: ${{ contains(github.ref, 'alpha') || contains(github.ref, 'beta') }}
          files: |
            app/windows/Sonorium.exe
            app/windows/updater.exe
            core.zip
          body: |
            ${{ steps.get_changelog.outputs.CHANGELOG }}

            ---

            ### Downloads
            - **Sonorium.exe** - Standalone Windows launcher (portable)
            - **core.zip** - Core files with embedded Python

            ### First-time setup
            1. Download `Sonorium.exe` to any folder
            2. Run it - the app will automatically download required files
            3. No Python installation required!

            ### Manual installation
            1. Download both files
            2. Extract `core.zip` to the same folder as `Sonorium.exe`
            3. Run `Sonorium.exe`
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Customization Notes

When adapting for another project:

1. **Change file paths** in the workflow to match your project structure
2. **Update `requirements.txt`** with your application's dependencies
3. **Modify the spec files** to point to your entry point scripts
4. **Update the release body** with your application's instructions
5. **Change the app name** in PyInstaller specs and release step

---

## Triggering a Build

To trigger the workflow:

```bash
# For alpha/beta release (builds from dev branch)
git tag -a v1.0.0-alpha -m "Alpha release notes here"
git push origin v1.0.0-alpha

# For stable release (builds from main branch)
git tag -a v1.0.0 -m "Release notes here"
git push origin v1.0.0
```

The tag message becomes the release changelog.

---

## Troubleshooting

### Common Issues

1. **Icon not found**: Ensure `app/core/icon.png` exists and is a valid PNG
2. **PyInstaller fails**: Check that all hidden imports are listed in the spec file
3. **pip install fails in embedded Python**: Verify the `._pth` file modification succeeded
4. **Release not created**: Check `permissions: contents: write` is set

### Debugging

Add this step to inspect the build environment:

```yaml
- name: Debug environment
  run: |
    echo "Python version:"
    python --version
    echo "Working directory:"
    pwd
    echo "Directory contents:"
    ls -la
  shell: bash
```

---

## References

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [Python Embeddable Package](https://docs.python.org/3/using/windows.html#the-embeddable-package)
- [GitHub Actions: softprops/action-gh-release](https://github.com/softprops/action-gh-release)
- [GitHub Actions: Workflow Syntax](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
