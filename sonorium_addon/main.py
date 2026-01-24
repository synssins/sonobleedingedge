#!/usr/bin/env python3
"""
Sonorium Home Assistant Addon - Main Entry Point.

This is the main entry point for the Home Assistant addon.
Uses the unified core code with HA-specific configuration.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sonorium.web.app import create_ha_addon_app, run_server


async def main():
    """Main entry point for Home Assistant addon."""
    print("Starting Sonorium (Home Assistant Addon)...")

    # Check if MQTT is actually configured (from HA service discovery)
    mqtt_host = os.environ.get("SONORIUM_MQTT_HOST")
    if mqtt_host:
        print(f"MQTT configured: {mqtt_host}:{os.environ.get('SONORIUM_MQTT_PORT', 1883)}")
    else:
        # MQTT not available - disable it by setting host to empty
        # Settings.from_env() will see no host and use default localhost
        # But we should explicitly disable MQTT when not configured
        print("MQTT not configured - running without MQTT integration")
        os.environ["SONORIUM_MQTT_ENABLED"] = "false"

    # Get port from environment (set by ha/settings.py or default to 8008)
    port = int(os.environ.get("SONORIUM_PORT", "8008"))

    # Create the HA addon app using unified core code
    # This handles:
    # - HA-specific paths (/data, /media)
    # - Settings from environment
    # - State manager initialization (in lifespan)
    # - MQTT initialization (in lifespan, after state manager)
    app = create_ha_addon_app()

    print(f"Starting web server on port {port}...")

    # Run the server
    await run_server(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    asyncio.run(main())
