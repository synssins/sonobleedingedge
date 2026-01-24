"""
Sonorium FastAPI Application.

Creates the main web application with all routes and middleware.
Built from scratch without external dependencies beyond FastAPI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
import logging

from .api import router as api_router
from ..core.state import init_state_manager, get_state_manager
from ..models import Settings

logger = logging.getLogger(__name__)


def get_version() -> str:
    """Read version from VERSION file."""
    # Look for VERSION file in project root
    current = Path(__file__).parent
    for _ in range(5):  # Search up to 5 levels
        version_file = current / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        current = current.parent
    return "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Sonorium...")

    # Initialize state manager
    config_path = app.state.config_path if hasattr(app.state, "config_path") else None
    await init_state_manager(config_path)

    # Get MQTT settings - prefer app settings over state manager settings
    # App settings come from environment variables and are more up-to-date
    if hasattr(app.state, "app_settings") and app.state.app_settings:
        mqtt_settings = app.state.app_settings.mqtt
    else:
        mqtt_settings = get_state_manager().get_settings().mqtt

    # Initialize MQTT if enabled
    if mqtt_settings.enabled:
        try:
            from ..core.mqtt import init_mqtt_bridge
            await init_mqtt_bridge(mqtt_settings)
            logger.info("MQTT bridge initialized")
        except ImportError:
            logger.warning("MQTT bridge not available")
        except Exception as e:
            logger.error(f"Failed to initialize MQTT: {e}")

    logger.info(f"Sonorium {get_version()} started")

    yield

    # Shutdown
    logger.info("Shutting down Sonorium...")

    # Disconnect MQTT
    try:
        from ..core.mqtt import stop_mqtt_bridge
        await stop_mqtt_bridge()
    except (ImportError, Exception):
        pass

    # Save state
    await get_state_manager().save()

    logger.info("Sonorium stopped")


def create_app(
    settings: Settings = None,
    config_path: Path = None,
    static_dir: Path = None,
) -> FastAPI:
    """
    Create the Sonorium FastAPI application.

    Args:
        settings: Application settings (optional, will use defaults)
        config_path: Path to config file for state persistence
        static_dir: Path to static files directory for web UI

    Returns:
        Configured FastAPI application
    """
    settings = settings or Settings()

    app = FastAPI(
        title="Sonorium",
        description="Multi-zone ambient soundscape mixer",
        version=get_version(),
        lifespan=lifespan,
    )

    # Store config path and settings for lifespan
    app.state.config_path = config_path
    app.state.app_settings = settings

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.web.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router)

    # Serve static files for web UI
    if static_dir and static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index():
            """Serve the web UI."""
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"message": "Sonorium API", "docs": "/docs"}

    else:
        @app.get("/")
        async def index():
            """API root."""
            return {
                "name": "Sonorium",
                "version": get_version(),
                "docs": "/docs",
                "api": "/api",
            }

    return app


def create_standalone_app(
    data_dir: Path = None,
    static_dir: Path = None,
) -> FastAPI:
    """
    Create app configured for standalone deployment.

    Args:
        data_dir: Directory for config and data storage
        static_dir: Directory containing web UI static files

    Returns:
        Configured FastAPI application
    """
    # Determine paths
    if data_dir is None:
        import appdirs
        data_dir = Path(appdirs.user_data_dir("sonorium", "sonorium"))

    config_path = data_dir / "config.json"

    # Load settings from environment and config
    settings = Settings.from_env()
    settings.data_dir = str(data_dir)

    return create_app(
        settings=settings,
        config_path=config_path,
        static_dir=static_dir,
    )


def create_ha_addon_app() -> FastAPI:
    """
    Create app configured for Home Assistant addon deployment.

    Paths and settings are derived from HA environment.

    Returns:
        Configured FastAPI application
    """
    import os

    # HA addon paths
    data_dir = Path("/data")
    config_path = data_dir / "config.json"
    static_dir = Path("/app/sonorium/web/static")

    # Load settings from environment
    settings = Settings.from_env()
    settings.data_dir = str(data_dir)

    # Check for media path
    media_path = Path("/media/sonorium")
    if media_path.exists():
        settings.theme_dirs.append(str(media_path))

    return create_app(
        settings=settings,
        config_path=config_path,
        static_dir=static_dir if static_dir.exists() else None,
    )


async def run_server(app: FastAPI, host: str = "0.0.0.0", port: int = 8099):
    """Run the application server."""
    import uvicorn

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()
