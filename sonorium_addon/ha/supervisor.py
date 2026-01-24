"""
Home Assistant Supervisor API Client.

Provides access to HA Supervisor for addon integration.
"""

import os
from typing import Optional, Any
import httpx


class SupervisorAPI:
    """Client for Home Assistant Supervisor API."""

    def __init__(self):
        """Initialize Supervisor API client."""
        self.token = os.environ.get("SUPERVISOR_TOKEN")
        self.base_url = "http://supervisor"
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_available(self) -> bool:
        """Check if Supervisor API is available."""
        return self.token is not None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, endpoint: str) -> Optional[dict]:
        """Make GET request to Supervisor API."""
        if not self.is_available:
            return None

        try:
            client = await self._get_client()
            response = await client.get(endpoint)
            response.raise_for_status()
            data = response.json()
            return data.get("data", data)
        except Exception as e:
            print(f"Supervisor API error (GET {endpoint}): {e}")
            return None

    async def post(self, endpoint: str, data: Optional[dict] = None) -> Optional[dict]:
        """Make POST request to Supervisor API."""
        if not self.is_available:
            return None

        try:
            client = await self._get_client()
            response = await client.post(endpoint, json=data or {})
            response.raise_for_status()
            result = response.json()
            return result.get("data", result)
        except Exception as e:
            print(f"Supervisor API error (POST {endpoint}): {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Core API
    # ─────────────────────────────────────────────────────────────────────────

    async def get_core_info(self) -> Optional[dict]:
        """Get Home Assistant Core information."""
        return await self.get("/core/info")

    async def get_supervisor_info(self) -> Optional[dict]:
        """Get Supervisor information."""
        return await self.get("/supervisor/info")

    async def get_host_info(self) -> Optional[dict]:
        """Get host information."""
        return await self.get("/host/info")

    # ─────────────────────────────────────────────────────────────────────────
    # Services
    # ─────────────────────────────────────────────────────────────────────────

    async def get_services(self) -> Optional[dict]:
        """Get available services."""
        return await self.get("/services")

    async def get_mqtt_info(self) -> Optional[dict]:
        """Get MQTT addon information."""
        return await self.get("/services/mqtt")

    # ─────────────────────────────────────────────────────────────────────────
    # Discovery
    # ─────────────────────────────────────────────────────────────────────────

    async def get_discovery(self) -> Optional[list]:
        """Get discovered services."""
        result = await self.get("/discovery")
        return result.get("discovery", []) if result else None

    async def send_discovery(
        self,
        service: str,
        config: dict,
    ) -> bool:
        """Send discovery message for a service."""
        result = await self.post(
            "/discovery",
            {"service": service, "config": config},
        )
        return result is not None
