#!/bin/bash
# Sonorium Docker Entrypoint
#
# Handles data directory setup and starts the server

set -e

DATA_DIR="${SONORIUM_DATA_DIR:-/app/data}"
HOST="${SONORIUM_HOST:-0.0.0.0}"
PORT="${SONORIUM_PORT:-8008}"

echo "==================================="
echo "  Sonorium - Ambient Soundscapes"
echo "==================================="
echo ""
echo "Data directory: ${DATA_DIR}"
echo "Server: http://${HOST}:${PORT}"
echo ""

# Create data directories if they don't exist
mkdir -p "${DATA_DIR}/config"
mkdir -p "${DATA_DIR}/themes"

# Copy bundled themes to data dir if themes dir is empty
if [ -z "$(ls -A ${DATA_DIR}/themes 2>/dev/null)" ]; then
    echo "Copying bundled themes to ${DATA_DIR}/themes..."
    if [ -d "/app/themes" ]; then
        cp -r /app/themes/* "${DATA_DIR}/themes/" 2>/dev/null || true
    fi
fi

# Export environment for the app
export SONORIUM_DATA_DIR="${DATA_DIR}"

echo "Starting Sonorium server..."
echo ""

# Run the server (--no-tray and --no-browser for headless Docker)
exec python -m sonorium.main --host "${HOST}" --port "${PORT}" --no-tray --no-browser
