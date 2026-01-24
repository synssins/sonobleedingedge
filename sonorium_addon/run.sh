#!/usr/bin/with-contenv bash
# shellcheck shell=bash
# ==============================================================================
# Sonorium Addon Startup Script
# ==============================================================================

source /usr/lib/bashio/bashio.sh

bashio::log.info "Starting Sonorium addon..."

# Read configuration
LOG_LEVEL="$(bashio::config 'log_level')"
export SONORIUM_LOG_LEVEL="${LOG_LEVEL:-info}"

# MQTT Configuration - Auto-detect from Supervisor services
if bashio::services.available "mqtt"; then
    bashio::log.info "Auto-detecting MQTT from Supervisor services..."
    export SONORIUM_MQTT_HOST="$(bashio::services mqtt "host")"
    export SONORIUM_MQTT_PORT="$(bashio::services mqtt "port")"
    export SONORIUM_MQTT_USERNAME="$(bashio::services mqtt "username")"
    export SONORIUM_MQTT_PASSWORD="$(bashio::services mqtt "password")"
    bashio::log.info "MQTT: ${SONORIUM_MQTT_HOST}:${SONORIUM_MQTT_PORT}"
else
    bashio::log.warning "MQTT service not available - install Mosquitto broker addon"
fi

bashio::log.info "Configuration:"
bashio::log.info "  Log Level: ${SONORIUM_LOG_LEVEL}"
bashio::log.info "  MQTT Host: ${SONORIUM_MQTT_HOST:-not configured}"

bashio::log.info "Launching Sonorium..."
exec python3 /app/main.py
