# Sonorium Plugin Architecture

This document describes the plugin system architecture for Sonorium, enabling extensible functionality through installable plugins.

## Overview

Sonorium's plugin system allows developers to extend functionality through:
- **Speaker Plugins**: Add support for new network audio protocols
- **Importer Plugins**: Import themes from external sources
- **Utility Plugins**: General-purpose tools (theme merge, etc.)
- **Automation Plugins**: Integration with automation systems

## Plugin Types

| Type | Purpose | Examples |
|------|---------|----------|
| `speaker` | Network audio streaming protocols | Chromecast, Sonos, AirPlay, DLNA |
| `importer` | Theme/audio importers | Ambient Mixer, MyNoise |
| `utility` | General tools | Theme Merge |
| `automation` | System integrations | Home Assistant, Webhooks |

## Plugin Structure

Each plugin is a directory containing:

```
plugins/
└── my_plugin/
    ├── __init__.py       # Package initialization
    ├── manifest.json     # Plugin metadata
    └── plugin.py         # Plugin class
```

### manifest.json

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "Brief description of what the plugin does",
  "author": "Your Name",
  "plugin_type": "utility",
  "builtin": false,
  "entry_point": "plugin.py",
  "plugin_class": "MyPlugin",
  "dependencies": ["required-package"],
  "settings_schema": {
    "setting_name": {
      "type": "string",
      "default": "value",
      "label": "Setting Label"
    }
  }
}
```

### Plugin Class

```python
from sonorium.plugins.base import BasePlugin

class MyPlugin(BasePlugin):
    id = "my_plugin"
    name = "My Plugin"
    version = "1.0.0"
    description = "What this plugin does"
    author = "Your Name"
    plugin_type = "utility"

    async def on_load(self) -> None:
        """Called when plugin is loaded."""
        pass

    async def on_enable(self) -> None:
        """Called when plugin is enabled."""
        pass

    async def on_disable(self) -> None:
        """Called when plugin is disabled."""
        pass

    async def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        pass
```

## Speaker Plugins

For network speaker protocols, extend `SpeakerPlugin`:

```python
from sonorium.plugins.speaker_base import SpeakerPlugin, NetworkSpeaker, SpeakerState

class MySpeakerPlugin(SpeakerPlugin):
    id = "my_speaker"
    name = "My Speaker Protocol"
    version = "1.0.0"
    plugin_type = "speaker"

    async def discover_speakers(self) -> list[NetworkSpeaker]:
        """Discover speakers on the network."""
        # Return list of NetworkSpeaker objects
        pass

    async def play_url(self, speaker_id: str, url: str) -> bool:
        """Play a URL on a speaker."""
        pass

    async def stop(self, speaker_id: str) -> bool:
        """Stop playback."""
        pass

    async def set_volume(self, speaker_id: str, level: float) -> bool:
        """Set volume (0.0-1.0)."""
        pass
```

### NetworkSpeaker Data Class

```python
@dataclass
class NetworkSpeaker:
    id: str                    # Unique identifier
    name: str                  # Display name
    model: str = ""            # Device model
    manufacturer: str = ""     # Manufacturer
    ip_address: str = ""       # IP address
    port: int = 0              # Control port
    state: SpeakerState        # Current state
    volume: float = 1.0        # Volume 0.0-1.0
    is_muted: bool = False
    current_media: str = None  # Currently playing URL
    capabilities: list[str]    # ["volume", "mute", "pause"]
    extra: dict                # Plugin-specific data
```

## Builtin Plugins

Sonorium includes these builtin plugins:

### Speaker Protocols
| Plugin | Protocol | Status |
|--------|----------|--------|
| Chromecast | Google Cast | Active |
| Sonos | SoCo | Active |
| AirPlay | pyatv/RAOP | Active |
| DLNA | UPnP AVTransport | Active |

### Theme Importers
| Plugin | Source | Status |
|--------|--------|--------|
| Ambient Mixer | ambient-mixer.com | Active |
| MyNoise | mynoise.net | Active |

### Utilities
| Plugin | Purpose | Status |
|--------|---------|--------|
| Theme Merge | Combine themes | Active |

## Plugin Lifecycle

1. **Discovery**: Plugin directories scanned on startup
2. **Loading**: Manifest read, class loaded, `on_load()` called
3. **Enabling**: User enables plugin, `on_enable()` called
4. **Running**: Plugin is active, handles actions
5. **Disabling**: User disables, `on_disable()` called
6. **Unloading**: App shutdown, `on_unload()` called

## Installing Plugins

### From ZIP File

1. Create a ZIP file containing the plugin directory
2. Upload via Settings > Plugins > Upload Plugin
3. Plugin is extracted and loaded automatically

### Manual Installation

1. Copy plugin directory to `plugins/`
2. Restart Sonorium or reload plugins

## API Reference

### Plugin Manager Methods

```python
# List all plugins
plugins = plugin_manager.list_plugins()

# Get plugin by ID
plugin = plugin_manager.get_plugin("plugin_id")

# Enable/disable
await plugin_manager.enable_plugin("plugin_id")
await plugin_manager.disable_plugin("plugin_id")

# Install from ZIP
result = await plugin_manager.install_plugin_from_zip(path)
result = await plugin_manager.install_plugin_from_bytes(data, filename)

# Delete plugin (non-builtin only)
result = await plugin_manager.delete_plugin("plugin_id")

# Get plugins by type
speakers = plugin_manager.get_speaker_plugins()
importers = plugin_manager.get_importer_plugins()
```

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/plugins` | GET | List all plugins |
| `/plugins/{id}` | GET | Get plugin details |
| `/plugins/{id}/enable` | POST | Enable plugin |
| `/plugins/{id}/disable` | POST | Disable plugin |
| `/plugins/{id}/action` | POST | Call plugin action |
| `/plugins/{id}/settings` | GET/PUT | Get/update settings |
| `/plugins/upload` | POST | Install from ZIP |
| `/api/plugins/{id}` | DELETE | Delete plugin |

## UI Integration

Plugins can provide UI schemas for settings and actions:

```python
def get_ui_schema(self) -> dict:
    return {
        "type": "form",
        "fields": [
            {
                "name": "url",
                "type": "url",
                "label": "URL",
                "required": True,
                "placeholder": "https://..."
            }
        ],
        "actions": [
            {
                "id": "import",
                "label": "Import",
                "primary": True
            }
        ]
    }

def get_settings_schema(self) -> dict:
    return {
        "auto_refresh": {
            "type": "boolean",
            "default": True,
            "label": "Auto-refresh"
        }
    }

async def handle_action(self, action: str, data: dict) -> dict:
    if action == "import":
        # Handle import action
        return {"success": True, "message": "Imported successfully"}
    return {"success": False, "message": f"Unknown action: {action}"}
```

## Best Practices

1. **Use async methods**: All lifecycle hooks and actions should be async
2. **Handle missing dependencies**: Check for optional imports gracefully
3. **Clean up resources**: Release connections in `on_disable()` and `on_unload()`
4. **Log appropriately**: Use `logger.info()`, `logger.debug()`, `logger.error()`
5. **Validate input**: Check action data before processing
6. **Return proper responses**: Always return `{"success": bool, "message": str}`

## Platform Compatibility

Plugins must be platform-agnostic:
- Use `pathlib.Path` for file paths
- Use `asyncio` for concurrency
- Use pip-installable dependencies only
- No subprocess calls to OS tools
- No hardcoded paths

## Testing Plugins

1. Place plugin in `plugins/` directory
2. Start Sonorium in development mode
3. Enable plugin via Settings > Plugins
4. Test functionality
5. Check logs for errors

## Troubleshooting

### Plugin Not Loading
- Check `manifest.json` syntax
- Verify `plugin.py` exists
- Check for import errors in logs

### Plugin Actions Failing
- Verify plugin is enabled
- Check action data format
- Look for exceptions in logs

### Dependencies Missing
- Install via `pip install <package>`
- Add to `dependencies` in manifest
