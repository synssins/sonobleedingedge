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
from sonorium.core.mqtt import MQTTBridge
from sonorium.web.app import create_app


async def main():
    """Main entry point for Home Assistant addon."""
    print("Starting Sonorium (Home Assistant Addon)...")

    # Load settings from HA options
    settings = HASettings.load()
    print(f"Loaded settings: port={settings.port}, mqtt_enabled={settings.mqtt.enabled}")

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
    if settings.mqtt.enabled:
        mqtt_config = {
            "host": settings.mqtt.host,
            "port": settings.mqtt.port,
            "username": settings.mqtt.username,
            "password": settings.mqtt.password,
            "topic_prefix": settings.mqtt.topic_prefix,
        }
        mqtt_bridge = MQTTBridge(state, mqtt_config)
        await mqtt_bridge.start()
        print(f"MQTT bridge connected to {settings.mqtt.host}:{settings.mqtt.port}")

    # Create FastAPI app
    app = create_app(state)

    # Run with uvicorn
    import uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        # Cleanup
        if mqtt_bridge:
            await mqtt_bridge.stop()
        await supervisor.close()


if __name__ == "__main__":
    asyncio.run(main())
