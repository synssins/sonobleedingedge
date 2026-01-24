#!/usr/bin/env python3
"""
Sonorium Standalone - Windows Entry Point.

This is the main entry point for the Windows standalone application.
"""

import asyncio
import sys
from pathlib import Path

# Add sonorium to path (synced from shared/sonorium/)
sys.path.insert(0, str(Path(__file__).parent))

from sonorium.core.state import StateManager
from sonorium.web.app import create_app


async def main():
    """Main entry point for Windows standalone."""
    print("Starting Sonorium (Windows Standalone)...")

    # Initialize state manager
    state = StateManager()

    # Create FastAPI app
    app = create_app(state)

    # Run with uvicorn
    import uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8099,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
