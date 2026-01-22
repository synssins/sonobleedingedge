"""
Network Utilities for Speaker Plugins

Provides helper functions for network discovery including
subnet detection that works correctly in Docker/container environments.
"""

from __future__ import annotations

import socket
from typing import Optional, List

from sonorium.obs import logger


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
