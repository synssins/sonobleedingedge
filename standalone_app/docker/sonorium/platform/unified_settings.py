"""
Unified Settings Management

Provides a single settings interface for all platforms with support for:
- Auto-detected values (greyed in UI)
- User overrides (persist through restarts)
- Secure storage for sensitive values
- Reset to defaults functionality

CORE CODE: This module is platform-agnostic and shared across all deployment targets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

from ..obs import logger


@dataclass
class HAIntegrationSettings:
    """Home Assistant integration settings."""
    enabled: bool = False            # Master toggle
    autodetect: bool = True          # Use auto-detected values
    override: bool = False           # User is overriding auto values

    # These are stored in secure storage, not here
    # token: str - stored securely
    # supervisor_url: str - can be stored here (not sensitive)
    supervisor_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'HAIntegrationSettings':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MQTTSettings:
    """MQTT broker settings."""
    enabled: bool = False            # Master toggle
    autodetect: bool = True          # Use auto-detected values
    override: bool = False           # User is overriding auto values

    broker: str | None = None
    port: int = 1883
    username: str | None = None
    # password: str - stored securely
    discovery_prefix: str = 'homeassistant'

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'MQTTSettings':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LocalAudioSettings:
    """Local audio output settings."""
    enabled: bool = False            # Master toggle
    devices: dict[str, dict] = field(default_factory=dict)
    # devices format: {"device_id": {"enabled": true, "name": "Speaker Name"}}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'LocalAudioSettings':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_device_enabled(self, device_id: str) -> bool:
        """Check if a specific device is enabled."""
        return self.devices.get(device_id, {}).get('enabled', False)

    def set_device_enabled(self, device_id: str, enabled: bool, name: str = '') -> None:
        """Enable or disable a specific device."""
        if device_id not in self.devices:
            self.devices[device_id] = {'enabled': enabled, 'name': name}
        else:
            self.devices[device_id]['enabled'] = enabled
            if name:
                self.devices[device_id]['name'] = name

    def get_enabled_device_ids(self) -> list[str]:
        """Get list of enabled device IDs."""
        return [did for did, cfg in self.devices.items() if cfg.get('enabled', False)]


@dataclass
class UnifiedSettings:
    """
    Complete unified settings for all platforms.

    Manages HA integration, MQTT, local audio, and general settings.
    """
    ha_integration: HAIntegrationSettings = field(default_factory=HAIntegrationSettings)
    mqtt: MQTTSettings = field(default_factory=MQTTSettings)
    local_audio: LocalAudioSettings = field(default_factory=LocalAudioSettings)

    # General settings (existing)
    master_volume: float = 0.8
    auto_play_on_start: bool = False
    last_theme: str | None = None

    # Plugin settings
    plugin_settings: dict[str, dict] = field(default_factory=dict)
    enabled_plugins: list[str] = field(default_factory=list)
    deleted_builtin_plugins: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'ha_integration': self.ha_integration.to_dict(),
            'mqtt': self.mqtt.to_dict(),
            'local_audio': self.local_audio.to_dict(),
            'master_volume': self.master_volume,
            'auto_play_on_start': self.auto_play_on_start,
            'last_theme': self.last_theme,
            'plugin_settings': self.plugin_settings,
            'enabled_plugins': self.enabled_plugins,
            'deleted_builtin_plugins': self.deleted_builtin_plugins,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'UnifiedSettings':
        """Create from dictionary."""
        settings = cls()

        if 'ha_integration' in data:
            settings.ha_integration = HAIntegrationSettings.from_dict(data['ha_integration'])
        if 'mqtt' in data:
            settings.mqtt = MQTTSettings.from_dict(data['mqtt'])
        if 'local_audio' in data:
            settings.local_audio = LocalAudioSettings.from_dict(data['local_audio'])

        settings.master_volume = data.get('master_volume', 0.8)
        settings.auto_play_on_start = data.get('auto_play_on_start', False)
        settings.last_theme = data.get('last_theme')
        settings.plugin_settings = data.get('plugin_settings', {})
        settings.enabled_plugins = data.get('enabled_plugins', [])
        settings.deleted_builtin_plugins = data.get('deleted_builtin_plugins', [])

        return settings

    @classmethod
    def get_defaults(cls) -> 'UnifiedSettings':
        """Get default settings."""
        return cls()


class UnifiedSettingsManager:
    """
    Manages unified settings with file persistence and secure storage.

    Provides:
    - Load/save settings to JSON file
    - Secure storage for sensitive values (tokens, passwords)
    - Reset to defaults
    - Change callbacks for reactive updates
    """

    def __init__(self, data_dir: Path):
        """
        Initialize settings manager.

        Args:
            data_dir: Directory for settings files
        """
        self.data_dir = data_dir
        self.settings_path = data_dir / 'unified_settings.json'
        self.defaults_path = data_dir / 'settings.defaults.json'

        self._settings: UnifiedSettings = UnifiedSettings()
        self._change_callbacks: list[Callable[[UnifiedSettings], None]] = []

        # Initialize secure storage
        from .secure_storage import initialize_secure_storage
        self._secure = initialize_secure_storage(data_dir)

        # Load settings
        self._load()

    def _load(self) -> None:
        """Load settings from file."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._settings = UnifiedSettings.from_dict(data)
                logger.info("Loaded unified settings")
            except Exception as e:
                logger.warning(f"Failed to load settings, using defaults: {e}")
                self._settings = UnifiedSettings()
        else:
            logger.info("No settings file found, using defaults")
            self._settings = UnifiedSettings()

    def _save(self) -> None:
        """Save settings to file."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            logger.debug("Saved unified settings")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def _notify_change(self) -> None:
        """Notify callbacks of settings change."""
        for callback in self._change_callbacks:
            try:
                callback(self._settings)
            except Exception as e:
                logger.error(f"Settings change callback error: {e}")

    @property
    def settings(self) -> UnifiedSettings:
        """Get current settings."""
        return self._settings

    def on_change(self, callback: Callable[[UnifiedSettings], None]) -> None:
        """Register a callback for settings changes."""
        self._change_callbacks.append(callback)

    def update(self, updates: dict[str, Any]) -> None:
        """
        Update settings with partial data.

        Args:
            updates: Dictionary of settings to update
        """
        current = self._settings.to_dict()
        self._deep_update(current, updates)
        self._settings = UnifiedSettings.from_dict(current)
        self._save()
        self._notify_change()

    def _deep_update(self, base: dict, updates: dict) -> None:
        """Recursively update nested dictionaries."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = UnifiedSettings.get_defaults()
        self._secure.clear()  # Clear secure storage too
        self._save()
        self._notify_change()
        logger.info("Settings reset to defaults")

    def reset_ha_settings(self) -> None:
        """Reset only HA integration settings to defaults."""
        self._settings.ha_integration = HAIntegrationSettings()
        self._secure.delete('ha_token')
        self._save()
        self._notify_change()
        logger.info("HA integration settings reset")

    def reset_mqtt_settings(self) -> None:
        """Reset only MQTT settings to defaults."""
        self._settings.mqtt = MQTTSettings()
        self._secure.delete('mqtt_password')
        self._save()
        self._notify_change()
        logger.info("MQTT settings reset")

    def reset_local_audio_settings(self) -> None:
        """Reset only local audio settings to defaults."""
        self._settings.local_audio = LocalAudioSettings()
        self._save()
        self._notify_change()
        logger.info("Local audio settings reset")

    # --- Secure value access ---

    def get_ha_token(self) -> str | None:
        """Get HA token from secure storage."""
        return self._secure.get('ha_token')

    def set_ha_token(self, token: str | None) -> None:
        """Set HA token in secure storage."""
        if token:
            self._secure.set('ha_token', token)
        else:
            self._secure.delete('ha_token')

    def get_mqtt_password(self) -> str | None:
        """Get MQTT password from secure storage."""
        return self._secure.get('mqtt_password')

    def set_mqtt_password(self, password: str | None) -> None:
        """Set MQTT password in secure storage."""
        if password:
            self._secure.set('mqtt_password', password)
        else:
            self._secure.delete('mqtt_password')

    # --- Convenience methods ---

    def is_ha_enabled(self) -> bool:
        """Check if HA integration is enabled."""
        return self._settings.ha_integration.enabled

    def is_mqtt_enabled(self) -> bool:
        """Check if MQTT is enabled."""
        return self._settings.mqtt.enabled

    def is_local_audio_enabled(self) -> bool:
        """Check if local audio is enabled."""
        return self._settings.local_audio.enabled

    def get_enabled_audio_devices(self) -> list[str]:
        """Get list of enabled local audio device IDs."""
        return self._settings.local_audio.get_enabled_device_ids()

    def export_for_api(self) -> dict:
        """
        Export settings for API response.

        Hides sensitive values, shows only safe data.
        """
        data = self._settings.to_dict()

        # Indicate presence of secure values without exposing them
        data['ha_integration']['has_token'] = self._secure.has('ha_token')
        data['mqtt']['has_password'] = self._secure.has('mqtt_password')

        return data


# Global instance
_settings_manager: UnifiedSettingsManager | None = None


def get_settings_manager(data_dir: Path | None = None) -> UnifiedSettingsManager:
    """
    Get the global settings manager instance.

    Args:
        data_dir: Data directory (only needed on first call)
    """
    global _settings_manager

    if _settings_manager is None:
        if data_dir is None:
            try:
                from . import runtime
                data_dir = runtime.paths.data
            except Exception:
                data_dir = Path.home() / '.sonorium'

        _settings_manager = UnifiedSettingsManager(data_dir)

    return _settings_manager


def initialize_settings_manager(data_dir: Path) -> UnifiedSettingsManager:
    """
    Initialize settings manager with a specific data directory.

    Call this during app startup.
    """
    global _settings_manager
    _settings_manager = UnifiedSettingsManager(data_dir)
    return _settings_manager


__all__ = [
    'HAIntegrationSettings',
    'MQTTSettings',
    'LocalAudioSettings',
    'UnifiedSettings',
    'UnifiedSettingsManager',
    'get_settings_manager',
    'initialize_settings_manager',
]
