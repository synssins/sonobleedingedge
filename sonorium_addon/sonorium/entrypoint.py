"""
Sonorium Entry Point

Main entry point for the Home Assistant addon.
Initializes all components and starts the uvicorn server.

ADDON CODE: This is specific to the Home Assistant addon deployment.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys


def main():
    """Main entry point."""
    try:
        asyncio.run(run_async())
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"FATAL: Failed to start Sonorium: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def run_async():
    """Async main function."""
    import uvicorn

    from sonorium.obs import logger
    from sonorium.version import __version__
    from sonorium.settings import settings

    # Configure logging
    log_level = os.environ.get("SONORIUM_LOG_LEVEL", "info").lower()
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    level = log_level_map.get(log_level, logging.INFO)
    logging.basicConfig(level=level)
    logging.getLogger("sonorium").setLevel(level)
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)

    # Keep access logs quieter unless in debug mode
    if level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger.info(f"Starting Sonorium {__version__}")
    logger.info(f"Server port: {settings.port}")
    logger.info(f"Log level: {log_level}")

    # Create the FastAPI application
    from sonorium.web.app import SonoriumApp

    sonorium_app = SonoriumApp(mqtt_client=None)

    # Initialize v2 components (sessions, groups, HA integration)
    try:
        sonorium_app.initialize_v2(settings)
        logger.info("Sonorium v2 components initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize v2 components: {e}")
        import traceback
        traceback.print_exc()

    # Initialize MQTT entities if available
    await _initialize_mqtt(sonorium_app)

    # Start the uvicorn server
    config = uvicorn.Config(
        app=sonorium_app.app,
        host="0.0.0.0",
        port=settings.port,
        log_level=log_level,
        access_log=True,
        lifespan="on",
    )
    server = uvicorn.Server(config)

    logger.info(f"Starting uvicorn server on 0.0.0.0:{settings.port}")
    await server.serve()


async def _initialize_mqtt(sonorium_app):
    """Initialize MQTT connection and entity manager."""
    from sonorium.obs import logger

    try:
        from sonorium.settings import settings

        # Check if MQTT is configured
        mqtt_enabled = settings.mqtt.enabled if hasattr(settings, 'mqtt') else True
        if not mqtt_enabled:
            logger.info("MQTT disabled in settings, skipping MQTT initialization")
            return

        # Try to get MQTT configuration
        mqtt_host = None
        mqtt_port = 1883
        mqtt_username = None
        mqtt_password = None

        if hasattr(settings, 'mqtt'):
            mqtt_host = settings.mqtt.host
            mqtt_port = settings.mqtt.port
            mqtt_username = settings.mqtt.username
            mqtt_password = settings.mqtt.password
        else:
            # Try to get from environment
            mqtt_host = os.environ.get("MQTT_HOST")
            mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
            mqtt_username = os.environ.get("MQTT_USERNAME")
            mqtt_password = os.environ.get("MQTT_PASSWORD")

        # Try to auto-detect from Supervisor API if not configured
        if not mqtt_host or mqtt_host == "auto":
            mqtt_host, mqtt_port, mqtt_username, mqtt_password = await _get_mqtt_from_supervisor()

        if not mqtt_host:
            logger.info("MQTT not configured, skipping MQTT initialization")
            return

        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}")

        # Create MQTT client
        import paho.mqtt.client as mqtt

        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        if mqtt_username and mqtt_password:
            mqtt_client.username_pw_set(mqtt_username, mqtt_password)

        # Connection callback
        connected = asyncio.Event()

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                logger.info("MQTT connected successfully")
                connected.set()
            else:
                logger.error(f"MQTT connection failed: {reason_code}")

        mqtt_client.on_connect = on_connect

        # Connect asynchronously
        mqtt_client.connect_async(mqtt_host, mqtt_port)
        mqtt_client.loop_start()

        # Wait for connection with timeout
        try:
            await asyncio.wait_for(connected.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(f"MQTT connection timeout, continuing without MQTT")
            mqtt_client.loop_stop()
            return

        # Initialize MQTT entity manager if we have the required components
        if sonorium_app.state_store and sonorium_app.session_manager:
            try:
                from sonorium.ha.mqtt_entities import SonoriumMQTTManager

                mqtt_manager = SonoriumMQTTManager(
                    state_store=sonorium_app.state_store,
                    session_manager=sonorium_app.session_manager,
                    mqtt_client=mqtt_client,
                    entity_prefix="sonorium",
                )

                # Initialize MQTT entities
                await mqtt_manager.initialize()

                # Set up message handling
                def on_message(client, userdata, message):
                    topic = message.topic
                    payload = message.payload.decode('utf-8', errors='replace')
                    asyncio.create_task(mqtt_manager.handle_command(topic, payload))

                mqtt_client.on_message = on_message

                logger.info("MQTT entity manager initialized")

            except Exception as e:
                logger.warning(f"Failed to initialize MQTT entity manager: {e}")
                import traceback
                traceback.print_exc()

    except Exception as e:
        logger.warning(f"Failed to initialize MQTT: {e}")
        import traceback
        traceback.print_exc()


async def _get_mqtt_from_supervisor():
    """Try to get MQTT configuration from HA Supervisor API."""
    import os
    import json
    import urllib.request

    from sonorium.obs import logger

    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None, 1883, None, None

    try:
        url = "http://supervisor/services/mqtt"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            response_json = json.loads(response.read().decode())

        data = response_json.get("data", response_json)

        if isinstance(data, dict) and data.get('host'):
            return (
                data.get('host'),
                data.get('port', 1883),
                data.get('username'),
                data.get('password'),
            )
    except Exception as e:
        logger.debug(f"Could not get MQTT from Supervisor: {e}")

    return None, 1883, None, None


if __name__ == "__main__":
    main()
