"""
Platform Capabilities Detection

Detects hardware and environment capabilities at startup.
Provides a unified view of what features are available on the current platform.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from sonorium.obs import logger


@dataclass
class AudioDevice:
    """Represents a local audio output device."""
    id: str
    name: str
    channels: int
    sample_rate: float
    is_default: bool
    enabled: bool = False

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'channels': self.channels,
            'sample_rate': self.sample_rate,
            'is_default': self.is_default,
            'enabled': self.enabled,
        }


@dataclass
class HACapabilities:
    """Home Assistant integration capabilities."""
    detected: bool = False           # HA environment detected (addon)
    enabled: bool = False            # User has HA integration enabled
    autodetect: bool = True          # Use auto-detected values
    override: bool = False           # User is overriding auto values

    # Auto-detected or user-provided values
    token: str | None = None
    supervisor_url: str | None = None

    # Connection status
    connected: bool = False
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            'detected': self.detected,
            'enabled': self.enabled,
            'autodetect': self.autodetect,
            'override': self.override,
            'connected': self.connected,
            'has_token': self.token is not None,
            'supervisor_url': self.supervisor_url,
            'last_error': self.last_error,
        }


@dataclass
class MQTTCapabilities:
    """MQTT integration capabilities."""
    detected: bool = False           # MQTT auto-discovered (via HA)
    enabled: bool = False            # User has MQTT enabled
    autodetect: bool = True          # Use auto-detected values
    override: bool = False           # User is overriding auto values

    # Connection settings
    broker: str | None = None
    port: int = 1883
    username: str | None = None
    password: str | None = None      # Stored securely
    discovery_prefix: str = 'homeassistant'

    # Connection status
    connected: bool = False
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            'detected': self.detected,
            'enabled': self.enabled,
            'autodetect': self.autodetect,
            'override': self.override,
            'broker': self.broker,
            'port': self.port,
            'has_credentials': self.username is not None,
            'discovery_prefix': self.discovery_prefix,
            'connected': self.connected,
            'last_error': self.last_error,
        }


@dataclass
class LocalAudioCapabilities:
    """Local audio output capabilities."""
    available: bool = False          # Audio devices detected
    enabled: bool = False            # User has enabled local audio
    devices: list[AudioDevice] = field(default_factory=list)
    detection_error: str | None = None

    def to_dict(self) -> dict:
        return {
            'available': self.available,
            'enabled': self.enabled,
            'device_count': len(self.devices),
            'devices': [d.to_dict() for d in self.devices],
            'reason': None if self.available else (
                self.detection_error or 'No audio output devices detected'
            ),
        }

    def get_enabled_devices(self) -> list[AudioDevice]:
        """Get list of user-enabled audio devices."""
        return [d for d in self.devices if d.enabled]


@dataclass
class PlatformCapabilities:
    """
    Complete platform capabilities.

    Detected at startup and updated as settings change.
    """
    platform: str = 'standalone'     # 'standalone' | 'docker' | 'ha_addon'

    ha: HACapabilities = field(default_factory=HACapabilities)
    mqtt: MQTTCapabilities = field(default_factory=MQTTCapabilities)
    local_audio: LocalAudioCapabilities = field(default_factory=LocalAudioCapabilities)

    # Always-available features
    direct_discovery: bool = True    # mDNS/SSDP always available

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            'platform': self.platform,
            'features': {
                'ha_integration': self.ha.to_dict(),
                'mqtt': self.mqtt.to_dict(),
                'local_audio': self.local_audio.to_dict(),
                'direct_discovery': self.direct_discovery,
                'hybrid_discovery': self.ha.enabled,  # Requires HA
            }
        }


def detect_platform() -> str:
    """Detect current platform."""
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "ha_addon"
    elif os.environ.get("SONORIUM_DOCKER") or os.path.exists("/.dockerenv"):
        return "docker"
    else:
        return "standalone"


def detect_ha_environment() -> HACapabilities:
    """Detect Home Assistant environment and credentials."""
    caps = HACapabilities()

    # Check for HA addon environment
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if supervisor_token:
        caps.detected = True
        caps.token = supervisor_token
        caps.supervisor_url = os.environ.get(
            "SUPERVISOR_URL",
            "http://supervisor/core"
        )
        caps.enabled = True  # Auto-enable when detected
        logger.info("Home Assistant addon environment detected")
    else:
        logger.debug("Not running as Home Assistant addon")

    return caps


def detect_mqtt_from_ha() -> MQTTCapabilities:
    """
    Detect MQTT configuration from Home Assistant Supervisor API.

    Only works when running as HA addon.
    """
    caps = MQTTCapabilities()

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        return caps

    try:
        import requests

        # Query Supervisor for MQTT addon info
        headers = {"Authorization": f"Bearer {supervisor_token}"}
        resp = requests.get(
            "http://supervisor/services/mqtt",
            headers=headers,
            timeout=5
        )

        if resp.status_code == 200:
            data = resp.json().get('data', {})
            if data:
                caps.detected = True
                caps.enabled = True
                caps.broker = data.get('host', 'core-mosquitto')
                caps.port = data.get('port', 1883)
                caps.username = data.get('username')
                caps.password = data.get('password')
                logger.info(f"MQTT auto-discovered: {caps.broker}:{caps.port}")
        else:
            logger.debug(f"MQTT service not available: {resp.status_code}")

    except Exception as e:
        logger.debug(f"Could not auto-detect MQTT: {e}")
        caps.last_error = str(e)

    return caps


def detect_audio_devices() -> LocalAudioCapabilities:
    """Detect available local audio output devices."""
    caps = LocalAudioCapabilities()

    try:
        import sounddevice as sd

        devices = []
        default_output = sd.default.device[1] if sd.default.device else None

        for i, device in enumerate(sd.query_devices()):
            # Only include output devices
            if device['max_output_channels'] > 0:
                devices.append(AudioDevice(
                    id=str(i),
                    name=device['name'],
                    channels=device['max_output_channels'],
                    sample_rate=device['default_samplerate'],
                    is_default=(i == default_output),
                    enabled=False,
                ))

        caps.devices = devices
        caps.available = len(devices) > 0

        if caps.available:
            logger.info(f"Detected {len(devices)} audio output device(s)")
        else:
            logger.info("No audio output devices detected")

    except ImportError:
        caps.detection_error = "sounddevice library not installed"
        logger.warning("sounddevice not available - local audio disabled")
    except Exception as e:
        caps.detection_error = str(e)
        logger.warning(f"Failed to detect audio devices: {e}")

    return caps


def detect_all_capabilities() -> PlatformCapabilities:
    """
    Detect all platform capabilities at startup.

    Returns a PlatformCapabilities object with all detected features.
    """
    caps = PlatformCapabilities()

    # Detect platform
    caps.platform = detect_platform()
    logger.info(f"Platform detected: {caps.platform}")

    # Detect HA environment
    caps.ha = detect_ha_environment()

    # Detect MQTT (if HA detected)
    if caps.ha.detected:
        caps.mqtt = detect_mqtt_from_ha()

    # Detect local audio
    caps.local_audio = detect_audio_devices()

    return caps


# Global capabilities instance - initialized at startup
_capabilities: PlatformCapabilities | None = None


def get_capabilities() -> PlatformCapabilities:
    """Get the global capabilities instance."""
    global _capabilities
    if _capabilities is None:
        _capabilities = detect_all_capabilities()
    return _capabilities


def refresh_capabilities() -> PlatformCapabilities:
    """Re-detect capabilities (e.g., after settings change)."""
    global _capabilities
    _capabilities = detect_all_capabilities()
    return _capabilities


def update_capabilities_from_settings(settings: dict[str, Any]) -> None:
    """
    Update capabilities based on user settings.

    Called when settings are loaded or changed.
    """
    caps = get_capabilities()

    # Update HA settings
    ha_settings = settings.get('ha_integration', {})
    caps.ha.autodetect = ha_settings.get('autodetect', True)
    caps.ha.override = ha_settings.get('override', False)
    caps.ha.enabled = ha_settings.get('enabled', caps.ha.detected)

    if caps.ha.override:
        # Use user-provided values
        caps.ha.token = ha_settings.get('token') or caps.ha.token
        caps.ha.supervisor_url = ha_settings.get('supervisor_url') or caps.ha.supervisor_url

    # Update MQTT settings
    mqtt_settings = settings.get('mqtt', {})
    caps.mqtt.autodetect = mqtt_settings.get('autodetect', True)
    caps.mqtt.override = mqtt_settings.get('override', False)
    caps.mqtt.enabled = mqtt_settings.get('enabled', caps.mqtt.detected)

    if caps.mqtt.override:
        # Use user-provided values
        caps.mqtt.broker = mqtt_settings.get('broker') or caps.mqtt.broker
        caps.mqtt.port = mqtt_settings.get('port', caps.mqtt.port)
        caps.mqtt.username = mqtt_settings.get('username') or caps.mqtt.username
        caps.mqtt.password = mqtt_settings.get('password') or caps.mqtt.password
        caps.mqtt.discovery_prefix = mqtt_settings.get(
            'discovery_prefix', caps.mqtt.discovery_prefix
        )

    # Update local audio settings
    audio_settings = settings.get('local_audio', {})
    caps.local_audio.enabled = audio_settings.get('enabled', False)

    # Update individual device enabled states
    device_settings = audio_settings.get('devices', {})
    for device in caps.local_audio.devices:
        device.enabled = device_settings.get(device.id, {}).get('enabled', False)


__all__ = [
    'AudioDevice',
    'HACapabilities',
    'MQTTCapabilities',
    'LocalAudioCapabilities',
    'PlatformCapabilities',
    'detect_platform',
    'detect_all_capabilities',
    'get_capabilities',
    'refresh_capabilities',
    'update_capabilities_from_settings',
]
