# Sonorium + SuperClaude Quick Reference

## Available /sc Commands

| Command | Use For |
|---------|---------|
| `/sc:spawn` | Parallel multi-agent analysis |
| `/sc:research` | Web search + library docs |
| `/sc:analyze` | Code analysis |
| `/sc:brainstorm` | Ideation |
| `/sc:implement` | Write code |
| `/sc:test` | Testing |
| `/sc:troubleshoot` | Debugging |
| `/sc:design` | Architecture |
| `/sc:reflect` | Code review |
| `/sc:git` | Git operations |
| `/sc` | List all commands |

## Custom Agents

| Agent | Focus | Key Commands |
|-------|-------|--------------|
| `@sonorium-orchestrator` | Coordinates everything | `/sc:spawn`, `/sc:research` |
| `@sonorium-core` | Shared Python code | `/sc:implement`, `/sc:analyze` |
| `@sonorium-streaming` | Network protocols | `/sc:research`, `/sc:troubleshoot` |
| `@sonorium-reviewer` | Pre-commit review | `/sc:reflect`, `/sc:git` |

## Project Structure

```
app/core/sonorium/     ← Shared (all platforms)
app/windows/           ← Windows launcher
app/docker/            ← Docker container  
sonorium_addon/        ← HA addon (DON'T TOUCH)
```

## Git Remotes

```
✅ origin  → http://192.168.1.222:3000  (Gitea - USE THIS)
❌ github  → github.com                  (OFF LIMITS)
```

## Test Speakers

- Office_C97a: 192.168.1.74 (primary)
- Arylic-livingroom: 192.168.1.254
- Marantz SR-5011: 192.168.1.13

🐕 Pleasant sounds, moderate volume (dog in house)

## Example Workflows

**Complex question:**
```
/sc:spawn Analyze the AirPlay implementation from 4 perspectives:
research, current code, compatibility, and gap analysis
```

**Add a feature:**
```
/sc:design WebSocket support for real-time UI updates
/sc:implement [after design is approved]
/sc:test WebSocket functionality
/sc:reflect before committing
```

**Debug an issue:**
```
/sc:troubleshoot AirPlay streaming drops after 30 seconds
```

**Before commit:**
```
/sc:reflect
/sc:git push origin dev
```
