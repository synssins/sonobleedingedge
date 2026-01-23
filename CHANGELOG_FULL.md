# Sonorium Full Changelog (v0.0.2 → v0.0.70)

## Overview

This document summarizes all significant changes from the initial bleeding edge release through the current version, organized by feature area.

---

## 🏗️ Architecture & Platform Parity (v0.0.48 - v0.0.51)

### Shared Code Consolidation
- **Moved CORE files to `shared/`** - Single source of truth for:
  - `obs.py` - Logging/observability
  - `recording.py` - Audio recording/mixing engine
  - `theme.py` - Theme management
  - `track.py` - Track/layer handling
  - `network_speakers.py` - Network speaker discovery
  - `streaming.py` - Streaming to network speakers
  - `utils.py` - Shared utilities

- **Core business logic in `shared/core/`**:
  - `channel.py` - Channel system
  - `state.py` - State management (platform-agnostic)
  - `speaker_manager.py` - Speaker management
  - `cycle_manager.py` - Theme cycling
  - `theme_metadata.py` - Theme metadata
  - `log_collector.py` - Log collection

- **Web UI moved to `shared/web/`** - Identical frontend across all platforms
- **Automated sync system** - `scripts/sync_shared.py` ensures platform parity

### Platform Capabilities System (v0.0.51)
- Unified capabilities API for feature detection
- Settings system adapts UI based on platform (HA vs Standalone)
- Graceful degradation for platform-specific features

---

## 🔌 Plugin System (v0.0.2 - v0.0.47)

### TRUE Plugin Architecture (v0.0.6)
Extracted all speaker protocols to independent, deletable plugins:

| Plugin | Protocol | Version |
|--------|----------|---------|
| Sonos | SoCo library | v1.0.0 |
| Chromecast | pychromecast | v1.0.1 |
| AirPlay | pyatv (RAOP) | v1.0.0 |
| DLNA | async_upnp_client | v1.0.0 |
| HEOS | aiohttp (telnet) | v1.0.0 |
| Linkplay | HTTP API | v1.0.0 |

### Plugin Browser & Catalog (v0.0.29+)
- **One-click plugin installation** from online catalog
- **Category filtering** (Speakers, Importers, Utilities)
- **Plugin settings UI** - Per-plugin configuration
- **Upload custom plugins** - ZIP file support
- **Auto-enable on install** - Plugins activate immediately

### Plugin Infrastructure
- `PluginType` enum for categorization
- Manifest-based metadata (name, version, author, category)
- Multi-path plugin discovery (bundled + user-installed)
- Plugin enable/disable with persistence

---

## 🔊 Speaker Discovery & Control

### Hybrid Discovery (HA Addon)
- **HA Registry integration** - Discovers speakers from Home Assistant
- **Direct network discovery** - mDNS, SSDP, protocol-specific
- **Speaker deduplication** - Single entry when found by multiple methods
- **Fuzzy name matching** - Handles slight naming differences

### Speaker Protocols Supported
- **Sonos** - Full SoCo integration with SonosPlayer
- **Chromecast/Google Cast** - CastPlayer with direct streaming
- **AirPlay 1 & 2** - pyatv with compatibility patches
- **DLNA/UPnP** - async_upnp_client renderer control
- **HEOS** - Denon/Marantz devices (beta)
- **Linkplay** - Arylic and compatible devices

### Speaker Features
- **Volume control** per speaker and per channel (v0.0.65)
- **Protocol badges** - Visual indicators (AIRPLAY, DLNA, SONOS, etc.)
- **IP address display** in Settings → Speakers
- **Model detection** - Device model names shown
- **Enable/disable** with persistence
- **MQTT entities** for direct-discovered speakers

---

## 🎨 User Interface

### Settings & Configuration
- **HA/MQTT Integration page** (v0.0.55)
  - Autodetect toggles for HA and MQTT
  - Connection status indicators (Connected/Not Configured)
  - Manual configuration fields
- **Collapsible sections** in Settings (v0.0.60)
- **Floor/Area hierarchy** for speakers (HA addon)
- **Speaker Groups** management

### Theme System
- **Theme browser** with category grid
- **Theme selector dropdown** in channel editor (v0.0.69)
- **Theme icons** properly resolved from theme data (v0.0.68)
- **Theme cycling** via cycle_manager

### Channel Editor
- **Multi-speaker selection** per channel
- **Volume sliders** - Channel and speaker-level
- **Theme assignment** with preview
- **Track management** with exclusive mode

### Mobile UI (v0.0.70)
- **Responsive speaker cards** - Protocols wrap on mobile
- **Compact buttons** - Icon-only on small screens
- **Single-column themes** on mobile
- **Touch-friendly action buttons** - 2-column grid
- **Sidebar auto-close** when tapping outside

### Status & Diagnostics
- **Internal logs panel** - View logs in UI
- **Server self-test** diagnostic
- **Update checker** with manual button (v0.0.56)
- **Auto-install updates** after download (v0.0.55)

---

## 🔧 Bug Fixes & Improvements

### Audio Quality
- **Fixed audio distortion** - Changed DEFAULT_OUTPUT_GAIN from 6.0 to 1.0 (v0.0.61)
- **AirPlay 1 compatibility patches** for pyatv

### Startup & Performance
- **Delayed speaker validation** - Waits for server start (v0.0.64)
- **Reduced log verbosity** - Cleaner startup output (v0.0.66)
- **Streamlined startup logging** with log_level setting
- **Plugin scanning efficiency** improvements

### Speaker Issues Fixed
- Sonos IP discovery for large HA installations
- Cast device IP resolution with mDNS fallback
- Speaker toggle bounce-back with single speaker
- Channel volume slider controlling speaker volume
- Speakers not loading on first view

### UI Fixes
- Page refresh navigation
- Plugin catalog refresh
- Settings menu expansion persistence
- Infinite spinner on Speakers view
- Stale speaker list in channel editor

### Security
- MQTT password hidden from logs

---

## 📁 Project Structure

```
sonobleedingedge/
├── shared/                    # SOURCE OF TRUTH
│   ├── *.py                   # Core modules
│   ├── core/                  # Business logic
│   ├── web/                   # Frontend (HTML/CSS/JS)
│   ├── plugins/               # Plugin framework
│   ├── models/                # Data models
│   └── platform/              # Platform adapters
│
├── sonorium_addon/            # HA Add-on
│   ├── config.yaml            # HA manifest
│   ├── Dockerfile
│   └── sonorium/              # Synced + HA-specific
│       └── ha/                # HA integration layer
│
├── app/                       # Standalone
│   ├── core/sonorium/         # Synced + standalone-specific
│   ├── windows/               # Windows launcher (PyQt6)
│   └── docker/                # Docker deployment
│
├── plugins/                   # Plugin implementations
│   └── speakers/              # Speaker protocol plugins
│
└── scripts/
    └── sync_shared.py         # Sync automation
```

---

## 📊 Version History Summary

| Version | Milestone |
|---------|-----------|
| 0.0.2 | Initial bleeding edge - Core file alignment |
| 0.0.3 | Plugin manager initialization fixes |
| 0.0.6 | TRUE speaker plugins extracted |
| 0.0.7 | Platform adapters complete |
| 0.0.29 | Plugin ZIP files for reinstall support |
| 0.0.47 | Plugin auto-install and category fixes |
| 0.0.50 | CORE code consolidated to shared/ |
| 0.0.51 | Unified platform capabilities |
| 0.0.55 | HA/MQTT Integration page redesign |
| 0.0.60 | Speaker enable/disable + collapsible UI |
| 0.0.61 | Audio distortion fix |
| 0.0.65 | Network speaker volume control |
| 0.0.69 | Theme dropdown + mobile sidebar |
| 0.0.70 | Mobile UI responsiveness |

---

## 🖼️ Screenshots Available

| Screenshot | Description |
|------------|-------------|
| `Channels.png` | Channel list view |
| `Channels_Theme_Selection.png` | Theme dropdown in editor |
| `Themes.png` | Theme browser |
| `Settings.png` | Settings page |
| `settings-ha-mqtt-manual-config.png` | HA/MQTT manual setup |
| `settings-ha-mqtt-autodetect-connected.png` | HA/MQTT connected |
| `speaker-settings-ha-addon-protocols.png` | HA speaker protocols |
| `speaker-settings-standalone-protocols.png` | Standalone protocols |
| `mockup-plugin-catalog-browser.png` | Plugin catalog (mockup) |
| `mockup-plugin-installed-management.png` | Installed plugins (mockup) |

---

## 🚀 What's Next

### Pending for Public Release
- [ ] README updates with new screenshots
- [ ] sonorium.app website refresh
- [ ] Documentation for all features
- [ ] Video tutorials/demos

### Future Considerations
- Plugin marketplace/store (mockups exist)
- Additional speaker protocols
- Theme import from external sources
- Advanced scheduling/automation
