"""
Home Assistant Specific Utilities

Functions that interact with Home Assistant APIs.
These are NOT available in standalone or Docker deployments.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from sonorium.obs import logger


def call_ha_service(
    domain: str,
    service: str,
    service_data: dict,
    timeout: float = 5.0
) -> Optional[Any]:
    """
    Call a Home Assistant service using the Supervisor REST API.

    Args:
        domain: Service domain (e.g., "media_player", "light")
        service: Service name (e.g., "play_media", "turn_on")
        service_data: Service call data (entity_id, etc.)
        timeout: Request timeout in seconds

    Returns:
        Response JSON if available, None otherwise

    Example:
        call_ha_service("media_player", "play_media", {
            "entity_id": "media_player.living_room",
            "media_content_id": "http://example.com/stream.mp3",
            "media_content_type": "music"
        })
    """
    token = os.environ.get('SUPERVISOR_TOKEN')

    if not token:
        logger.warning("No SUPERVISOR_TOKEN available - running outside HA?")
        return None

    url = f"http://supervisor/core/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    logger.info(f'Calling HA service: {domain}.{service}')

    try:
        response = httpx.post(url, json=service_data, headers=headers, timeout=timeout)
        logger.info(f'Response status: {response.status_code}')
        return response.json() if response.text else None
    except httpx.TimeoutException:
        logger.info('Service call sent (response timed out, but command was delivered)')
        return None
    except Exception as e:
        logger.error(f'Service call error: {e}')
        return None


def get_supervisor_token() -> Optional[str]:
    """Get the Home Assistant Supervisor token from environment."""
    return os.environ.get('SUPERVISOR_TOKEN')


def is_ha_environment() -> bool:
    """Check if running in Home Assistant addon environment."""
    return os.environ.get('SUPERVISOR_TOKEN') is not None
