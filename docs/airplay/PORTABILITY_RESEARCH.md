# AirPlay Portability Research

> Research conducted: December 2025
> Goal: Fully portable AirPlay support across all platforms

---

## Current Audio Architecture

```
Audio Files (any format)
    |
    v
PyAV (av) <-- Already used, excellent wheel support
    | decode + resample
    v
NumPy arrays
    |
    v
AudioMixer (mixing)
    |
    v
+------------------------------------------+
|           OUTPUT OPTIONS                  |
+------------------------------------------+
| Local:   sounddevice -> PortAudio        |
| DLNA:    HTTP pull (device fetches URL)  |
| AirPlay: pyatv -> miniaudio (PROBLEM)    |
+------------------------------------------+
```

---

## The miniaudio Problem

**miniaudio is NOT a direct Sonorium dependency.** It's a transitive dependency of pyatv, required for RAOP (AirPlay audio) streaming.

### Installation Issues
- Pre-built wheels often broken on ARM, M1 Macs, Windows
- May require C compiler (Visual C++ on Windows, gcc on Linux)
- Compiles with wrong CPU target from GitHub Actions runners

### Why miniaudio Should Be Fixable
1. **Designed to be portable** - Single-header C library, no dependencies
2. **Uses CFFI** - Pure Python bindings, works on PyPy too
3. **piwheels has ARM builds** - https://www.piwheels.org/project/miniaudio/
4. **The issue is wheel compilation**, not the library itself

### Solution: Build from Source
```bash
# Force source build instead of using broken pre-built wheels
pip install --no-binary miniaudio miniaudio
```

For release builds (in CI):
```yaml
- name: Install dependencies (build miniaudio from source)
  run: |
    pip install cffi  # Required for miniaudio build
    pip install --no-binary miniaudio miniaudio
    pip install -r app/core/requirements.txt
```

---

## Current Dependencies Assessment

| Library | Purpose | Wheel Status | Notes |
|---------|---------|--------------|-------|
| **PyAV** | Audio decode/resample | Excellent | Pre-built for Win/Mac/Linux, all architectures |
| **sounddevice** | Local audio output | Good | Bundles PortAudio on Win/Mac; Linux needs libportaudio2 |
| **pyatv** | AirPlay streaming | Problematic | miniaudio wheels broken on some platforms |
| **miniaudio** | Audio codec (pyatv dep) | Fixable | Build from source works everywhere |

---

## Alternative: RAOP-Player-bindings

If miniaudio proves too problematic, this is a solid fallback.

**Repository:** https://github.com/Schlaubischlump/RAOP-Player-bindings

### Features
- **Explicit platform support**: Windows, macOS, Linux x86, ARM
- **Dependencies**: OpenSSL (widely available), pthread
- **Protocol**: RAOP v2 with sync (same as pyatv)
- **Input**: Raw PCM (use existing PyAV pipeline to decode)
- **Based on**: philippe44's proven RAOP C library

### Installation
```bash
pip install git+https://github.com/Schlaubischlump/RAOP-Player-bindings
```

### Conceptual Integration
```python
import av
from raop_player import RAOPPlayer

# Decode with PyAV (already working in recording.py)
audio_data = decode_to_pcm(source_file)

# Stream with RAOP-Player
player = RAOPPlayer(host, port)
player.play(audio_data)
```

### Device-Specific Notes
- Apple TV 4 / HomePods: Do NOT use `-e` encryption flag
- shairport-sync: Use `-e -c alac` flags

### Underlying C Library
- Repository: https://github.com/NebzHB/RAOP-Player
- Build requirements: OpenSSL 1.0+, ALAC codec, Curve25519 crypto
- Makefiles provided for: OSX, Linux x86, Linux x86-64, ARM (armhf)
- Windows: Uses Embarcadero C++ compiler

---

## Other Options Evaluated

### owntone (forked-daapd)
- **What**: Full media server with AirPlay 1 & 2 support
- **Pros**: Mature, has JSON API for control
- **Cons**: Heavy dependency, Linux/FreeBSD only, not embeddable
- **Repository**: https://github.com/owntone/owntone-server

### ffmpeg RAOP Output
- **Status**: FFmpeg does NOT have native RAOP output
- **Workaround**: Pipe ffmpeg PCM output to separate RAOP client
- **Example**: `ffmpeg -i file.mp3 -f s16le -ar 44100 -ac 2 - | raop_play <IP> -`

### shairport-sync
- **What**: AirPlay RECEIVER (turns device into speaker)
- **Not applicable**: We need to SEND to speakers, not receive

---

## Recommended Implementation Path

### Phase 1: Fix miniaudio (Try First)
1. Update CI/release pipeline to build miniaudio from source
2. Test on: Windows x64, Linux x64, Linux ARM (Docker)
3. Verify pyatv AirPlay streaming works on all platforms

### Phase 2: RAOP-Player-bindings (Fallback)
If miniaudio continues to cause issues:
1. Add RAOP-Player-bindings as dependency
2. Create wrapper that matches pyatv streaming interface
3. Use PyAV for PCM conversion (already in codebase)

### Phase 3: Graceful Degradation
```python
AIRPLAY_AVAILABLE = False
AIRPLAY_BACKEND = None

try:
    import pyatv
    AIRPLAY_AVAILABLE = True
    AIRPLAY_BACKEND = "pyatv"
except ImportError:
    try:
        from raop_player import RAOPPlayer
        AIRPLAY_AVAILABLE = True
        AIRPLAY_BACKEND = "raop_player"
    except ImportError:
        pass  # AirPlay disabled
```

---

## Key Files Reference

- **AirPlay streaming**: `app/core/sonorium/streaming.py` (lines 426-646)
- **Audio decoding**: `app/core/sonorium/recording.py` (uses PyAV)
- **Local output**: `app/core/sonorium/audio_output.py` (uses sounddevice)
- **Requirements**: `app/core/requirements.txt`

---

## Sources

- [pyatv Documentation](https://pyatv.dev/)
- [pyatv miniaudio Issue #1162](https://github.com/postlund/pyatv/issues/1162)
- [pyminiaudio GitHub](https://github.com/irmen/pyminiaudio)
- [piwheels miniaudio](https://www.piwheels.org/project/miniaudio/)
- [RAOP-Player-bindings](https://github.com/Schlaubischlump/RAOP-Player-bindings)
- [RAOP-Player C Library](https://github.com/NebzHB/RAOP-Player)
- [sounddevice Installation](https://python-sounddevice.readthedocs.io/en/latest/installation.html)
- [owntone-server](https://github.com/owntone/owntone-server)
