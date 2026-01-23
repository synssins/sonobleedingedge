# Unified Platform Architecture

> **Design Document for Sonorium Platform Unification**
> **Created:** 2026-01-23
> **Status:** Implementation In Progress

---

## Overview

This document describes the unified architecture that allows Sonorium to run identically across all platforms (Standalone, Docker, HA Addon) with automatic capability detection and user-configurable overrides.

## Core Principles

1. **Single Codebase** - One API file handles all platforms
2. **Auto-detection** - Platform and hardware capabilities detected at startup
3. **User Override** - All auto-detected settings can be manually configured
4. **Graceful Degradation** - Features unavailable on a platform are hidden, not broken
5. **Feature Parity** - Any platform CAN have any feature if hardware/config supports it

---

## Platform Detection

### Detection Hierarchy

```python
def detect_platform() -> str:
    """Detect current platform at startup."""
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "ha_addon"
    elif os.environ.get("SONORIUM_DOCKER") or os.path.exists("/.dockerenv"):
        return "docker"
    else:
        return "standalone"
```

### Capability Detection

```python
@dataclass
class PlatformCapabilities:
    platform: str                    # 'standalone' | 'docker' | 'ha_addon'

    # Home Assistant
    ha_detected: bool                # SUPERVISOR_TOKEN present
    ha_enabled: bool                 # User has HA integration enabled
    ha_token: str | None             # Auto-detected or user-provided
    supervisor_url: str | None       # Auto-detected or user-provided

    # MQTT
    mqtt_detected: bool              # HA addon MQTT auto-discovered
    mqtt_enabled: bool               # User has MQTT enabled
    mqtt_broker: str | None
    mqtt_port: int | None
    mqtt_username: str | None
    mqtt_password: str | None        # Stored securely

    # Local Audio
    local_audio_available: bool      # Audio devices detected
    local_audio_enabled: bool        # User has enabled local audio
    local_audio_devices: list[dict]  # All detected devices
    enabled_audio_devices: list[str] # User-enabled device IDs

    # Discovery
    direct_discovery: bool = True    # mDNS/SSDP always available
    hybrid_discovery: bool           # HA registry + direct (requires HA)
```

---

## Settings Architecture

### Settings Storage

```
config/
├── settings.json          # General settings (plaintext)
├── settings.secure.json   # Encrypted sensitive values (tokens, passwords)
└── settings.defaults.json # Default values for reset
```

### Secure Storage

Sensitive values encrypted using:
- **Standalone/Docker**: Machine-specific key derived from hardware ID
- **HA Addon**: HA's secrets management or encrypted file

Secured fields:
- `ha_token`
- `mqtt_password`

### Settings Schema

```json
{
  "ha_integration": {
    "autodetect": true,
    "override": false,
    "enabled": false,
    "token": null,
    "supervisor_url": null
  },
  "mqtt": {
    "autodetect": true,
    "override": false,
    "enabled": false,
    "broker": null,
    "port": 1883,
    "username": null,
    "password": null,
    "discovery_prefix": "homeassistant"
  },
  "local_audio": {
    "enabled": false,
    "devices": {}
  }
}
```

---

## Home Assistant Integration

### Auto-detection (HA Addon)

When running as HA addon:
1. Detect `SUPERVISOR_TOKEN` environment variable
2. Query Supervisor API for MQTT addon credentials
3. Auto-populate HA and MQTT settings
4. Initialize HA registry integration
5. Initialize MQTT entity publishing

### Manual Configuration (Standalone/Docker)

Users can manually configure HA integration:
1. Enable "Home Assistant Integration" toggle
2. Disable "Autodetect" toggle
3. Enter HA Long-Lived Access Token
4. Enter HA URL (e.g., `http://homeassistant.local:8123`)
5. Optionally configure MQTT broker details

### Settings UI - Home Assistant Page

| Setting | Auto-detect Value | Override Enabled | Notes |
|---------|-------------------|------------------|-------|
| Enable HA Integration | - | Editable | Master toggle |
| Autodetect | On by default | - | Toggle |
| Override | Off by default | - | Unlocks fields below |
| HA Token | From env/greyed | Editable | Stored securely |
| Supervisor URL | From env/greyed | Editable | |
| MQTT Broker | From HA/greyed | Editable | |
| MQTT Port | 1883/greyed | Editable | |
| MQTT Username | From HA/greyed | Editable | |
| MQTT Password | From HA/greyed | Editable | Stored securely |

**Buttons:**
- `[Reset to Defaults]` - Clears all overrides, restores defaults

### Conditional UI Elements

When HA is active (detected OR manually configured and enabled):
- Speakers page shows "Refresh from HA" button
- Speakers list shows HA icon next to HA-discovered speakers

When HA is NOT active:
- These elements are removed from the DOM (not hidden)

---

## Local Audio Device Management

### Detection

```python
import sounddevice as sd

def detect_audio_devices() -> list[dict]:
    """Enumerate available audio output devices."""
    devices = []
    for i, device in enumerate(sd.query_devices()):
        if device['max_output_channels'] > 0:
            devices.append({
                'id': str(i),
                'name': device['name'],
                'channels': device['max_output_channels'],
                'sample_rate': device['default_samplerate'],
                'is_default': i == sd.default.device[1]
            })
    return devices
```

### Settings UI - Local Audio Page

| Element | Condition | Behavior |
|---------|-----------|----------|
| Enable Local Audio | Devices detected | Toggle enabled |
| Enable Local Audio | No devices | Toggle disabled + message |
| Device List | Local audio enabled | Show all devices with toggles |
| Device Toggle | Per device | Enable/disable as speaker |

**Message when no devices:**
> "No audio output devices detected on this system"

### Enabled Devices as Speakers

Enabled local audio devices appear in the speaker selection:
- Listed alongside network speakers
- Icon indicates local device (speaker icon vs network icon)
- Volume control per device
- Can be assigned to channels like any speaker

---

## Unified API Structure

### File Organization

```
shared/
├── platform/
│   ├── __init__.py
│   ├── capabilities.py      # Platform/capability detection
│   ├── secure_storage.py    # Encrypted settings storage
│   └── settings.py          # Unified settings management
│
└── web/
    ├── unified_api.py       # Single unified API file
    ├── static/
    └── templates/
```

### API Endpoint Organization

```python
def create_app(capabilities: PlatformCapabilities) -> FastAPI:
    app = FastAPI()

    # Core endpoints (always registered)
    register_core_endpoints(app)           # themes, presets, channels
    register_plugin_endpoints(app)         # plugin management, catalog
    register_speaker_endpoints(app)        # network speakers
    register_settings_endpoints(app)       # all settings including HA/MQTT/audio
    register_capabilities_endpoint(app)    # /api/capabilities

    # Conditional endpoints
    if capabilities.local_audio_available:
        register_local_audio_endpoints(app)

    if capabilities.ha_enabled:
        register_ha_endpoints(app)         # HA registry queries

    if capabilities.mqtt_enabled:
        register_mqtt_endpoints(app)       # MQTT status/control

    return app
```

### Capabilities Endpoint

```python
@app.get('/api/capabilities')
async def get_capabilities():
    """Return current platform capabilities for frontend adaptation."""
    return {
        'platform': capabilities.platform,
        'features': {
            'ha_integration': {
                'detected': capabilities.ha_detected,
                'enabled': capabilities.ha_enabled,
                'autodetect': settings.ha_integration.autodetect,
                'override': settings.ha_integration.override
            },
            'mqtt': {
                'detected': capabilities.mqtt_detected,
                'enabled': capabilities.mqtt_enabled,
                'connected': mqtt_client.is_connected if mqtt_client else False
            },
            'local_audio': {
                'available': capabilities.local_audio_available,
                'enabled': capabilities.local_audio_enabled,
                'device_count': len(capabilities.local_audio_devices),
                'reason': None if capabilities.local_audio_available
                         else 'No audio output devices detected'
            },
            'hybrid_discovery': {
                'available': capabilities.ha_enabled,
                'enabled': capabilities.ha_enabled
            }
        }
    }
```

---

## Frontend Adaptation

### Initialization

```javascript
// On app load
async function initializeApp() {
    const caps = await api('GET', '/api/capabilities');
    window.capabilities = caps;

    // Adapt UI based on capabilities
    adaptUIForCapabilities(caps);
}

function adaptUIForCapabilities(caps) {
    // HA-specific elements
    if (!caps.features.ha_integration.enabled) {
        // Remove HA elements entirely
        document.querySelectorAll('.ha-only').forEach(el => el.remove());
    }

    // Local audio
    if (!caps.features.local_audio.available) {
        disableLocalAudioToggle(caps.features.local_audio.reason);
    }
}
```

### Conditional Elements

```html
<!-- Only shown when HA is enabled -->
<button class="ha-only" onclick="refreshFromHA()">Refresh from HA</button>

<!-- Speaker row with conditional HA icon -->
<div class="speaker-row">
    <span class="speaker-name">Living Room</span>
    <span class="ha-only ha-icon" title="Discovered via Home Assistant">🏠</span>
</div>
```

---

## Migration Path

### Phase 1: Foundation
- [x] Create design document
- [ ] Create `shared/platform/capabilities.py`
- [ ] Create `shared/platform/secure_storage.py`
- [ ] Create `shared/platform/settings.py`

### Phase 2: Unified API
- [ ] Create `shared/web/unified_api.py`
- [ ] Merge all endpoints from `web_api.py` and `api_v2.py`
- [ ] Add conditional registration
- [ ] Add `/api/capabilities` endpoint

### Phase 3: Settings UI
- [ ] Add HA/MQTT settings page
- [ ] Add Local Audio settings page
- [ ] Implement secure token storage
- [ ] Add Reset to Defaults functionality

### Phase 4: Frontend
- [ ] Query capabilities on load
- [ ] Implement conditional UI rendering
- [ ] Remove HA elements when not enabled
- [ ] Implement local audio device list

### Phase 5: Integration
- [ ] Update standalone `main.py` to use unified API
- [ ] Update HA addon `entrypoint.py` to use unified API
- [ ] Test all platforms
- [ ] Remove old API files

---

## Security Considerations

1. **Token Storage**: HA tokens encrypted at rest
2. **Password Storage**: MQTT passwords encrypted at rest
3. **API Access**: Settings endpoints should validate request origin
4. **Override Mode**: Warn users when enabling override mode

---

## Testing Checklist

- [ ] Standalone with no HA config
- [ ] Standalone with manual HA config
- [ ] Docker with no HA config
- [ ] Docker with manual HA config
- [ ] HA Addon with autodetect
- [ ] HA Addon with override
- [ ] Local audio on Windows
- [ ] Local audio on Linux/Docker
- [ ] Local audio on HA Addon (if available)
- [ ] Reset to Defaults functionality
- [ ] Secure storage encryption/decryption
