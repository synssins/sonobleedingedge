# Sonorium Docker

Run Sonorium as a standalone Docker container for Linux servers or any Docker-capable system.

## Quick Start

### Using Docker Compose (recommended)

```bash
cd app/docker
docker compose up -d
```

Access the web UI at: **http://localhost:8008**

### Using Docker directly

```bash
# Build
cd app
docker build -t sonorium:latest -f docker/Dockerfile .

# Run
docker run -d \
  --name sonorium \
  -p 8008:8008 \
  -v sonorium-data:/app/data \
  sonorium:latest
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SONORIUM_HOST` | `0.0.0.0` | Server bind address |
| `SONORIUM_PORT` | `8008` | Server port |
| `SONORIUM_DATA_DIR` | `/app/data` | Data directory for config and themes |

### Volumes

| Path | Description |
|------|-------------|
| `/app/data/config` | Configuration files |
| `/app/data/themes` | User-added themes (bundled themes are copied here on first run) |

### Custom Themes

Mount a local folder to add your own themes:

```yaml
volumes:
  - ./my-themes:/app/data/themes
```

Or copy themes into the volume:

```bash
docker cp ./MyTheme sonorium:/app/data/themes/
```

## Network Speakers

The Docker container can stream to DLNA/UPnP speakers on your network. Ensure the container can reach your network:

```yaml
network_mode: host  # Full network access for speaker discovery
```

Or use specific port mappings for controlled access.

## Health Check

The container includes a health check that verifies the API is responding:

```bash
docker inspect --format='{{.State.Health.Status}}' sonorium
```

## Logs

View container logs:

```bash
docker compose logs -f sonorium
# or
docker logs -f sonorium
```

## Updating

```bash
docker compose pull
docker compose up -d
```

## Building from Source

```bash
cd app
docker build -t sonorium:latest -f docker/Dockerfile .
```

## Differences from Windows App

| Feature | Docker | Windows App |
|---------|--------|-------------|
| Local audio output | No (headless) | Yes |
| Network speakers (DLNA) | Yes | Yes |
| System tray | No | Yes |
| Auto-open browser | No | Yes |
| Updates | Manual/Docker pull | Built-in updater |
