# Sonorium Standalone Docker Container
# Multi-zone ambient soundscape mixer
#
# Build from repo root:
#   docker build -t sonorium:latest .
#
# Run:
#   docker run -d -p 8008:8008 -v sonorium-data:/app/data --name sonorium sonorium:latest
#
# Or deploy directly from GitHub:
#   docker build -t sonorium https://github.com/synssins/sonobleedingedge.git
#

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Sonorium"
LABEL org.opencontainers.image.description="Multi-zone ambient soundscape mixer"
LABEL org.opencontainers.image.source="https://github.com/synssins/sonobleedingedge"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY app/docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy core source code
COPY app/core/sonorium/ /app/sonorium/

# Copy bundled themes
COPY app/themes/ /app/themes/

# Copy logo and icon for web UI
COPY app/core/logo.png /app/logo.png
COPY app/core/icon.png /app/icon.png

# Create data directories
RUN mkdir -p /app/data/config /app/data/themes /app/data/plugins

# Set Python path
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Environment variables for configuration
ENV SONORIUM_HOST="0.0.0.0"
ENV SONORIUM_PORT="8008"
ENV SONORIUM_DATA_DIR="/app/data"

# Verify installation
RUN python -c "from sonorium.obs import logger; print('Sonorium module OK')"

# Copy entrypoint and fix line endings (Windows CRLF -> Unix LF)
COPY app/docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8008/api/status')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
