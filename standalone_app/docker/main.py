#!/usr/bin/env python3
"""
Sonorium Standalone - Docker Entry Point.

This is the main entry point for the Docker standalone container.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add sonorium to path (synced from shared/sonorium/)
sys.path.insert(0, str(Path(__file__).parent))

from sonorium.core.state import StateManager
from sonorium.web.app import create_app


async def main():
    """Main entry point for Docker standalone."""
    print("Starting Sonorium (Docker Standalone)...")

    # Get configuration from environment
    host = os.environ.get("SONORIUM_HOST", "0.0.0.0")
    port = int(os.environ.get("SONORIUM_PORT", "8099"))

    # Initialize state manager
    state = StateManager()

    # Create FastAPI app
    app = create_app(state)

    # Run with uvicorn
    import uvicorn
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
