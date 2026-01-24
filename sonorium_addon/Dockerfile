# Sonorium HA Addon Dockerfile
ARG BUILD_FROM=ghcr.io/hassio-addons/base:16.3.2
FROM ${BUILD_FROM}

# Install Python and system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg

WORKDIR /app

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn[standard] \
    pydantic \
    httpx \
    aiofiles \
    python-multipart \
    paho-mqtt \
    zeroconf

# Copy shared code (synced from shared/sonorium/)
COPY sonorium/ /app/sonorium/

# Copy HA-specific wrapper code (NOT synced)
COPY ha/ /app/ha/

# Copy entry point (wrapper code)
COPY main.py /app/main.py

# Copy assets
COPY logo.png icon.png /app/

# Copy bundled themes
COPY themes/ /app/themes/

# Set environment
ENV PYTHONPATH="/app:${PYTHONPATH}" \
    PYTHONUNBUFFERED=1

# Copy run script
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Version label from build arg
ARG ADDON_VERSION
LABEL io.hass.version="${ADDON_VERSION:-0.1.0}"

CMD [ "/run.sh" ]
