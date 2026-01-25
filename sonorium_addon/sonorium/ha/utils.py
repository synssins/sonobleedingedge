"""
Home Assistant Specific Utilities

Functions that interact with Home Assistant APIs.
These are NOT available in standalone or Docker deployments.

ADDON CODE: This is specific to the Home Assistant addon deployment.
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


async def call_ha_service_async(
    domain: str,
    service: str,
    service_data: dict,
    timeout: float = 5.0
) -> Optional[Any]:
    """
    Call a Home Assistant service asynchronously.

    Args:
        domain: Service domain (e.g., "media_player", "light")
        service: Service name (e.g., "play_media", "turn_on")
        service_data: Service call data (entity_id, etc.)
        timeout: Request timeout in seconds

    Returns:
        Response JSON if available, None otherwise
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=service_data, headers=headers)
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


def get_ha_api_url() -> str:
    """Get the Home Assistant API URL."""
    return os.environ.get('SUPERVISOR_URL', 'http://supervisor/core') + '/api'


async def get_ha_state(entity_id: str, timeout: float = 5.0) -> Optional[dict]:
    """
    Get the current state of a Home Assistant entity.

    Args:
        entity_id: Entity ID (e.g., "media_player.living_room")
        timeout: Request timeout in seconds

    Returns:
        State dict with 'state' and 'attributes', or None if not found
    """
    token = get_supervisor_token()
    if not token:
        return None

    url = f"http://supervisor/core/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to get state for {entity_id}: {response.status_code}")
    except Exception as e:
        logger.error(f"Error getting state for {entity_id}: {e}")

    return None


async def get_all_media_players(timeout: float = 10.0) -> list[dict]:
    """
    Get all media_player entities from Home Assistant.

    Returns:
        List of state dicts for media_player entities
    """
    token = get_supervisor_token()
    if not token:
        return []

    url = "http://supervisor/core/api/states"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                states = response.json()
                return [
                    s for s in states
                    if s.get('entity_id', '').startswith('media_player.')
                ]
    except Exception as e:
        logger.error(f"Error getting media players: {e}")

    return []


__all__ = [
    "call_ha_service",
    "call_ha_service_async",
    "get_supervisor_token",
    "is_ha_environment",
    "get_ha_api_url",
    "get_ha_state",
    "get_all_media_players",
]
