# Binary Files

This directory contains platform-specific binaries for Sonorium.

## raop_play - AirPlay 1 (RAOP) Streamer

Binary for streaming audio to AirPlay 1 speakers (RAOP protocol).
Built from [philippe44/libraop](https://github.com/philippe44/libraop).

### Available Binaries

| Platform | Binary Name | Status |
|----------|-------------|--------|
| Linux x86_64 | `raop_play-linux-x86_64` | Built |
| Linux ARM64 | `raop_play-linux-aarch64` | Planned |
| Windows x64 | `raop_play-windows-x64.exe` | Not available* |
| macOS x64 | `raop_play-macos-x64` | Planned |
| macOS ARM64 | `raop_play-macos-arm64` | Planned |

*Windows binaries cannot be cross-compiled from Linux due to missing Windows
SDK headers. Native Windows build with Visual Studio is required.

### Building Linux Binary

Docker-based build environment on a Linux host:

```bash
# On Docker host (e.g., 192.168.1.150)
cd /tmp/libraop-builder
docker-compose build --no-cache
docker-compose run --rm --entrypoint /bin/bash libraop-builder -c \
  'cd /build/libraop && mkdir -p build-linux-x64 && cd build-linux-x64 && \
   cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS="-D_GNU_SOURCE" \
   -DCMAKE_CXX_FLAGS="-D_GNU_SOURCE" && make -j4 && \
   cp raop_play-linux-x86_64 /output/'
# Binary will be in ./output/
```

### Usage

The `raop_streamer.py` module automatically locates binaries in this directory.

```python
from sonorium.raop_streamer import RaopStreamer

streamer = RaopStreamer()
await streamer.start("192.168.1.74", port=4515, volume=50)
await streamer.write(pcm_data)  # 16-bit, 44.1kHz, stereo
await streamer.stop()
```

### Notes

- Arylic/Linkplay speakers use port 4515 for RAOP (not default 7000)
- The binary connects and sends audio, but actual playback depends on device
- For Arylic/Linkplay devices, the HTTP API (`setPlayerCmd:play:{url}`) is
  more reliable than RAOP streaming
