"""
Unified API for Sonorium

Single API file that works across all platforms with conditional
endpoint registration based on detected capabilities.

This replaces both web_api.py (standalone) and api_v2.py (shared).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Body, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from sonorium.obs import logger

if TYPE_CHECKING:
    from sonorium.platform.capabilities import PlatformCapabilities
    from sonorium.platform.unified_settings import UnifiedSettingsManager
    from sonorium.plugins.manager import PluginManager


# =============================================================================
# Pydantic Models
# =============================================================================

class HAIntegrationUpdate(BaseModel):
    """Update HA integration settings."""
    enabled: Optional[bool] = None
    autodetect: Optional[bool] = None
    override: Optional[bool] = None
    token: Optional[str] = None
    supervisor_url: Optional[str] = None


class MQTTSettingsUpdate(BaseModel):
    """Update MQTT settings."""
    enabled: Optional[bool] = None
    autodetect: Optional[bool] = None
    override: Optional[bool] = None
    broker: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    discovery_prefix: Optional[str] = None


class LocalAudioUpdate(BaseModel):
    """Update local audio settings."""
    enabled: Optional[bool] = None


class AudioDeviceUpdate(BaseModel):
    """Update a specific audio device."""
    enabled: bool


# =============================================================================
# Global State (set during initialization)
# =============================================================================

_capabilities: 'PlatformCapabilities | None' = None
_settings_manager: 'UnifiedSettingsManager | None' = None
_plugin_manager: 'PluginManager | None' = None
_app_instance: Any = None  # SonoriumApp or equivalent
_mqtt_client: Any = None   # MQTT client if connected
_ha_registry: Any = None   # HA registry client if connected


def set_capabilities(caps: 'PlatformCapabilities') -> None:
    """Set the global capabilities instance."""
    global _capabilities
    _capabilities = caps


def set_settings_manager(manager: 'UnifiedSettingsManager') -> None:
    """Set the global settings manager."""
    global _settings_manager
    _settings_manager = manager


def set_plugin_manager(manager: 'PluginManager') -> None:
    """Set the global plugin manager."""
    global _plugin_manager
    _plugin_manager = manager


def set_app_instance(app: Any) -> None:
    """Set the main application instance."""
    global _app_instance
    _app_instance = app


def set_mqtt_client(client: Any) -> None:
    """Set the MQTT client."""
    global _mqtt_client
    _mqtt_client = client


def set_ha_registry(registry: Any) -> None:
    """Set the HA registry client."""
    global _ha_registry
    _ha_registry = registry


# =============================================================================
# API Factory
# =============================================================================

def create_unified_app(
    capabilities: 'PlatformCapabilities',
    settings_manager: 'UnifiedSettingsManager',
    app_instance: Any = None,
    plugin_manager: 'PluginManager | None' = None,
    static_dir: Path | None = None,
    templates_dir: Path | None = None,
) -> FastAPI:
    """
    Create the unified FastAPI application.

    Args:
        capabilities: Detected platform capabilities
        settings_manager: Unified settings manager
        app_instance: Main application instance (SonoriumApp)
        plugin_manager: Plugin manager instance
        static_dir: Path to static files
        templates_dir: Path to templates

    Returns:
        Configured FastAPI application
    """
    # Store globals
    set_capabilities(capabilities)
    set_settings_manager(settings_manager)
    set_app_instance(app_instance)
    if plugin_manager:
        set_plugin_manager(plugin_manager)

    # Create app
    app = FastAPI(
        title="Sonorium",
        description="Multi-zone ambient soundscape mixer",
        version="1.0.0",
    )

    # Register endpoint groups
    register_capabilities_endpoints(app)
    register_settings_endpoints(app)
    register_plugin_catalog_endpoints(app)

    # Conditional registration based on capabilities
    if capabilities.local_audio.available:
        register_local_audio_endpoints(app)

    if capabilities.ha.enabled:
        register_ha_specific_endpoints(app)

    # Always register logs endpoints
    register_logs_endpoints(app)

    # Mount static files if provided
    if static_dir and static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    logger.info(f"Unified API created for platform: {capabilities.platform}")

    return app


# =============================================================================
# Capabilities Endpoints
# =============================================================================

def register_capabilities_endpoints(app: FastAPI) -> None:
    """Register platform capabilities endpoints."""

    @app.get('/api/capabilities')
    async def get_capabilities() -> dict:
        """
        Get platform capabilities for frontend adaptation.

        Returns detected capabilities, feature availability, and status.
        The frontend uses this to show/hide features and adapt the UI.
        """
        if not _capabilities:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Capabilities not initialized"
            )
        return _capabilities.to_dict()

    @app.post('/api/capabilities/refresh')
    async def refresh_capabilities() -> dict:
        """
        Re-detect platform capabilities.

        Useful after hardware changes (e.g., plugging in audio device).
        """
        from sonorium.platform.capabilities import refresh_capabilities as do_refresh
        global _capabilities
        _capabilities = do_refresh()
        return _capabilities.to_dict()


# =============================================================================
# Settings Endpoints
# =============================================================================

def register_settings_endpoints(app: FastAPI) -> None:
    """Register unified settings endpoints."""

    # --- General Settings ---

    @app.get('/api/settings/unified')
    async def get_unified_settings() -> dict:
        """Get all unified settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )
        return _settings_manager.export_for_api()

    @app.post('/api/settings/reset')
    async def reset_all_settings() -> dict:
        """Reset all settings to defaults."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )
        _settings_manager.reset_to_defaults()
        return {'status': 'ok', 'message': 'All settings reset to defaults'}

    # --- Home Assistant Integration ---

    @app.get('/api/settings/ha')
    async def get_ha_settings() -> dict:
        """Get Home Assistant integration settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        settings = _settings_manager.settings.ha_integration.to_dict()

        # Add detection status from capabilities
        if _capabilities:
            settings['detected'] = _capabilities.ha.detected
            settings['connected'] = _capabilities.ha.connected

        # Indicate if token is set (without exposing it)
        settings['has_token'] = _settings_manager._secure.has('ha_token')

        return settings

    @app.put('/api/settings/ha')
    async def update_ha_settings(update: HAIntegrationUpdate) -> dict:
        """Update Home Assistant integration settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        # Build update dict
        updates = {'ha_integration': {}}

        if update.enabled is not None:
            updates['ha_integration']['enabled'] = update.enabled
        if update.autodetect is not None:
            updates['ha_integration']['autodetect'] = update.autodetect
        if update.override is not None:
            updates['ha_integration']['override'] = update.override
        if update.supervisor_url is not None:
            updates['ha_integration']['supervisor_url'] = update.supervisor_url

        # Handle token separately (secure storage)
        if update.token is not None:
            _settings_manager.set_ha_token(update.token if update.token else None)

        if updates['ha_integration']:
            _settings_manager.update(updates)

        # Update capabilities with new settings
        if _capabilities:
            from sonorium.platform.capabilities import update_capabilities_from_settings
            update_capabilities_from_settings(_settings_manager.settings.to_dict())

        return {'status': 'ok'}

    @app.post('/api/settings/ha/reset')
    async def reset_ha_settings() -> dict:
        """Reset HA integration settings to defaults."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )
        _settings_manager.reset_ha_settings()
        return {'status': 'ok', 'message': 'HA integration settings reset'}

    @app.post('/api/settings/ha/test')
    async def test_ha_connection() -> dict:
        """Test Home Assistant connection with current settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        settings = _settings_manager.settings.ha_integration
        token = _settings_manager.get_ha_token()

        if not settings.enabled:
            return {'status': 'error', 'message': 'HA integration not enabled'}

        if not token:
            return {'status': 'error', 'message': 'No HA token configured'}

        # Test connection
        try:
            import aiohttp
            url = settings.supervisor_url or 'http://supervisor/core'
            headers = {'Authorization': f'Bearer {token}'}

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{url}/api/config',
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'status': 'ok',
                            'message': 'Connected to Home Assistant',
                            'ha_version': data.get('version'),
                            'location_name': data.get('location_name'),
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'HA returned status {resp.status}'
                        }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    # --- MQTT Settings ---

    @app.get('/api/settings/mqtt')
    async def get_mqtt_settings() -> dict:
        """Get MQTT broker settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        settings = _settings_manager.settings.mqtt.to_dict()

        # Add detection/connection status
        if _capabilities:
            settings['detected'] = _capabilities.mqtt.detected
            settings['connected'] = _capabilities.mqtt.connected

        # Indicate if password is set
        settings['has_password'] = _settings_manager._secure.has('mqtt_password')

        return settings

    @app.put('/api/settings/mqtt')
    async def update_mqtt_settings(update: MQTTSettingsUpdate) -> dict:
        """Update MQTT broker settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        updates = {'mqtt': {}}

        if update.enabled is not None:
            updates['mqtt']['enabled'] = update.enabled
        if update.autodetect is not None:
            updates['mqtt']['autodetect'] = update.autodetect
        if update.override is not None:
            updates['mqtt']['override'] = update.override
        if update.broker is not None:
            updates['mqtt']['broker'] = update.broker
        if update.port is not None:
            updates['mqtt']['port'] = update.port
        if update.username is not None:
            updates['mqtt']['username'] = update.username
        if update.discovery_prefix is not None:
            updates['mqtt']['discovery_prefix'] = update.discovery_prefix

        # Handle password separately (secure storage)
        if update.password is not None:
            _settings_manager.set_mqtt_password(update.password if update.password else None)

        if updates['mqtt']:
            _settings_manager.update(updates)

        # Update capabilities
        if _capabilities:
            from sonorium.platform.capabilities import update_capabilities_from_settings
            update_capabilities_from_settings(_settings_manager.settings.to_dict())

        return {'status': 'ok'}

    @app.post('/api/settings/mqtt/reset')
    async def reset_mqtt_settings() -> dict:
        """Reset MQTT settings to defaults."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )
        _settings_manager.reset_mqtt_settings()
        return {'status': 'ok', 'message': 'MQTT settings reset'}

    @app.post('/api/settings/mqtt/test')
    async def test_mqtt_connection() -> dict:
        """Test MQTT broker connection with current settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        settings = _settings_manager.settings.mqtt

        if not settings.enabled:
            return {'status': 'error', 'message': 'MQTT not enabled'}

        if not settings.broker:
            return {'status': 'error', 'message': 'No MQTT broker configured'}

        # Test connection
        try:
            import paho.mqtt.client as mqtt

            result = {'status': 'pending'}

            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    result['status'] = 'ok'
                    result['message'] = 'Connected to MQTT broker'
                else:
                    result['status'] = 'error'
                    result['message'] = f'Connection failed with code {rc}'
                client.disconnect()

            client = mqtt.Client()

            if settings.username:
                password = _settings_manager.get_mqtt_password()
                client.username_pw_set(settings.username, password)

            client.on_connect = on_connect

            # Connect with timeout
            client.connect_async(settings.broker, settings.port)
            client.loop_start()

            # Wait for result
            for _ in range(50):  # 5 second timeout
                if result['status'] != 'pending':
                    break
                await asyncio.sleep(0.1)

            client.loop_stop()

            if result['status'] == 'pending':
                return {'status': 'error', 'message': 'Connection timeout'}

            return result

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    # --- Local Audio Settings ---

    @app.get('/api/settings/local-audio')
    async def get_local_audio_settings() -> dict:
        """Get local audio settings and available devices."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        result = _settings_manager.settings.local_audio.to_dict()

        # Add capability info
        if _capabilities:
            result['available'] = _capabilities.local_audio.available
            result['detected_devices'] = [
                d.to_dict() for d in _capabilities.local_audio.devices
            ]
            result['reason'] = (
                None if _capabilities.local_audio.available
                else _capabilities.local_audio.detection_error or 'No audio devices detected'
            )

        return result

    @app.put('/api/settings/local-audio')
    async def update_local_audio_settings(update: LocalAudioUpdate) -> dict:
        """Update local audio master settings."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        # Check if local audio is available
        if update.enabled and _capabilities and not _capabilities.local_audio.available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enable local audio: no devices available"
            )

        updates = {'local_audio': {}}
        if update.enabled is not None:
            updates['local_audio']['enabled'] = update.enabled

        _settings_manager.update(updates)

        # Update capabilities
        if _capabilities:
            from sonorium.platform.capabilities import update_capabilities_from_settings
            update_capabilities_from_settings(_settings_manager.settings.to_dict())

        return {'status': 'ok'}

    @app.post('/api/settings/local-audio/reset')
    async def reset_local_audio_settings() -> dict:
        """Reset local audio settings to defaults."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )
        _settings_manager.reset_local_audio_settings()
        return {'status': 'ok', 'message': 'Local audio settings reset'}


# =============================================================================
# Local Audio Device Endpoints
# =============================================================================

def register_local_audio_endpoints(app: FastAPI) -> None:
    """Register local audio device management endpoints."""

    @app.get('/api/local-audio/devices')
    async def get_audio_devices() -> dict:
        """Get all detected local audio output devices."""
        if not _capabilities:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Capabilities not initialized"
            )

        return {
            'available': _capabilities.local_audio.available,
            'devices': [d.to_dict() for d in _capabilities.local_audio.devices],
        }

    @app.put('/api/local-audio/devices/{device_id}')
    async def update_audio_device(device_id: str, update: AudioDeviceUpdate) -> dict:
        """Enable or disable a specific audio device."""
        if not _settings_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Settings manager not initialized"
            )

        if not _capabilities:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Capabilities not initialized"
            )

        # Find the device
        device = None
        for d in _capabilities.local_audio.devices:
            if d.id == device_id:
                device = d
                break

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio device '{device_id}' not found"
            )

        # Update settings
        _settings_manager.settings.local_audio.set_device_enabled(
            device_id, update.enabled, device.name
        )
        _settings_manager._save()

        # Update capability object
        device.enabled = update.enabled

        return {'status': 'ok', 'device_id': device_id, 'enabled': update.enabled}

    @app.post('/api/local-audio/refresh')
    async def refresh_audio_devices() -> dict:
        """Re-scan for audio devices."""
        if not _capabilities:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Capabilities not initialized"
            )

        from sonorium.platform.capabilities import detect_audio_devices

        # Re-detect devices
        _capabilities.local_audio = detect_audio_devices()

        # Re-apply enabled states from settings
        if _settings_manager:
            device_settings = _settings_manager.settings.local_audio.devices
            for device in _capabilities.local_audio.devices:
                device.enabled = device_settings.get(device.id, {}).get('enabled', False)

        return {
            'available': _capabilities.local_audio.available,
            'devices': [d.to_dict() for d in _capabilities.local_audio.devices],
        }


# =============================================================================
# Plugin Catalog Endpoints
# =============================================================================

def register_plugin_catalog_endpoints(app: FastAPI) -> None:
    """Register plugin catalog endpoints."""

    _catalog_cache: dict = {'data': None, 'timestamp': 0}
    CATALOG_CACHE_TTL = 3600  # 1 hour

    @app.get('/api/plugins/catalog')
    async def get_plugin_catalog() -> dict:
        """Fetch available plugins from the GitHub catalog."""
        import time
        import aiohttp

        now = time.time()

        if _catalog_cache['data'] and (now - _catalog_cache['timestamp']) < CATALOG_CACHE_TTL:
            catalog = _catalog_cache['data']
        else:
            catalog_url = 'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/catalog.json'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(catalog_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f'Failed to fetch catalog: HTTP {resp.status}'
                            )
                        catalog = await resp.json(content_type=None)
                        _catalog_cache['data'] = catalog
                        _catalog_cache['timestamp'] = now
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f'Failed to fetch plugin catalog: {e}')
                if _catalog_cache['data']:
                    catalog = _catalog_cache['data']
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f'Failed to fetch catalog: {e}'
                    )

        # Enrich with installed status
        installed_plugins = {}
        if _plugin_manager:
            for plugin in _plugin_manager.plugins.values():
                installed_plugins[plugin.id] = plugin.version

        enriched_plugins = []
        for plugin in catalog.get('plugins', []):
            plugin_copy = dict(plugin)
            pid = plugin.get('id')
            if pid in installed_plugins:
                plugin_copy['installed'] = True
                plugin_copy['installed_version'] = installed_plugins[pid]
                plugin_copy['update_available'] = plugin.get('version') != installed_plugins[pid]
            else:
                plugin_copy['installed'] = False
                plugin_copy['installed_version'] = None
                plugin_copy['update_available'] = False
            enriched_plugins.append(plugin_copy)

        return {
            'version': catalog.get('version', 1),
            'updated': catalog.get('updated'),
            'plugins': enriched_plugins
        }

    @app.post('/api/plugins/install-from-catalog')
    async def install_plugin_from_catalog(request: Request) -> dict:
        """Download and install a plugin from the GitHub catalog."""
        import aiohttp
        import zipfile
        import io
        import shutil

        if not _plugin_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='Plugin system not initialized'
            )

        body = await request.json()
        plugin_id = body.get('plugin_id')
        if not plugin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='plugin_id is required'
            )

        # Fetch catalog
        catalog_url = 'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/catalog.json'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(catalog_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail='Failed to fetch catalog'
                        )
                    catalog = await resp.json(content_type=None)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Failed to fetch catalog: {e}'
            )

        # Find plugin
        plugin_info = None
        for p in catalog.get('plugins', []):
            if p.get('id') == plugin_id:
                plugin_info = p
                break

        if not plugin_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Plugin "{plugin_id}" not found in catalog'
            )

        # Download ZIP
        zip_filename = plugin_info.get('zip_file')
        if not zip_filename:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Plugin has no zip_file specified'
            )

        zip_url = f'https://raw.githubusercontent.com/synssins/sonobleedingedge/main/plugins/{zip_filename}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(zip_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f'Failed to download plugin: HTTP {resp.status}'
                        )
                    content = await resp.read()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Failed to download plugin: {e}'
            )

        # Install
        try:
            zip_buffer = io.BytesIO(content)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                file_list = zf.namelist()
                plugin_py_paths = [f for f in file_list if f.endswith('plugin.py')]
                if not plugin_py_paths:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='No plugin.py found in ZIP'
                    )

                plugin_py = plugin_py_paths[0]
                plugin_dir_name = plugin_py.rsplit('/', 1)[0] if '/' in plugin_py else ''
                target_dir = _plugin_manager.plugins_dir / plugin_id

                if target_dir.exists():
                    shutil.rmtree(target_dir)

                target_dir.mkdir(parents=True, exist_ok=True)
                for member in zf.namelist():
                    if plugin_dir_name and member.startswith(plugin_dir_name + '/'):
                        target_path = target_dir / member[len(plugin_dir_name) + 1:]
                    elif plugin_dir_name and member == plugin_dir_name:
                        continue
                    else:
                        target_path = target_dir / member

                    if member.endswith('/'):
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target_path, 'wb') as dst:
                            dst.write(src.read())

            # Update manifest with category
            manifest_path = target_dir / 'manifest.json'
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    if plugin_info.get('category') and not manifest.get('category'):
                        manifest['category'] = plugin_info['category']
                        with open(manifest_path, 'w') as f:
                            json.dump(manifest, f, indent=2)
                except Exception as e:
                    logger.warning(f"Could not update manifest: {e}")

            # Reload plugins
            await _plugin_manager.reload_plugins()

            return {
                'status': 'ok',
                'plugin_id': plugin_id,
                'name': plugin_info.get('name', plugin_id),
                'version': plugin_info.get('version'),
                'message': f'Plugin "{plugin_info.get("name", plugin_id)}" installed'
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f'Failed to install plugin: {e}')
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Failed to install plugin: {e}'
            )


# =============================================================================
# HA-Specific Endpoints (only registered when HA is enabled)
# =============================================================================

def register_ha_specific_endpoints(app: FastAPI) -> None:
    """Register Home Assistant-specific endpoints."""

    @app.post('/api/speakers/refresh-ha')
    async def refresh_speakers_from_ha() -> dict:
        """Refresh speaker list from Home Assistant registry."""
        if not _ha_registry:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='HA registry not available'
            )

        try:
            speakers = await _ha_registry.refresh()
            return {
                'status': 'ok',
                'speaker_count': len(speakers),
                'speakers': [s.to_dict() for s in speakers]
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f'Failed to refresh from HA: {e}'
            )


# =============================================================================
# Internal Logs Endpoints
# =============================================================================

def register_logs_endpoints(app: FastAPI) -> None:
    """Register internal logs endpoints for Status page."""

    @app.get('/api/logs')
    async def get_logs(
        category: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 50
    ) -> dict:
        """
        Get internal logs for the Status page.

        Args:
            category: Filter by category (core, discovery, playback, plugins, ha, mqtt, api)
            level: Filter by minimum level (debug, info, warning, error)
            limit: Maximum entries to return (default 50)

        Returns:
            List of log entries, newest first
        """
        from sonorium.core.log_collector import get_log_collector

        log_collector = get_log_collector()
        logs = log_collector.get_logs(category=category, level=level, limit=limit)

        return {
            "status": "ok",
            "count": len(logs),
            "logs": logs
        }

    @app.get('/api/logs/categories')
    async def get_log_categories() -> dict:
        """Get list of log categories with entry counts."""
        from sonorium.core.log_collector import get_log_collector

        log_collector = get_log_collector()
        categories = log_collector.get_categories()

        return {
            "status": "ok",
            "categories": categories
        }

    @app.delete('/api/logs')
    async def clear_logs(category: Optional[str] = None) -> dict:
        """Clear logs, optionally for a specific category."""
        from sonorium.core.log_collector import get_log_collector

        log_collector = get_log_collector()
        log_collector.clear(category=category)

        return {
            "status": "ok",
            "message": f"Logs cleared" + (f" for category '{category}'" if category else "")
        }


# =============================================================================
# Integration with Existing API
# =============================================================================

def add_unified_endpoints_to_app(
    app: FastAPI,
    capabilities: 'PlatformCapabilities',
    settings_manager: 'UnifiedSettingsManager',
    plugin_manager: 'PluginManager | None' = None,
) -> FastAPI:
    """
    Add unified settings/capabilities endpoints to an existing FastAPI app.

    This allows incremental migration - the existing web_api.py endpoints
    continue to work while new capabilities are added.

    Args:
        app: Existing FastAPI application
        capabilities: Detected platform capabilities
        settings_manager: Unified settings manager
        plugin_manager: Plugin manager (optional)

    Returns:
        The same FastAPI app with new endpoints added
    """
    # Store globals
    set_capabilities(capabilities)
    set_settings_manager(settings_manager)
    if plugin_manager:
        set_plugin_manager(plugin_manager)

    # Register new endpoint groups
    register_capabilities_endpoints(app)
    register_settings_endpoints(app)

    # Only register these if not already present (avoid duplicates)
    # Check if plugin catalog endpoints exist
    existing_routes = {r.path for r in app.routes}

    if '/api/plugins/catalog' not in existing_routes:
        register_plugin_catalog_endpoints(app)

    if capabilities.local_audio.available:
        if '/api/local-audio/devices' not in existing_routes:
            register_local_audio_endpoints(app)

    if capabilities.ha.enabled:
        if '/api/speakers/refresh-ha' not in existing_routes:
            register_ha_specific_endpoints(app)

    # Always register logs endpoints
    if '/api/logs' not in existing_routes:
        register_logs_endpoints(app)

    logger.info(f"Unified endpoints added to app (platform: {capabilities.platform})")

    return app


def create_standalone_app(
    app_instance: Any,
    data_dir: Path,
    static_dir: Path | None = None,
    templates_dir: Path | None = None,
    plugin_manager: 'PluginManager | None' = None,
) -> FastAPI:
    """
    Create a complete standalone application with unified API.

    This combines the existing web_api.py functionality with the new
    unified settings and capabilities system.

    Args:
        app_instance: SonoriumApp instance
        data_dir: Data directory for settings
        static_dir: Path to static files
        templates_dir: Path to templates
        plugin_manager: Plugin manager instance (optional)

    Returns:
        Configured FastAPI application
    """
    from sonorium.platform.capabilities import detect_all_capabilities, update_capabilities_from_settings
    from sonorium.platform.unified_settings import initialize_settings_manager

    # Initialize platform systems
    capabilities = detect_all_capabilities()
    settings_manager = initialize_settings_manager(data_dir)

    # Update capabilities with user settings
    update_capabilities_from_settings(settings_manager.settings.to_dict())

    # Store globals
    set_capabilities(capabilities)
    set_settings_manager(settings_manager)
    set_app_instance(app_instance)
    if plugin_manager:
        set_plugin_manager(plugin_manager)

    # Import and use existing web_api create_app
    # This preserves all existing functionality
    try:
        from sonorium.web_api import create_app as create_legacy_app
        from sonorium.web_api import set_plugin_manager as set_legacy_plugin_manager

        # Set plugin manager on legacy web_api for existing plugin endpoints
        if plugin_manager:
            set_legacy_plugin_manager(plugin_manager)

        # Create the base app with all existing endpoints
        fastapi_app = create_legacy_app(app_instance)

        # Add unified endpoints
        add_unified_endpoints_to_app(
            fastapi_app,
            capabilities,
            settings_manager,
            plugin_manager,
        )

        logger.info("Created standalone app with unified API")
        return fastapi_app

    except ImportError as e:
        logger.warning(f"Could not import legacy web_api: {e}")
        # Fall back to pure unified app
        return create_unified_app(
            capabilities,
            settings_manager,
            app_instance,
            static_dir=static_dir,
            templates_dir=templates_dir,
        )


def create_ha_addon_app(
    state_manager: Any,
    data_dir: Path,
    static_dir: Path | None = None,
    templates_dir: Path | None = None,
    plugin_manager: 'PluginManager | None' = None,
) -> FastAPI:
    """
    Create a complete HA addon application with unified API.

    Args:
        state_manager: HA addon state manager
        data_dir: Data directory for settings
        static_dir: Path to static files
        templates_dir: Path to templates
        plugin_manager: Plugin manager

    Returns:
        Configured FastAPI application
    """
    from sonorium.platform.capabilities import detect_all_capabilities, update_capabilities_from_settings
    from sonorium.platform.unified_settings import initialize_settings_manager

    # Initialize platform systems
    capabilities = detect_all_capabilities()
    settings_manager = initialize_settings_manager(data_dir)

    # Update capabilities with user settings
    update_capabilities_from_settings(settings_manager.settings.to_dict())

    # Store globals
    set_capabilities(capabilities)
    set_settings_manager(settings_manager)
    if plugin_manager:
        set_plugin_manager(plugin_manager)

    # Try to import and extend the existing HA API
    try:
        # The HA addon may have its own app creation
        from sonorium.web.app import SonoriumWebApp

        web_app = SonoriumWebApp(
            state_manager=state_manager,
            plugin_manager=plugin_manager,
        )
        fastapi_app = web_app.app

        # Add unified endpoints
        add_unified_endpoints_to_app(
            fastapi_app,
            capabilities,
            settings_manager,
            plugin_manager,
        )

        logger.info("Created HA addon app with unified API")
        return fastapi_app

    except ImportError as e:
        logger.warning(f"Could not import HA web app: {e}")
        # Fall back to pure unified app
        return create_unified_app(
            capabilities,
            settings_manager,
            plugin_manager=plugin_manager,
            static_dir=static_dir,
            templates_dir=templates_dir,
        )


# =============================================================================
# Export
# =============================================================================

__all__ = [
    'create_unified_app',
    'create_standalone_app',
    'create_ha_addon_app',
    'add_unified_endpoints_to_app',
    'set_capabilities',
    'set_settings_manager',
    'set_plugin_manager',
    'set_app_instance',
    'set_mqtt_client',
    'set_ha_registry',
]
