# Sonorium Multi-Agent Development System

## Quick Start

```bash
# In Claude Code, from G:\Projects\SonoriumDev:
/project:start
```

## Commands

| Command | Purpose |
|---------|---------|
| `/project:start` | Initialize session, load all context |
| `/project:status` | Quick status check |
| `/project:feature <desc>` | Plan and implement a feature |
| `/project:fix <desc>` | Debug and fix an issue |
| `/project:review` | Pre-commit code review |

## Agents

| Agent | Domain | Files |
|-------|--------|-------|
| `sonorium-orchestrator` | Coordination | All |
| `sonorium-core` | Shared code | `app/core/sonorium/` |
| `sonorium-windows` | Desktop app | `app/windows/` |
| `sonorium-docker` | Container | `app/docker/` |
| `sonorium-reviewer` | Code review | All |

## Git Workflow

```
┌─────────────────────────────────────────────────────────┐
│                    DEVELOPMENT                          │
│                                                         │
│   origin (Gitea)  ←──── ALL WORK GOES HERE             │
│   192.168.1.222:3000                                   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                    OFF LIMITS                           │
│                                                         │
│   github ←──── NEVER PUSH HERE                         │
│   github.com/synssins/sonorium                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Commands:**
```bash
git push origin dev      # ✅ Correct
git push origin feature  # ✅ Correct
git push github anything # ❌ FORBIDDEN
```

## Protected Zone

```
sonorium_addon/    ← HA Addon is STABLE
                     DO NOT MODIFY without explicit permission
```

## Project Structure

```
G:\Projects\SonoriumDev\
├── app/
│   ├── core/sonorium/     # Shared platform-agnostic code
│   ├── windows/           # Windows launcher
│   └── docker/            # Docker container
├── sonorium_addon/        # PROTECTED - HA addon
├── docs/airplay/          # AirPlay protocol specs
├── CLAUDE.md              # Project rules
├── Summary.md             # Current state (UPDATE THIS)
├── TODO.md                # Pending work
└── Completed.md           # History
```

## Key Rules

1. ⛔ **Never push to github** - Origin (Gitea) only
2. ⛔ **Never modify sonorium_addon/** - It's stable
3. ⛔ **Never add AI attribution** - No Claude mentions
4. ✅ **Always use feature branches** - Not main directly
5. ✅ **Always update Summary.md** - Keep state current
6. ✅ **Always run /project:review** - Before committing

## Current Focus

**AirPlay Streaming** (from TODO.md Priority 1)
- Use pyatv's `stream_file()` with asyncio StreamReader
- Pure Python only (aiohttp, no curl)
- Test device: 192.168.1.74 (Office_C97a)

## VS Code Integration

Open the folder to watch changes in real-time:
```bash
code G:\Projects\SonoriumDev
```

## Useful Links

- **Gitea:** http://192.168.1.222:3000/Synthesis/sonorium
- **pyatv docs:** https://pyatv.dev/
- **AirPlay docs:** `docs/airplay/` (pull from Gitea if missing)
