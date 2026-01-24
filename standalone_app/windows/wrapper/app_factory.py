"""
Windows Standalone App Factory.

Platform-specific application configuration for Windows deployment.
"""

from pathlib import Path
from fastapi import FastAPI

# Import from synced core
from sonorium.web.app import create_app
from sonorium.models import Settings


def create_windows_app(
    data_dir: Path = None,
    static_dir: Path = None,
) -> FastAPI:
    """
    Create app configured for Windows standalone deployment.

    Args:
        data_dir: Directory for config and data storage
        static_dir: Directory containing web UI static files

    Returns:
        Configured FastAPI application
    """
    # Determine paths using Windows conventions
    if data_dir is None:
        import appdirs
        data_dir = Path(appdirs.user_data_dir("sonorium", "sonorium"))

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    config_path = data_dir / "config.json"

    # Load settings from environment and config
    settings = Settings.from_env()
    settings.data_dir = str(data_dir)

    # Add plugins and themes directories
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
