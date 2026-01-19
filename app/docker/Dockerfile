# Sonorium Standalone Docker Container
# Multi-zone ambient soundscape mixer
#
# Build: docker build -t sonorium:latest -f docker/Dockerfile .
# Run:   docker run -d -p 8008:8008 -v sonorium-data:/app/data sonorium:latest

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY docker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy core source code
COPY core/sonorium/ /app/sonorium/

# Copy bundled themes
COPY themes/ /app/themes/

# Copy icon for web UI
COPY core/icon.png /app/icon.png

# Create data directories
RUN mkdir -p /app/data/config /app/data/themes

# Set Python path
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Environment variables for configuration
ENV SONORIUM_HOST="0.0.0.0"
ENV SONORIUM_PORT="8008"
ENV SONORIUM_DATA_DIR="/app/data"

# Verify installation
RUN python -c "from sonorium.version import __version__; print(f'Sonorium {__version__}')"

# Copy entrypoint and fix line endings (Windows CRLF -> Unix LF)
COPY docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8008/api/status')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
