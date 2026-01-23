# Release Migration Guide: sonobleedingedge → sonorium

## Overview

This document outlines the safest approach to migrate the bleeding edge codebase to the production Sonorium repository and release it as a major version (v2.0.0).

---

## Pre-Migration Checklist

### 1. Verify Bleeding Edge Stability
- [ ] All features working in HA addon
- [ ] All features working in Windows standalone
- [ ] All features working in Docker standalone
- [ ] No critical bugs in issue tracker
- [ ] Mobile UI responsive and functional

### 2. Document Current State
- [ ] CHANGELOG_FULL.md is up to date
- [ ] Screenshots are current and named properly
- [ ] README reflects current features

---

## Migration Strategy

### Option A: Clean Merge (Recommended)

This preserves git history from both repositories.

```bash
# 1. Clone fresh copy of production repo
git clone https://github.com/synssins/sonorium.git sonorium-release
cd sonorium-release

# 2. Add bleeding edge as remote
git remote add bleeding https://github.com/synssins/sonobleedingedge.git
git fetch bleeding

# 3. Create release branch from bleeding edge
git checkout -b release/v2.0.0 bleeding/main

# 4. Update all references (see URL Updates section below)
# ... make changes ...

# 5. Merge into main with a merge commit
git checkout main
git merge release/v2.0.0 --no-ff -m "Release v2.0.0 - Major architecture overhaul"

# 6. Tag the release
git tag -a v2.0.0 -m "Version 2.0.0 - Plugin system, shared architecture, mobile UI"

# 7. Push
git push origin main --tags
```

### Option B: Squash Merge (Clean History)

If you want a clean single commit in production:

```bash
git checkout main
git merge release/v2.0.0 --squash
git commit -m "Release v2.0.0 - Complete rewrite with plugin architecture"
git tag -a v2.0.0 -m "Version 2.0.0"
git push origin main --tags
```

### Option C: Force Replace (Nuclear)

Only if you want to completely replace production with bleeding edge:

```bash
# WARNING: Destroys production history
git checkout main
git reset --hard bleeding/main
# Then update URLs and version
git push origin main --force-with-lease
```

**Recommendation**: Use Option A for traceability.

---

## Version Numbering

### Current State
- **sonobleedingedge**: v0.0.70
- **sonorium (production)**: v1.2.x

### Recommended Release Version: v2.0.0

Justification for major version bump:
1. **Complete architecture rewrite** - shared/ consolidation
2. **New plugin system** - TRUE plugins, not decorative
3. **Breaking changes** - Config format, API endpoints changed
4. **New features** - Plugin browser, hybrid discovery, mobile UI

### Version Update Locations

| File | Current | Change To |
|------|---------|-----------|
| `shared/version` | 0.0.70 | 2.0.0 |
| `sonorium_addon/config.yaml` | 0.0.70 | 2.0.0 |
| `app/windows/src/version_info.py` | 0.0.70 | 2.0.0 |
| `app/docker/Dockerfile` | (if versioned) | 2.0.0 |

### Script to Update All Versions

```bash
# Run from repo root after migration
VERSION="2.0.0"

echo "$VERSION" > shared/version
sed -i "s/version: \"[^\"]*\"/version: \"$VERSION\"/" sonorium_addon/config.yaml

# Then run sync
python scripts/sync_shared.py
```

---

## URL Updates Required

### Files to Search and Replace

```bash
# Find all references to sonobleedingedge
grep -r "sonobleedingedge" --include="*.py" --include="*.md" --include="*.yaml" --include="*.json" --include="*.html" --include="*.js"
```

### Specific Updates

| File | Find | Replace |
|------|------|---------|
| `repository.yaml` | `synssins/sonobleedingedge` | `synssins/sonorium` |
| `sonorium_addon/config.yaml` | `synssins/sonobleedingedge` | `synssins/sonorium` |
| `README.md` | All bleeding edge URLs | Production URLs |
| `CLAUDE.md` | Remote references | Update or remove |
| `.claude/rules/*.md` | Remote references | Update |
| `shared/web/templates/index.html` | Any hardcoded URLs | Update |
| `app/windows/src/*.py` | Update URLs | Production |

### HA One-Click Install Badge

```markdown
# OLD (bleeding edge)
[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsynssins%2Fsonobleedingedge)

# NEW (production)
[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsynssins%2Fsonorium)
```

### Plugin Catalog URL

If plugins reference a catalog URL, update:
```
https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/catalog.json
→
https://raw.githubusercontent.com/synssins/sonorium/main/plugins/catalog.json
```

---

## Git Remote Cleanup

### After Migration - Update Remotes

```bash
# In your local working copy
git remote remove sonobleedingedge  # Remove bleeding edge remote
git remote set-url origin https://github.com/synssins/sonorium.git

# Verify
git remote -v
# Should show only:
# origin  https://github.com/synssins/sonorium.git (fetch)
# origin  https://github.com/synssins/sonorium.git (push)
```

### Update CLAUDE.md

Remove or update the "FORBIDDEN" remote references since after migration, sonorium is the correct target.

---

## Post-Migration Testing

### 1. HA Addon
```bash
# Users with old repo should see update available
# New users can one-click install from production URL
```

### 2. Windows Standalone
- Build new EXE with production URLs
- Test auto-update points to production releases

### 3. Docker
- Build and push to Docker Hub (if applicable)
- Test docker-compose with production image

### 4. Plugin Catalog
- Verify plugin downloads work from new URLs
- Test one-click plugin install

---

## Rollback Plan

If issues discovered after release:

```bash
# Create hotfix branch
git checkout -b hotfix/v2.0.1
# Fix issues
git commit -m "Fix critical bug"
# Merge and tag
git checkout main
git merge hotfix/v2.0.1
git tag -a v2.0.1 -m "Hotfix for v2.0.0"
git push origin main --tags
```

For catastrophic issues, revert to previous release:
```bash
git revert HEAD
git tag -a v2.0.2 -m "Revert to stable"
git push origin main --tags
```

---

## Release Announcement Template

```markdown
# Sonorium v2.0.0 Released! 🎉

Major release with complete architecture overhaul.

## What's New
- **Plugin System** - Install speaker protocols as plugins
- **Mobile UI** - Fully responsive on phones/tablets
- **Unified Codebase** - HA addon and Standalone share identical core
- **Speaker Discovery** - Hybrid HA + direct network discovery
- **Theme Dropdown** - Improved theme selection UX
- **Volume Control** - Per-speaker volume in channels

## Breaking Changes
- Config format updated (migration automatic)
- API endpoint changes (clients may need updates)

## Upgrade Instructions
### HA Addon
Update through Supervisor - existing config preserved.

### Windows Standalone
Download new installer from Releases page.

### Docker
Pull new image: `docker pull synssins/sonorium:2.0.0`

## Full Changelog
See CHANGELOG_FULL.md for complete list of changes.
```

---

## Timeline Suggestion

| Day | Task |
|-----|------|
| 1 | Final testing on all platforms |
| 2 | Create migration branch, update URLs/versions |
| 3 | Test migration branch thoroughly |
| 4 | Merge to production, create release |
| 5 | Monitor for issues, respond to feedback |

---

## Questions to Decide

1. **Keep sonobleedingedge active?** - Archive it or continue for future bleeding edge?
2. **Docker Hub?** - Push official images or GitHub Container Registry?
3. **sonorium.app website** - Update simultaneously or after?
4. **Existing HA users** - How to notify of repo change?

---

## Summary

1. Use Option A (clean merge) for best traceability
2. Version as 2.0.0 (major architectural changes)
3. Update ALL URLs from sonobleedingedge → sonorium
4. Test thoroughly before pushing
5. Tag release and announce
