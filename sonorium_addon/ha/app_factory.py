"""
Home Assistant Addon App Factory.

Platform-specific application configuration for HA addon deployment.
"""

from pathlib import Path
from fastapi import FastAPI

# Import from synced core
from sonorium.web.app import create_app
from sonorium.models import Settings


def create_ha_addon_app() -> FastAPI:
    """
    Create app configured for Home Assistant addon deployment.

    Paths and settings are derived from HA environment.

    Returns:
        Configured FastAPI application
    """
    # HA addon paths
    data_dir = Path("/data")
    config_path = data_dir / "config.json"
    static_dir = Path("/app/sonorium/web/static")

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load settings from environment
    settings = Settings.from_env()
    settings.data_dir = str(data_dir)

    # Add plugins directory
    plugins_dir = Path("/app/plugins")
    if plugins_dir.exists():
        settings.plugins_dir = str(plugins_dir)

    # Check for media path (HA media folder)
    media_path = Path("/media/sonorium")
    if media_path.exists():
        settings.theme_dirs.append(str(media_path))

    # Also check addon themes folder
    themes_dir = Path("/app/themes")
    if themes_dir.exists():
        settings.theme_dirs.append(str(themes_dir))

    return create_app(
        settings=settings,
        config_path=config_path,
        static_dir=static_dir if static_dir.exists() else None,
    )
