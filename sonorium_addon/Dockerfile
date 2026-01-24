# Sonorium HA Addon Dockerfile
ARG BUILD_FROM=ghcr.io/hassio-addons/base:16.3.2
FROM ${BUILD_FROM}

# Install Python and system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    ffmpeg

WORKDIR /app

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    pyyaml \
    appdirs \
    cachetools \
    fastapi \
    uvicorn \
    pydantic \
    pydantic-settings \
    httpx \
    homeassistant_api \
    websockets \
    python-multipart \
    soco \
    paho-mqtt \
    pychromecast \
    pyatv \
    'fmtr.tools[version.dev,logging,sets,yaml,debug,caching,api,path.app,tabular,av,ha.api,http]'

# Copy application code
COPY sonorium/ /app/sonorium/

# Copy assets
COPY logo.png icon.png /app/

# Copy bundled themes
COPY themes/ /app/themes/

# Set environment
ENV PYTHONPATH="/app:${PYTHONPATH}" \
    PYTHONUNBUFFERED=1

# Copy entrypoint
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Version label from build arg
ARG ADDON_VERSION
LABEL io.hass.version="${ADDON_VERSION:-0.1.0}"

CMD [ "/run.sh" ]
