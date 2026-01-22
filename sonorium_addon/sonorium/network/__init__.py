"""
Network Utilities

Platform-agnostic network utility functions used across Sonorium components.
"""

from .network_utils import (
    get_local_ip,
    get_all_local_ips,
    get_host_network_ip,
    get_subnet_prefix,
    get_target_subnet,
    is_docker_network,
    DOCKER_PREFIXES,
)

__all__ = [
    "get_local_ip",
    "get_all_local_ips",
    "get_host_network_ip",
    "get_subnet_prefix",
    "get_target_subnet",
    "is_docker_network",
    "DOCKER_PREFIXES",
]
