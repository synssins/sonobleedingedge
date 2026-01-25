"""
Internal Log Collector

Collects logs from various Sonorium services for display in the Status page.
Keeps a rolling buffer of recent log entries organized by category.

CORE CODE: This module is shared across all platforms.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable

from ..obs import logger


class LogLevel(str, Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogCategory(str, Enum):
    """Log categories for organization."""
    CORE = "core"               # Core system events
    DISCOVERY = "discovery"     # Speaker discovery
    PLAYBACK = "playback"       # Playback operations
    PLUGINS = "plugins"         # Plugin loading/operations
    HA = "ha"                   # Home Assistant integration
    MQTT = "mqtt"               # MQTT operations
    API = "api"                 # API requests


@dataclass
class LogEntry:
    """A single log entry."""
    timestamp: datetime
    category: str
    level: str
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "category": self.category,
            "level": self.level,
            "message": self.message,
            "details": self.details,
        }


class LogCollector:
    """
    Collects and stores logs for UI display.

    Maintains separate buffers for each category with a configurable max size.
    """

    def __init__(self, max_entries_per_category: int = 100):
        """
        Initialize the log collector.

        Args:
            max_entries_per_category: Maximum entries to keep per category
        """
        self.max_entries = max_entries_per_category
        self._logs: dict[str, deque[LogEntry]] = {}
        self._listeners: list[Callable[[LogEntry], None]] = []

        # Initialize all category buffers
        for cat in LogCategory:
            self._logs[cat.value] = deque(maxlen=max_entries_per_category)

        logger.info("LogCollector initialized")

    def log(
        self,
        category: str | LogCategory,
        level: str | LogLevel,
        message: str,
        details: Optional[dict] = None,
    ) -> LogEntry:
        """
        Add a log entry.

        Args:
            category: Log category
            level: Log severity level
            message: Log message
            details: Optional additional details

        Returns:
            The created log entry
        """
        cat_str = category.value if isinstance(category, LogCategory) else category
        level_str = level.value if isinstance(level, LogLevel) else level

        entry = LogEntry(
            timestamp=datetime.now(),
            category=cat_str,
            level=level_str,
            message=message,
            details=details,
        )

        # Add to category buffer
        if cat_str not in self._logs:
            self._logs[cat_str] = deque(maxlen=self.max_entries)
        self._logs[cat_str].append(entry)

        # Also log to standard logger based on level
        log_msg = f"[{cat_str.upper()}] {message}"
        if level_str == LogLevel.ERROR.value:
            logger.error(log_msg)
        elif level_str == LogLevel.WARNING.value:
            logger.warning(log_msg)
        elif level_str == LogLevel.DEBUG.value:
            logger.debug(log_msg)
        else:
            logger.info(log_msg)

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(entry)
            except Exception:
                pass

        return entry

    def debug(self, category: str | LogCategory, message: str, details: Optional[dict] = None):
        """Log at DEBUG level."""
        return self.log(category, LogLevel.DEBUG, message, details)

    def info(self, category: str | LogCategory, message: str, details: Optional[dict] = None):
        """Log at INFO level."""
        return self.log(category, LogLevel.INFO, message, details)

    def warning(self, category: str | LogCategory, message: str, details: Optional[dict] = None):
        """Log at WARNING level."""
        return self.log(category, LogLevel.WARNING, message, details)

    def error(self, category: str | LogCategory, message: str, details: Optional[dict] = None):
        """Log at ERROR level."""
        return self.log(category, LogLevel.ERROR, message, details)

    def get_logs(
        self,
        category: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Get log entries, optionally filtered.

        Args:
            category: Filter by category (None for all)
            level: Filter by minimum level (None for all)
            limit: Maximum entries to return

        Returns:
            List of log entry dicts, newest first
        """
        entries = []

        if category:
            # Single category
            if category in self._logs:
                entries = list(self._logs[category])
        else:
            # All categories
            for cat_logs in self._logs.values():
                entries.extend(cat_logs)

        # Sort by timestamp descending (newest first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Filter by level if specified
        if level:
            level_order = [LogLevel.DEBUG.value, LogLevel.INFO.value,
                          LogLevel.WARNING.value, LogLevel.ERROR.value]
            try:
                min_idx = level_order.index(level)
                entries = [e for e in entries if level_order.index(e.level) >= min_idx]
            except ValueError:
                pass

        # Apply limit
        entries = entries[:limit]

        return [e.to_dict() for e in entries]

    def get_categories(self) -> list[dict]:
        """Get list of categories with entry counts."""
        return [
            {
                "id": cat,
                "name": cat.replace("_", " ").title(),
                "count": len(self._logs.get(cat, [])),
            }
            for cat in self._logs.keys()
        ]

    def clear(self, category: Optional[str] = None):
        """Clear logs, optionally for a specific category."""
        if category:
            if category in self._logs:
                self._logs[category].clear()
        else:
            for logs in self._logs.values():
                logs.clear()

    def add_listener(self, callback: Callable[[LogEntry], None]):
        """Add a listener for new log entries."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]):
        """Remove a log listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)


# Global log collector instance
_collector: Optional[LogCollector] = None


def get_log_collector() -> LogCollector:
    """Get or create the global log collector instance."""
    global _collector
    if _collector is None:
        _collector = LogCollector()
    return _collector


def log(category: str | LogCategory, level: str | LogLevel, message: str, details: Optional[dict] = None):
    """Convenience function to log to the global collector."""
    return get_log_collector().log(category, level, message, details)


def log_info(category: str | LogCategory, message: str, details: Optional[dict] = None):
    """Convenience function to log INFO."""
    return get_log_collector().info(category, message, details)


def log_error(category: str | LogCategory, message: str, details: Optional[dict] = None):
    """Convenience function to log ERROR."""
    return get_log_collector().error(category, message, details)


def log_warning(category: str | LogCategory, message: str, details: Optional[dict] = None):
    """Convenience function to log WARNING."""
    return get_log_collector().warning(category, message, details)


def log_debug(category: str | LogCategory, message: str, details: Optional[dict] = None):
    """Convenience function to log DEBUG."""
    return get_log_collector().debug(category, message, details)
