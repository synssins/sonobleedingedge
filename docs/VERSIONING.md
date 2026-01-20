# VERSIONING SYSTEM - SINGLE SOURCE OF TRUTH

## Overview

**Git tags are the SINGLE source of truth for versioning.**

When you push a tag like `v0.0.8`, GitHub Actions automatically:
1. Extracts the version from the tag
2. Updates ALL version files
3. Builds the release
4. Creates the GitHub release

You NEVER manually edit version files. The automation handles everything.

---

## How It Works

```
git tag v0.0.8                    # Create tag (SOURCE OF TRUTH)
git push sonobleedingedge v0.0.8  # Push tag
                                   |
                                   v
                    GitHub Actions triggered
                                   |
        +----------+---------------+---------------+
        |          |               |               |
        v          v               v               v
    VERSION     config.yaml    version.json    launcher.py
    (text)      (HA addon)     (standalone)    (APP_VERSION)
```

---

## Workflow: Creating a Release

### Step 1: Ensure code is ready
```bash
# Make sure all changes are committed and pushed
git status
git push sonobleedingedge main
```

### Step 2: Create an annotated tag with changelog
```bash
git tag -a v0.0.8 -m "Release 0.0.8

- Added new feature X
- Fixed bug Y
- Improved performance Z"
```

### Step 3: Push the tag
```bash
git push sonobleedingedge v0.0.8
```

### Step 4: GitHub Actions does the rest
- Extracts version `0.0.8` from tag
- Updates all version files in the build
- Builds standalone app
- Creates GitHub release with changelog

---

## Version Files (Auto-Updated by CI)

| File | Purpose | Updated By |
|------|---------|------------|
| `VERSION` (root) | Single source for local dev | `scripts/bump_version.py` |
| `app/core/sonorium/version` | Standalone runtime | CI from tag |
| `sonorium_addon/sonorium/version` | HA addon runtime | CI from tag |
| `sonorium_addon/config.yaml` | HA addon manifest | CI from tag |
| `app/core/version.json` | Standalone metadata | CI from tag |
| `app/windows/src/launcher.py` | Windows APP_VERSION | CI from tag |

---

## Local Development: bump_version.py

For local development, use the bump script:

```bash
# Bump patch version (0.0.7 -> 0.0.8)
python scripts/bump_version.py patch

# Bump minor version (0.0.7 -> 0.1.0)
python scripts/bump_version.py minor

# Bump major version (0.0.7 -> 1.0.0)
python scripts/bump_version.py major

# Set specific version
python scripts/bump_version.py 1.2.3

# Dry run (preview changes)
python scripts/bump_version.py patch --dry-run
```

This updates ALL local version files but does NOT create tags or push.

---

## CI Workflow: update-versions.yml

The GitHub Action that syncs versions on tag push:

```yaml
name: Update Versions and Build

on:
  push:
    tags:
      - 'v*'

jobs:
  update-versions:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Extract version from tag
        id: version
        run: |
          VERSION=${GITHUB_REF#refs/tags/v}
          echo "VERSION=$VERSION" >> $GITHUB_OUTPUT
          
      - name: Update all version files
        run: python scripts/bump_version.py ${{ steps.version.outputs.VERSION }}
        
      - name: Commit version updates
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git commit -m "chore: bump version to ${{ steps.version.outputs.VERSION }}" || true
          git push origin HEAD:main
```

---

## Version Format

```
MAJOR.MINOR.PATCH[-PRERELEASE]

Examples:
  0.0.7        - Development
  0.1.0        - First feature-complete
  1.0.0        - First stable release
  1.0.1-alpha  - Alpha pre-release
  1.0.1-beta   - Beta pre-release
```

---

## Rules for Claude Code

### NEVER do this:
- Manually edit version numbers in any file
- Create version files with different numbers
- Skip the bump script when changing versions

### ALWAYS do this:
- Use `python scripts/bump_version.py <version>` to change versions
- Let CI handle version updates on release
- Keep all version files in sync

### When asked to "bump the version":
```bash
python scripts/bump_version.py patch    # or minor/major
git add -A
git commit -m "chore: bump version to X.Y.Z"
git push sonobleedingedge main
```

### When asked to "create a release":
```bash
# First ensure version is bumped locally
python scripts/bump_version.py 0.0.8

# Commit the version bump
git add -A
git commit -m "chore: bump version to 0.0.8"
git push sonobleedingedge main

# Then create and push the tag
git tag -a v0.0.8 -m "Release notes here"
git push sonobleedingedge v0.0.8
```

---

## Verification

To check all versions are in sync:
```bash
python scripts/bump_version.py --check
```

This will report any mismatched version files.
