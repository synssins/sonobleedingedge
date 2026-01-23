# Sonorium Docker

Run Sonorium as a standalone Docker container for Linux servers or any Docker-capable system.

## Quick Start Options

### Option 1: Deploy directly from GitHub (easiest)

```bash
# Download docker-compose.yml and run
curl -O https://raw.githubusercontent.com/synssins/sonobleedingedge/main/docker-compose.yml
docker compose up -d
```

### Option 2: Clone and run

```bash
git clone https://github.com/synssins/sonobleedingedge.git
cd sonobleedingedge
docker compose up -d
```

### Option 3: Build from GitHub URL

```bash
docker build -t sonorium:latest https://github.com/synssins/sonobleedingedge.git
docker run -d --name sonorium --network host -v sonorium-data:/app/data sonorium:latest
```

**Access the web UI at: http://localhost:8008** (or your server's IP)

---

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
| `/app/data/plugins` | Installed plugins |

---

## Network Speaker Discovery

For speaker discovery (mDNS, SSDP, Sonos, Chromecast, etc.), the container needs host network access:

```yaml
network_mode: host
```

Without host networking, only manual speaker configuration will work.

### Supported Protocols
- **Sonos** - Auto-discovery and control
- **Chromecast/Google Cast** - Auto-discovery and streaming
- **AirPlay** - AirPlay 1 and 2 devices
- **DLNA/UPnP** - Universal media renderers
- **HEOS** - Denon/Marantz devices
- **Linkplay** - Arylic and compatible devices

---

## Custom Themes

### Mount a local folder

```yaml
volumes:
  - /path/to/your/themes:/app/data/themes:ro
```

### Copy themes into the volume

```bash
docker cp ./MyTheme sonorium:/app/data/themes/
docker restart sonorium
```

---

## Health Check

The container includes a health check:

```bash
docker inspect --format='{{.State.Health.Status}}' sonorium
```

---

## Logs

```bash
docker compose logs -f sonorium
# or
docker logs -f sonorium
```

---

## Updating

```bash
# If using docker-compose.yml from repo root:
git pull
docker compose build
docker compose up -d

# If built from GitHub URL:
docker build -t sonorium:latest https://github.com/synssins/sonobleedingedge.git
docker stop sonorium && docker rm sonorium
docker run -d --name sonorium --network host -v sonorium-data:/app/data sonorium:latest
```

---

## Alternative: Bridge Network (limited)

If you can't use host networking, you can use port mapping:

```yaml
services:
  sonorium:
    # ...
    # network_mode: host  # Comment this out
    ports:
      - "8008:8008"
```

**Note:** Speaker auto-discovery will NOT work in bridge mode. You'll need to manually configure speaker IPs.

---

## Differences from Windows App

| Feature | Docker | Windows App |
|---------|--------|-------------|
| Local audio output | No (headless) | Yes |
| Network speakers | Yes (all protocols) | Yes |
| System tray | No | Yes |
| Auto-open browser | No | Yes |
| Updates | Manual rebuild | Built-in updater |

---

## Troubleshooting

### Speakers not discovered

1. Ensure `network_mode: host` is set
2. Check that speakers are on the same network
3. View logs: `docker logs sonorium`

### Container won't start

1. Check port 8008 isn't in use: `netstat -tlnp | grep 8008`
2. View logs: `docker logs sonorium`

### Permission issues

```bash
# Fix volume permissions
docker exec sonorium chown -R 1000:1000 /app/data
```
