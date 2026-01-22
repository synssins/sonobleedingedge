"""
Sonorium Shared Utilities

Common utility functions and classes used across the codebase.
Platform-agnostic - no HA or standalone specific code here.
"""

from __future__ import annotations

import re
import socket
from typing import Any, Iterator, List, Optional

from sonorium.obs import logger


class IndexList(list):
    """
    List subclass that supports attribute-based indexing.

    Allows accessing items by their attribute values using dict-like syntax.

    Example:
        themes = IndexList([theme1, theme2, theme3])
        # Access by 'name' attribute:
        themes.name['Forest']  # Returns theme with name='Forest'
        # Access by 'id' attribute:
        themes.id['abc123']    # Returns theme with id='abc123'

    Also supports a 'current' attribute for tracking selection state.
    """

    def __init__(self, iterable: Optional[Iterator] = None):
        super().__init__(iterable or [])
        self.current: Any = None

    def __getattr__(self, name: str):
        """Allow attribute-style access to create dict views."""
        if name.startswith('_'):
            raise AttributeError(name)

        # Return a dict mapping the attribute value to the item
        result = {}
        for item in self:
            if hasattr(item, name):
                key = getattr(item, name)
                result[key] = item
        return result


def sanitize(text: str) -> str:
    """
    Sanitize a string for use as an ID or filename.

    - Converts to lowercase
    - Replaces spaces and special characters with underscores
    - Removes consecutive underscores
    - Strips leading/trailing underscores

    Args:
        text: Input string to sanitize

    Returns:
        Sanitized string safe for use as ID/filename

    Example:
        sanitize("My Theme (v2)")  # Returns "my_theme_v2"
        sanitize("  Hello World!  ")  # Returns "hello_world"
    """
    # Replace spaces and special chars with underscores
    text = re.sub(r'[^\w\-]', '_', text.lower())
    # Remove consecutive underscores
    text = re.sub(r'_+', '_', text)
    # Strip leading/trailing underscores
    return text.strip('_')


def safe_filename(text: str, max_length: int = 255) -> str:
    """
    Create a safe filename from arbitrary text.

    More aggressive than sanitize() - removes all potentially
    problematic characters for cross-platform filesystem compatibility.

    Args:
        text: Input string
        max_length: Maximum filename length (default 255)

    Returns:
        Filesystem-safe filename
    """
    # Remove characters that are problematic on any OS
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    # Replace spaces with underscores
    text = text.replace(' ', '_')
    # Remove consecutive underscores/dots
    text = re.sub(r'[_.]+', lambda m: m.group(0)[0], text)
    # Strip leading/trailing dots and spaces
    text = text.strip('. ')
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    return text or "unnamed"


# =============================================================================
# Network Utilities
# =============================================================================

# Docker/virtual network prefixes to avoid
DOCKER_PREFIXES = [
    '172.17.',   # Default Docker bridge
    '172.18.',
    '172.19.',
    '172.20.',
    '172.21.',
    '172.22.',
    '172.23.',
    '172.24.',
    '172.25.',
    '172.26.',
    '172.27.',
    '172.28.',
    '172.29.',
    '172.30.',   # HA Supervisor networks
    '172.31.',
    '127.',      # Loopback
    '169.254.',  # Link-local
]


def get_local_ip() -> Optional[str]:
    """
    Get the local IP address by connecting to an external endpoint.

    Returns:
        IP address string or None if detection fails
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to Google DNS - doesn't actually send data
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def is_docker_network(ip: str) -> bool:
    """Check if an IP belongs to a Docker/virtual network."""
    return any(ip.startswith(prefix) for prefix in DOCKER_PREFIXES)


def get_all_local_ips() -> List[str]:
    """
    Get all local IP addresses from all network interfaces.

    Returns:
        List of IP addresses
    """
    ips = []
    try:
        hostname = socket.gethostname()
        # Get all addresses for hostname
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Also try the default route method
    default_ip = get_local_ip()
    if default_ip and default_ip not in ips:
        ips.append(default_ip)

    return ips


def get_host_network_ip() -> Optional[str]:
    """
    Get the best IP address for host network operations.

    Prefers non-Docker network IPs. Falls back to any available IP.

    Returns:
        IP address string or None
    """
    ips = get_all_local_ips()

    # First, try to find a non-Docker IP
    for ip in ips:
        if not is_docker_network(ip):
            return ip

    # Fall back to any IP (even Docker network)
    return ips[0] if ips else get_local_ip()


def get_subnet_prefix(ip: str) -> str:
    """Get the /24 subnet prefix from an IP address."""
    return '.'.join(ip.split('.')[:3])


def get_target_subnet(
    configured_subnet: Optional[str] = None,
    plugin_name: str = "Plugin"
) -> Optional[str]:
    """
    Get the target subnet for network scanning.

    Args:
        configured_subnet: User-configured subnet (e.g., "192.168.1")
        plugin_name: Name of the plugin for logging

    Returns:
        Subnet prefix (e.g., "192.168.1") or None
    """
    # Use configured subnet if provided
    if configured_subnet:
        subnet = configured_subnet.strip().rstrip('.')
        parts = subnet.split('.')
        if len(parts) >= 3:
            return '.'.join(parts[:3])
        logger.warning(f"{plugin_name}: Invalid target_subnet '{configured_subnet}'")

    # Auto-detect
    ip = get_host_network_ip()
    if not ip:
        logger.warning(f"{plugin_name}: Could not detect local IP address")
        return None

    subnet = get_subnet_prefix(ip)

    # Warn if Docker network detected
    if is_docker_network(ip):
        logger.warning(
            f"{plugin_name}: Detected Docker/container network ({ip}). "
            f"Network speaker discovery may not work. "
            f"Configure 'target_subnet' in plugin settings if needed."
        )
    else:
        logger.debug(f"{plugin_name}: Using subnet {subnet}.0/24")

    return subnet
