# Deployment Target Isolation Rules - MANDATORY

## CRITICAL: These Are SEPARATE Codebases

The Sonorium project has THREE deployment targets with **SEPARATE, INDEPENDENT codebases**.
They are NOT copies of each other. They share similar structure but have different implementations.

**NEVER sync files between deployment targets unless explicitly instructed.**

---

## Deployment Targets

### 1. Home Assistant Addon
**Root:** `sonorium_addon/`
**When to modify:** User says "HA addon", "Home Assistant", "addon"

### 2. Standalone App (Windows/Docker)
**Root:** `app/core/` (shared), `app/windows/` (Windows-specific), `app/docker/` (Docker-specific)
**When to modify:** User says "standalone", "Windows app", "Docker container"

---

## File Ownership Matrix

### HOME ASSISTANT ADDON ONLY (`sonorium_addon/`)
These files are EXCLUSIVELY for the HA addon. NEVER touch when working on standalone:

```
sonorium_addon/
├── config.yaml                    # HA addon config
├── Dockerfile                     # HA addon container
├── run.sh                         # HA addon entrypoint
├── sonorium/
│   ├── ha/                        # HA-SPECIFIC - NO EQUIVALENT IN STANDALONE
│   │   ├── cast_player.py         # Cast via HA registry
│   │   ├── media_controller.py    # HA media control
│   │   ├── mqtt_entities.py       # MQTT device exposure
│   │   ├── registry.py            # HA device/area registry
│   │   └── sonos_player.py        # Sonos via HA + SoCo
│   ├── web/
│   │   ├── api_v2.py              # HA-SPECIFIC API (different from standalone!)
│   │   ├── app.py                 # HA-SPECIFIC FastAPI app
│   │   └── static/
│   │       ├── css/styles.css     # HA-SPECIFIC CSS
│   │       └── js/
│   │           ├── api.js         # HA-SPECIFIC API client
│   │           └── app.js         # HA-SPECIFIC frontend (DIFFERENT FUNCTIONS!)
│   ├── core/
│   │   ├── session_manager.py     # HA-SPECIFIC session management
│   │   ├── group_manager.py       # HA-SPECIFIC groups
│   │   └── state.py               # HA-SPECIFIC state
│   └── settings.py                # HA-SPECIFIC settings
```

### STANDALONE APP ONLY (`app/core/`, `app/windows/`, `app/docker/`)
These files are EXCLUSIVELY for standalone. NEVER touch when working on HA addon:

```
app/core/
├── sonorium/
│   ├── network_speakers.py        # STANDALONE - Direct network discovery
│   ├── streaming.py               # STANDALONE - Direct streaming (pyatv, etc.)
│   ├── local_stream_player.py     # STANDALONE - Local audio output
│   ├── pyatv_patches.py           # STANDALONE - pyatv compatibility
│   ├── update.py                  # STANDALONE - Auto-update system
│   ├── audio_output.py            # STANDALONE - Audio device management
│   ├── config.py                  # STANDALONE - Config management
│   └── main.py                    # STANDALONE - Main entry point
├── web/
│   └── static/
│       ├── css/styles.css         # STANDALONE CSS (similar but different!)
│       └── js/
│           ├── api.js             # STANDALONE API client
│           └── app.js             # STANDALONE frontend
│               # Has: loadLocalAudioDevices(), loadNetworkSpeakers()
│               # DOES NOT have: renderSettingsSpeakerTree() for HA hierarchy

app/windows/
├── src/
│   ├── launcher.py                # Windows PyQt6 launcher
│   ├── updater.py                 # Windows auto-update
│   └── version_info.py            # Windows version metadata

app/docker/
├── Dockerfile                     # Docker standalone container
├── docker-compose.yml             # Docker compose config
└── entrypoint.sh                  # Docker entry point
```

---

## Key Differences Between Codebases

### Speaker Discovery
| HA Addon | Standalone |
|----------|------------|
| `ha/registry.py` - Uses HA device registry | `network_speakers.py` - Direct mDNS/SSDP |
| Speakers come from HA entities | Speakers discovered on network |

### Media Control
| HA Addon | Standalone |
|----------|------------|
| `ha/media_controller.py` - Routes to SonosPlayer/CastPlayer | `streaming.py` - Direct pyatv/pychromecast |
| Uses HA API for unknown devices | No HA dependency |

### Frontend Functions
| HA Addon `app.js` | Standalone `app.js` |
|-------------------|---------------------|
| `renderSettingsSpeakerTree()` | `loadLocalAudioDevices()` |
| `loadSpeakerHierarchy()` | `loadNetworkSpeakers()` |
| `refreshSpeakersFromHA()` | `refreshSpeakers()` |
| Uses `/speakers/hierarchy` API | Uses `/speakers/local` and `/speakers/network` APIs |

### API Endpoints
| HA Addon `api_v2.py` | Standalone `web_api.py` |
|----------------------|-------------------------|
| `/speakers/hierarchy` | `/speakers/local`, `/speakers/network` |
| `/settings/speakers/enable` | N/A |
| MQTT entity management | N/A |

---

## Enforcement Rules

### When User Says "Home Assistant Addon" or "HA Addon":
1. ONLY modify files under `sonorium_addon/`
2. NEVER touch `app/core/`, `app/windows/`, `app/docker/`
3. Use HA-specific functions in `app.js` (e.g., `renderSettingsSpeakerTree()`)
4. Reference `ha/` modules for speaker/media operations

### When User Says "Standalone" or "Windows App":
1. ONLY modify files under `app/core/` and `app/windows/`
2. NEVER touch `sonorium_addon/`
3. Use standalone functions in `app.js` (e.g., `loadNetworkSpeakers()`)
4. Reference `network_speakers.py` and `streaming.py` for speaker/media operations

### When User Says "Docker Container" (Standalone):
1. ONLY modify files under `app/core/` and `app/docker/`
2. NEVER touch `sonorium_addon/`
3. Same as standalone but with Docker-specific deployment files

---

## Common Mistakes to Avoid

### WRONG: Syncing app.js between codebases
The HA addon `app.js` has HA-specific functions that don't exist in standalone, and vice versa.
Copying one to the other WILL break functionality.

### WRONG: Assuming shared file names mean identical code
Files like `recording.py`, `theme.py`, `plugins/` exist in both codebases but have different implementations.

### WRONG: Using standalone discovery in HA addon
The HA addon gets speakers from Home Assistant's device registry, not from direct network discovery.

### WRONG: Using HA registry in standalone
The standalone app discovers speakers directly via mDNS/SSDP, not from Home Assistant.

---

## Pre-Commit Checklist

Before committing, verify:
- [ ] I identified which deployment target I'm modifying
- [ ] I ONLY touched files belonging to that target
- [ ] I did NOT sync/copy files between `sonorium_addon/` and `app/core/`
- [ ] Functions I called exist in the target's codebase (not the other one)
