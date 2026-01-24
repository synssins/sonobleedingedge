# Sonorium Core Architecture

> **Living Document** - Updated as components are built
> **Last Updated:** 2026-01-24

---

## Overview

Sonorium is a multi-zone ambient soundscape mixer that streams layered audio themes to network speakers. It supports multiple speaker protocols (Sonos, Chromecast, AirPlay, DLNA, etc.) and can be controlled via Web UI, REST API, or MQTT.

---

## Design Principles

1. **API-First** - All functionality accessible via REST API
2. **Single State** - One source of truth for all application state
3. **MQTT as Core** - Full control via MQTT topics (not just HA integration)
4. **True Plugins** - Speakers/sources are plugins that can be added/removed
5. **Platform Parity** - Identical behavior across Standalone and HA Addon

---

## Core Components

### 1. State Management (`core/state.py`)

Single source of truth for all application state.

```python
class SonoriumState:
    # Settings
    enabled_speakers: list[str]      # Speaker IDs that are enabled
    master_volume: float             # 0.0 - 1.0

    # Sessions (active playback)
    sessions: dict[str, Session]     # channel_id -> Session

    # Discovered resources
    speakers: dict[str, Speaker]     # speaker_id -> Speaker
    themes: dict[str, Theme]         # theme_id -> Theme

    # Configuration
    settings: Settings               # User preferences
```

**Key Methods:**
- `load()` / `save()` - Persistence to JSON
- `enable_speaker(id)` / `disable_speaker(id)`
- `get_enabled_speakers()` - Returns only enabled speakers
- `on_change(callback)` - Subscribe to state changes

### 2. REST API (`web/api.py`)

FastAPI-based REST API. All state changes go through here.

#### Speaker Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/speakers` | List all discovered speakers |
| GET | `/api/speakers/enabled` | List enabled speakers only |
| POST | `/api/speakers/{id}/enable` | Enable a speaker |
| POST | `/api/speakers/{id}/disable` | Disable a speaker (stops streams) |
| POST | `/api/speakers/enable-all` | Enable all speakers |
| POST | `/api/speakers/disable-all` | Disable all speakers (stops all streams) |
| POST | `/api/speakers/{id}/volume` | Set speaker volume |
| POST | `/api/speakers/discover` | Trigger speaker discovery |

#### Session Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions` | List active sessions |
| POST | `/api/sessions` | Create new session (play theme to speakers) |
| DELETE | `/api/sessions/{id}` | Stop session |
| PATCH | `/api/sessions/{id}` | Update session (volume, speakers) |

#### Theme Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/themes` | List available themes |
| GET | `/api/themes/{id}` | Get theme details |
| POST | `/api/themes/{id}/play` | Play theme (creates session) |
| POST | `/api/themes/scan` | Rescan theme directories |

#### Channel Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/channels` | List channels |
| GET | `/api/channels/{id}` | Get channel details |
| PATCH | `/api/channels/{id}` | Update channel settings |
| POST | `/api/channels/{id}/speakers` | Assign speakers to channel |

#### System Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | System status (version, uptime, etc.) |
| GET | `/api/settings` | Get all settings |
| PATCH | `/api/settings` | Update settings |
| GET | `/api/logs` | Get recent logs |

### 3. MQTT Bridge (`core/mqtt.py`)

Full control via MQTT. Enables integration with Node-RED, Home Assistant, and other automation systems.

#### Control Topics (Subscribe)
```
sonorium/speakers/{id}/set          # {"enabled": true/false, "volume": 0.5}
sonorium/speakers/all/set           # {"enabled": true/false}
sonorium/sessions/set               # {"theme": "forest", "speakers": ["id1", "id2"]}
sonorium/sessions/{id}/set          # {"volume": 0.8, "action": "stop"}
sonorium/settings/set               # {"master_volume": 0.7}
sonorium/command                    # {"action": "discover_speakers"}
```

#### State Topics (Publish)
```
sonorium/status                     # {"state": "playing", "version": "0.1.0"}
sonorium/speakers/{id}/state        # {"enabled": true, "volume": 0.8, "playing": true}
sonorium/speakers/state             # Full speaker list JSON
sonorium/sessions/state             # Active sessions JSON
sonorium/themes/state               # Available themes JSON
```

#### Home Assistant Discovery
When HA integration is enabled, publishes MQTT discovery messages:
```
homeassistant/switch/sonorium_{speaker_id}/config
homeassistant/media_player/sonorium_{session_id}/config
homeassistant/sensor/sonorium_status/config
```

### 4. Plugin System (`plugins/`)

**IMPORTANT**: Sonorium has NO native speaker protocol support. ALL speaker protocols are provided via plugins. The core includes only basic mDNS/Zeroconf discovery to detect devices - protocol support requires installing the appropriate plugin.

#### Plugin Distribution Format

Plugins are distributed as **self-contained ZIP files** that include:
- Plugin code (Python)
- All required dependencies (bundled wheels)
- Manifest file (`manifest.json`)
- Optional: settings UI schema, icons, documentation

```
sonos-plugin-1.0.0.zip
├── manifest.json           # Plugin metadata
├── plugin.py               # Entry point (or __init__.py)
├── dependencies/           # Bundled Python wheels
│   └── soco-0.30.0-py3-none-any.whl
├── icon.png                # Optional plugin icon
└── README.md               # Optional documentation
```

#### Plugin Manifest (`manifest.json`)

```json
{
    "id": "sonos",
    "name": "Sonos Speaker",
    "version": "1.0.0",
    "description": "Stream audio to Sonos speakers on your network",
    "author": "Sonorium",
    "plugin_type": "speaker",
    "category": "speakers",
    "homepage": "https://github.com/synssins/sonobleedingedge",
    "entry_point": "plugin.py",
    "plugin_class": "SonosPlugin",
    "dependencies": {
        "soco": ">=0.30.0"
    },
    "capabilities": ["discovery", "playback", "volume", "groups"],
    "settings_schema": {
        "type": "object",
        "properties": {
            "discovery_timeout": {
                "type": "number",
                "title": "Discovery Timeout",
                "description": "Seconds to wait for discovery",
                "default": 5,
                "minimum": 1,
                "maximum": 30
            }
        }
    }
}
```

#### Plugin Categories

Plugins are organized into categories for the UI:

| Category | Description | Examples |
|----------|-------------|----------|
| `speakers` | Network speaker protocols | Sonos, Chromecast, AirPlay, DLNA |
| `importers` | Theme import sources | Ambient-Mixer, MyNoise |
| `utilities` | Helper tools | Theme merger, audio converter |

#### Plugin Interface

```python
class SpeakerPlugin(BasePlugin):
    """Base class for speaker protocol plugins."""

    @property
    def manifest(self) -> PluginManifest:
        """Return plugin manifest with metadata."""

    async def discover(self, timeout: float = 10.0) -> list[DiscoveredSpeaker]:
        """Discover speakers using this protocol."""

    async def play_url(self, speaker_id: str, url: str, **kwargs) -> bool:
        """Stream URL to speaker."""

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback on speaker."""

    async def set_volume(self, speaker_id: str, volume: float) -> bool:
        """Set speaker volume (0.0 - 1.0)."""

    async def stop_all(self) -> int:
        """Stop all speakers managed by this plugin."""
```

#### Device Detection Without Plugin

When Sonorium's core mDNS/Zeroconf discovery detects a device without a matching plugin:

1. Device appears in UI with "Plugin Required" indicator
2. User sees which plugin is needed (e.g., "Install Sonos plugin")
3. Device cannot be used until plugin is installed
4. Plugin installation enables full functionality

#### Available Speaker Plugins

| Plugin | Protocol | Dependencies |
|--------|----------|--------------|
| `sonos` | Sonos/SoCo | `soco>=0.30.0` |
| `chromecast` | Google Cast | `pychromecast>=13.0.0` |
| `airplay` | AirPlay 1/2 | `pyatv>=0.14.0` |
| `dlna` | DLNA/UPnP | `async_upnp_client>=0.33.0` |
| `linkplay` | Linkplay | HTTP API (no external deps) |
| `heos` | Denon HEOS | `pyheos>=0.7.0` |

### 5. Streaming Engine (`core/streaming.py`)

Manages audio streaming to speakers.

```python
class StreamingManager:
    """Manages active streams to speakers."""

    async def start_stream(self, speaker_id: str, audio_url: str) -> StreamSession
    async def stop_stream(self, speaker_id: str) -> bool
    async def stop_all() -> None

    def get_active_streams() -> dict[str, StreamSession]
```

### 6. Theme Engine (`core/themes.py`)

Manages themes and audio mixing.

#### Theme Distribution Format

Themes are distributed as **self-contained ZIP files** that include:
- Audio files (MP3, WAV, OGG, FLAC)
- Metadata file (`metadata.json`)
- Optional: preview image, documentation

```
rainy-day-theme.zip
├── metadata.json           # Theme metadata and track settings
├── Light_rain.mp3          # Audio file
├── Thunder_distant.mp3     # Audio file
├── Wind_howling.mp3        # Audio file
├── preview.png             # Optional preview image
└── README.md               # Optional documentation
```

#### Theme Metadata (`metadata.json`)

```json
{
    "id": "b851228a-94ca-47b7-aa55-576ceb791adb",
    "name": "A Rainy Day",
    "description": "Gentle rain with occasional thunder",
    "icon": "⛈️",
    "is_favorite": false,
    "categories": ["Weather", "Relaxation"],
    "short_file_threshold": 15.0,
    "tracks": {
        "Light_rain.mp3": {
            "presence": 1.0,
            "muted": false,
            "volume": 0.32,
            "playback_mode": "presence",
            "seamless_loop": false,
            "exclusive": false
        },
        "Thunder_distant.mp3": {
            "presence": 0.2,
            "muted": false,
            "volume": 1.0,
            "playback_mode": "sparse",
            "seamless_loop": false,
            "exclusive": false
        }
    },
    "presets": {
        "mild": {
            "name": "Mild Storm",
            "is_default": true,
            "tracks": {
                "Light_rain.mp3": {"volume": 0.32, "presence": 1.0},
                "Thunder_distant.mp3": {"volume": 0.5, "presence": 0.1}
            }
        },
        "intense": {
            "name": "Intense Storm",
            "is_default": false,
            "tracks": {
                "Light_rain.mp3": {"volume": 0.8, "presence": 1.0},
                "Thunder_distant.mp3": {"volume": 1.0, "presence": 0.5}
            }
        }
    },
    "attribution": {
        "source": "Ambient-Mixer.com",
        "source_url": "https://weather.ambient-mixer.com/light-thunderstorm",
        "license": "Creative Commons Sampling Plus 1.0",
        "license_url": "https://creativecommons.org/licenses/sampling+/1.0/",
        "imported_date": "2025-12-15T20:22:36.626402Z",
        "imported_by": "ambient_mixer"
    }
}
```

#### Track Playback Modes

| Mode | Description |
|------|-------------|
| `loop` | Continuous looping playback |
| `presence` | Plays based on presence value (0.0-1.0 probability) |
| `sparse` | Plays occasionally with gaps between plays |
| `random` | Random playback from track pool |
| `sequential` | Plays tracks in order |
| `auto` | Automatically determined from file length |

#### Track Properties

| Property | Type | Description |
|----------|------|-------------|
| `presence` | float (0.0-1.0) | Probability of track playing |
| `volume` | float (0.0-1.0) | Track volume |
| `muted` | bool | Whether track is muted |
| `playback_mode` | string | How track is played (see above) |
| `seamless_loop` | bool | Enable gapless looping |
| `exclusive` | bool | Only one exclusive track plays at a time |

#### Presets

Presets allow users to save and switch between different track configurations:
- Each preset can override any track property
- One preset can be marked as default (`is_default: true`)
- Presets inherit base track settings and only store overrides

#### Theme Manager Interface

```python
class ThemeManager:
    async def scan_themes(path: Path) -> list[Theme]
    async def import_theme(zip_path: Path) -> Theme
    async def export_theme(theme_id: str, output_path: Path) -> Path
    def get_theme(theme_id: str) -> Optional[Theme]
    def get_themes() -> list[Theme]
    def get_themes_by_category(category: str) -> list[Theme]
    def apply_preset(theme_id: str, preset_id: str) -> bool
```

### 7. Channel System (`core/channels.py`)

Multi-zone audio routing.

```python
class Channel:
    id: str
    name: str
    speakers: list[str]         # Assigned speaker IDs
    theme: Optional[str]        # Currently playing theme
    volume: float

class ChannelManager:
    def get_channels() -> list[Channel]
    def assign_speakers(channel_id: str, speaker_ids: list[str])
    def play(channel_id: str, theme_id: str)
    def stop(channel_id: str)
```

---

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │     │    MQTT     │     │  External   │
│             │     │   Client    │     │    API      │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │   REST API  │
                    │  (FastAPI)  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    State    │
                    │   Manager   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
   ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
   │  Speaker  │    │  Theme    │    │  Channel  │
   │  Manager  │    │  Manager  │    │  Manager  │
   └─────┬─────┘    └───────────┘    └───────────┘
         │
   ┌─────▼─────┐
   │  Plugin   │
   │  System   │
   └─────┬─────┘
         │
   ┌─────▼─────┐
   │ Speakers  │
   │ (Network) │
   └───────────┘
```

---

## File Structure

```
shared/
├── core/
│   ├── __init__.py
│   ├── state.py            # State management
│   ├── streaming.py        # Audio streaming
│   ├── themes.py           # Theme management
│   ├── channels.py         # Channel/zone management
│   ├── mqtt.py             # MQTT bridge
│   └── logging.py          # Logging utilities
│
├── plugins/
│   ├── __init__.py
│   ├── base.py             # Plugin base classes
│   ├── loader.py           # Plugin discovery/loading
│   └── manager.py          # Plugin lifecycle
│
├── models/
│   ├── __init__.py
│   ├── speaker.py          # Speaker data model
│   ├── theme.py            # Theme data model
│   ├── session.py          # Session data model
│   └── settings.py         # Settings model
│
├── web/
│   ├── __init__.py
│   ├── api.py              # REST API endpoints
│   ├── app.py              # FastAPI application
│   └── static/             # Web UI files
│       ├── css/
│       ├── js/
│       └── index.html
│
└── ARCHITECTURE.md         # This document
```

---

## Platform-Specific Extensions

### Home Assistant Addon (`sonorium_addon/sonorium/ha/`)
- `registry.py` - Query HA device registry for additional speakers
- `media_controller.py` - Control speakers via HA media_player service
- `mqtt_entities.py` - Expose Sonorium entities to HA via MQTT discovery

### Standalone (`app/core/sonorium/standalone/`)
- `local_audio.py` - Local audio device playback
- `tray.py` - System tray integration (Windows/macOS)
- `updater.py` - Auto-update functionality

---

## Configuration

### Environment Variables
```
SONORIUM_DATA_DIR       # Data directory (themes, config)
SONORIUM_LOG_LEVEL      # Logging level (debug, info, warning, error)
SONORIUM_PORT           # HTTP server port (default: 8099)
SONORIUM_MQTT_HOST      # MQTT broker host
SONORIUM_MQTT_PORT      # MQTT broker port (default: 1883)
SONORIUM_MQTT_USERNAME  # MQTT username (optional)
SONORIUM_MQTT_PASSWORD  # MQTT password (optional)
```

### Config File (`config.json`)
```json
{
  "enabled_speakers": ["speaker_1", "speaker_2"],
  "master_volume": 0.8,
  "mqtt": {
    "enabled": true,
    "host": "localhost",
    "port": 1883,
    "topic_prefix": "sonorium"
  },
  "discovery": {
    "interval_seconds": 300,
    "protocols": ["sonos", "chromecast", "airplay", "dlna"]
  }
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-24 | Initial rebuild - architecture defined |
