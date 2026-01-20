"""
Sonorium Logging - Unified logging module.

Provides InstrumentedLogger with @instrument decorator for method tracing.
Platform-aware logging:
- Standalone: Console + rotating file handler
- Docker/HA: Console only (logs managed by container runtime)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, TypeVar

# Configuration
LOG_NAME = "sonorium"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILES = 10  # Keep up to 10 files (current + 9 backups)

F = TypeVar("F", bound=Callable)


def _detect_platform() -> str:
    """Detect the current deployment platform (self-contained to avoid circular imports)."""
    if os.environ.get("SUPERVISOR_TOKEN"):
        return "ha_addon"
    if os.environ.get("DOCKER_CONTAINER") or os.path.exists("/.dockerenv"):
        return "docker"
    return "standalone"


def _get_log_dir() -> Path:
    """Get the logs directory for standalone deployment."""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE - exe is in app/windows/, logs is in app/logs/
        log_dir = Path(sys.executable).parent.parent / 'logs'
    else:
        # Running as script - this file is in app/core/sonorium/
        # app/core/sonorium/obs.py -> parent = sonorium/, parent.parent = core/, parent.parent.parent = app/
        log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _cleanup_old_logs(log_dir: Path):
    """Clean up legacy timestamped log files."""
    try:
        old_logs = sorted(
            log_dir.glob('sonorium_*.log'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_log in old_logs:
            try:
                old_log.unlink()
            except Exception:
                pass
    except Exception:
        pass


class InstrumentedLogger(logging.Logger):
    """Logger with instrument decorator for method tracing."""

    def instrument(self, message_template: str = "") -> Callable[[F], F]:
        """
        Decorator that logs entry to a function/method.

        Args:
            message_template: Format string that can reference {self}, {value}, etc.
                              from the decorated function's arguments.

        Example:
            @logger.instrument('Setting volume to {value}')
            async def set_volume(self, value):
                ...
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                msg = self._format_instrument_message(message_template, args, kwargs)
                if msg:
                    self.info(msg)
                return func(*args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                msg = self._format_instrument_message(message_template, args, kwargs)
                if msg:
                    self.info(msg)
                return await func(*args, **kwargs)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper  # type: ignore
            return sync_wrapper  # type: ignore

        return decorator

    def _format_instrument_message(self, template: str, args: tuple, kwargs: dict) -> str:
        """Format the instrument message template with available context."""
        if not template:
            return ""
        try:
            # Try to format with self if it's a method
            if args and hasattr(args[0], '__class__'):
                return template.format(self=args[0], **kwargs)
            return template.format(**kwargs)
        except (KeyError, AttributeError, IndexError):
            return template


def get_logger(name: str = LOG_NAME) -> InstrumentedLogger:
    """
    Create an instrumented logger with platform-appropriate handlers.

    Args:
        name: Logger name (default: "sonorium")

    Returns:
        InstrumentedLogger instance
    """
    # Set custom logger class
    logging.setLoggerClass(InstrumentedLogger)

    logger = logging.getLogger(name)
    logger.__class__ = InstrumentedLogger

    if logger.handlers:
        # Already configured
        return logger  # type: ignore

    logger.setLevel(logging.DEBUG)
    platform = _detect_platform()

    # Force unbuffered stdout for Docker/container environments
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except Exception:
            pass

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler for standalone only
    if platform == "standalone":
        try:
            log_dir = _get_log_dir()
            _cleanup_old_logs(log_dir)
            log_file = log_dir / 'sonorium.log'

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=MAX_LOG_SIZE,
                backupCount=MAX_LOG_FILES - 1,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            logger.info(f'Log file: {log_file} (max {MAX_LOG_SIZE // 1024 // 1024}MB, {MAX_LOG_FILES} files)')
        except Exception as e:
            logger.warning(f'Could not create log file: {e}')

    return logger  # type: ignore


# Create the main logger singleton
logger = get_logger()
