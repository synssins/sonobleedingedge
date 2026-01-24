"""
Docker Standalone App Factory.

Platform-specific application configuration for Docker deployment.
"""

from pathlib import Path
from fastapi import FastAPI

# Import from synced core
from sonorium.web.app import create_app
from sonorium.models import Settings


def create_docker_app(
    data_dir: Path = None,
    static_dir: Path = None,
) -> FastAPI:
    """
    Create app configured for Docker standalone deployment.

    Args:
        data_dir: Directory for config and data storage
        static_dir: Directory containing web UI static files

    Returns:
        Configured FastAPI application
    """
    # Docker paths - configurable via environment or defaults
    import os

    if data_dir is None:
        data_dir = Path(os.environ.get("SONORIUM_DATA_DIR", "/data"))

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    config_path = data_dir / "config.json"

    # Load settings from environment
    settings = Settings.from_env()
    settings.data_dir = str(data_dir)

    # Add plugins and themes directories (volume mapped)
    app_root = Path(__file__).parent.parent
    plugins_dir = app_root / "plugins"
    themes_dir = app_root / "themes"

    if plugins_dir.exists():
        settings.plugins_dir = str(plugins_dir)
    if themes_dir.exists():
        settings.theme_dirs.append(str(themes_dir))

    return create_app(
        settings=settings,
        config_path=config_path,
        static_dir=static_dir,
    )
