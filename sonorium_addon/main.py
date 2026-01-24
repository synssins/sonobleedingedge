#!/usr/bin/env python3
"""
Sonorium Home Assistant Addon - Main Entry Point.

This is the main entry point for the Home Assistant addon.
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ha.settings import HASettings
from ha.supervisor import SupervisorAPI
from sonorium.core.state import StateManager
from sonorium.core.mqtt import init_mqtt_bridge, stop_mqtt_bridge
from sonorium.models.settings import MQTTSettings
from sonorium.web.app import create_app


async def main():
    """Main entry point for Home Assistant addon."""
    print("Starting Sonorium (Home Assistant Addon)...")

    # Load settings from HA options
    ha_settings = HASettings.load()
    print(f"Loaded settings: port={ha_settings.port}, mqtt_enabled={ha_settings.mqtt.enabled}")

    # Initialize Supervisor API
    supervisor = SupervisorAPI()
    if supervisor.is_available:
        print("Supervisor API available")
        info = await supervisor.get_supervisor_info()
        if info:
            print(f"Supervisor version: {info.get('version', 'unknown')}")
    else:
        print("Supervisor API not available (not running in HA?)")

    # Initialize state manager
    state = StateManager()

    # Initialize MQTT bridge if enabled
    mqtt_bridge = None
    if ha_settings.mqtt.enabled:
        # Convert HA MQTT settings to core MQTTSettings
        mqtt_settings = MQTTSettings(
            enabled=ha_settings.mqtt.enabled,
            host=ha_settings.mqtt.host,
            port=ha_settings.mqtt.port,
            username=ha_settings.mqtt.username,
            password=ha_settings.mqtt.password,
            topic_prefix=ha_settings.mqtt.topic_prefix,
            ha_discovery_prefix=ha_settings.mqtt.discovery_prefix,
        )
        mqtt_bridge = await init_mqtt_bridge(mqtt_settings)
        if mqtt_bridge:
            print(f"MQTT bridge connected to {ha_settings.mqtt.host}:{ha_settings.mqtt.port}")
        else:
            print("MQTT bridge failed to connect")

    # Create FastAPI app
    app = create_app(state)

    # Run with uvicorn
    import uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=ha_settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        # Cleanup
        await stop_mqtt_bridge()
        await supervisor.close()


if __name__ == "__main__":
    asyncio.run(main())
