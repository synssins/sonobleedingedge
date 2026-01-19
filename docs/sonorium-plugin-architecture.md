# Sonorium Plugin Architecture

## Overview

This document defines the plugin architecture for Sonorium, enabling extensible functionality through modular, self-contained plugins. Plugins can extend Sonorium's capabilities in areas such as audio source browsing, scheduling, audio processing, and Home Assistant integration.

## Design Principles

1. **Isolation** - Plugins operate independently; one plugin's failure doesn't crash Sonorium
2. **Discoverability** - Plugins self-describe their capabilities, settings, and UI components
3. **Consistency** - All plugins follow the same interface patterns
4. **Security** - Plugins have scoped permissions; sensitive operations require explicit grants
5. **Hot-reload** - Plugins can be enabled/disabled without restarting Sonorium

---

## Plugin Directory Structure

```
/config/sonorium/plugins/
├── enabled/                    # Symlinks to active plugins
├── available/                  # All installed plugins
│   ├── theme-pack-manager/
│   │   ├── manifest.json       # Plugin metadata & capabilities
│   │   ├── plugin.py           # Main plugin entry point
│   │   ├── routes.py           # Optional: API routes
│   │   ├── ui/                 # Optional: Frontend components
│   │   │   ├── settings.jsx    # Settings panel component
│   │   │   └── panel.jsx       # Main UI panel (if applicable)
│   │   ├── requirements.txt    # Python dependencies
│   │   └── README.md           # Documentation
│   └── soundscape-scheduler/
│       └── ...
└── plugin_registry.json        # Tracks installed plugins & state
```

---

## Plugin Manifest (manifest.json)

Every plugin must include a manifest file describing its capabilities:

```json
{
  "id": "theme-pack-manager",
  "name": "Theme Pack Manager",
  "version": "1.0.0",
  "description": "Create, export, import, and share Sonorium theme packs",
  "author": "Sonorium Contributors",
  "license": "MIT",
  
  "sonorium_version": ">=1.2.0",
  "python_version": ">=3.10",
  
  "entry_point": "plugin.py",
  "class_name": "ThemePackManagerPlugin",
  
  "capabilities": {
    "has_settings_ui": true,
    "has_main_panel": true,
    "registers_api_routes": true,
    "registers_ha_entities": false,
    "requires_network": false,
    "modifies_audio_files": true,
    "modifies_themes": true
  },
  
  "permissions": [
    "read_themes",
    "write_themes",
    "read_audio_files",
    "write_audio_files",
    "access_config"
  ],
  
  "config_schema": {
    "type": "object",
    "properties": {
      "export_directory": {
        "type": "string",
        "title": "Export Directory",
        "default": "/config/sonorium/exports"
      }
    }
  }
}
```

---

## Plugin Base Class

All plugins must inherit from SonoriumPlugin:

```python
from abc import ABC
from typing import Dict, Any, Optional, List
from enum import Enum
import logging

class PluginState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"

class SonoriumPlugin(ABC):
    """Base class for all Sonorium plugins."""
    
    def __init__(self):
        self.context: Optional[PluginContext] = None
        self.state: PluginState = PluginState.UNLOADED
        self.logger = None
    
    async def initialize(self, context: PluginContext) -> bool:
        """Called when plugin is loaded. Return True if successful."""
        self.context = context
        self.logger = logging.getLogger(f"sonorium.plugin.{context.plugin_id}")
        return True
    
    async def activate(self) -> bool:
        """Called when plugin is enabled. Start background tasks here."""
        self.state = PluginState.ACTIVE
        return True
    
    async def deactivate(self) -> None:
        """Called when plugin is disabled. Stop background tasks."""
        self.state = PluginState.DISABLED
    
    async def shutdown(self) -> None:
        """Called when Sonorium shuts down. Final cleanup."""
        pass
    
    def get_api_routes(self) -> List[APIRoute]:
        """Return API routes this plugin provides."""
        return []
    
    def get_ha_entities(self) -> List[HAEntityDefinition]:
        """Return HA entities this plugin creates (addon mode only)."""
        return []
    
    def get_actions(self) -> Dict[str, callable]:
        """Return callable actions for automation/other plugins."""
        return {}
```

---

## PluginContext

```python
from dataclasses import dataclass

@dataclass
class PluginContext:
    """Injected context providing plugins access to Sonorium services."""
    plugin_id: str
    config: Dict[str, Any]
    data_dir: str
    
    # Service references
    theme_manager: ThemeManager
    audio_manager: AudioManager
    session_manager: SessionManager
    config_manager: ConfigManager
    event_bus: EventBus
    ha_client: Optional[HomeAssistantClient]  # None if standalone
    
    # Platform detection
    platform: str  # "standalone", "ha_addon", "docker"
    
    async def get_setting(self, key: str, default: Any = None) -> Any: ...
    async def set_setting(self, key: str, value: Any) -> None: ...
    async def emit_event(self, event_type: str, data: Dict) -> None: ...
```

---

## EventBus

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Event:
    type: str
    data: Dict[str, Any]
    source: str
    timestamp: datetime

class EventBus:
    """Central event bus for plugin communication."""
    
    def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe to event. Returns subscription ID."""
        ...
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from event."""
        ...
    
    async def emit(self, event_type: str, data: Dict, source: str = "core") -> None:
        """Emit event to all subscribers."""
        ...


class EventTypes:
    """Standard event type constants."""
    PLAYBACK_STARTED = "playback.started"
    PLAYBACK_STOPPED = "playback.stopped"
    VOLUME_CHANGED = "playback.volume_changed"
    THEME_CHANGED = "theme.changed"
    THEME_CREATED = "theme.created"
    THEME_DELETED = "theme.deleted"
    SESSION_CREATED = "session.created"
    SESSION_DELETED = "session.deleted"
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_ACTIVATED = "plugin.activated"
    PLUGIN_DEACTIVATED = "plugin.deactivated"
    PLUGIN_ERROR = "plugin.error"
    SCHEDULE_TRIGGERED = "schedule.triggered"
    SCHEDULE_OVERRIDDEN = "schedule.overridden"
    HA_STATE_CHANGED = "ha.state_changed"
```

---

## PluginManager

```python
class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""
    
    def __init__(self, plugins_dir: str, event_bus: EventBus):
        self.plugins_dir = plugins_dir
        self.event_bus = event_bus
        self.plugins: Dict[str, SonoriumPlugin] = {}
        self.manifests: Dict[str, Dict] = {}
    
    async def discover_plugins(self) -> List[str]:
        """Scan plugins directory, return list of plugin IDs."""
        ...
    
    async def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin by ID. Returns True if successful."""
        ...
    
    async def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin."""
        ...
    
    async def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a loaded plugin."""
        ...
    
    async def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin without unloading."""
        ...
    
    async def shutdown_all(self) -> None:
        """Shutdown all active plugins."""
        ...
```

---

## API Route Registration

```python
from dataclasses import dataclass
from enum import Enum

class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

@dataclass
class APIRoute:
    path: str                    # e.g., "/packs" (prefixed with /api/plugins/{plugin_id})
    method: HTTPMethod
    handler: Callable
    summary: str
    requires_auth: bool = True
```

---

## Home Assistant Entity Registration

```python
from dataclasses import dataclass
from enum import Enum

class HAEntityType(Enum):
    SWITCH = "switch"
    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SELECT = "select"
    NUMBER = "number"
    BUTTON = "button"

@dataclass
class HAEntityDefinition:
    entity_type: HAEntityType
    unique_id: str
    name: str
    icon: str = "mdi:puzzle"
    state_getter: Callable[[], Any] = None
    state_setter: Callable[[Any], None] = None
```

---

## Permissions System

| Permission | Description |
|------------|-------------|
| read_themes | Read theme configurations |
| write_themes | Create, modify, delete themes |
| read_audio_files | Access audio file contents |
| write_audio_files | Add, remove, modify audio files |
| read_sessions | Read session/channel state |
| write_sessions | Control playback, modify sessions |
| access_config | Read/write Sonorium configuration |
| network_access | Make outbound network requests |
| ha_read | Read Home Assistant states |
| ha_write | Call Home Assistant services |
| ha_entities | Create Home Assistant entities |

---

## Platform Detection

```python
import os
import sys

def get_plugins_directory() -> str:
    if os.path.exists("/config/sonorium"):
        return "/config/sonorium/plugins"
    if os.environ.get("DOCKER_CONTAINER"):
        return "/data/plugins"
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", ""), "Sonorium", "plugins")
    return os.path.expanduser("~/.sonorium/plugins")

def get_platform() -> str:
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "ha_addon"
    if os.environ.get("DOCKER_CONTAINER"):
        return "docker"
    return "standalone"
```

---

## Integration with FOUNDATIONAL_CHANGES.md

The plugin system is implemented as `plugins.py` - an **optional module** per the modular architecture:

- **Module metadata**: `__feature_name__ = "Plugin System"`, `__required__ = False`
- **Standard interface**: `init(app_context)`, `shutdown()`, `health_check()`
- **Category A file**: Identical across all platforms
- **Graceful degradation**: App runs without plugins if module is missing
