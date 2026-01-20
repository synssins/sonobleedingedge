"""
Sonorium Shared Utilities

Common utility functions and classes used across the codebase.
Platform-agnostic - no HA or standalone specific code here.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional


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
