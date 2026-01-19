# Sonorium Architecture Document

**Version:** 1.0  
**Last Updated:** December 2024  
**Author:** Chris (synssins)

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Goals and Vision](#goals-and-vision)
3. [Requirements](#requirements)
4. [Architecture](#architecture)
5. [Deployment Targets](#deployment-targets)
6. [Protocol Support](#protocol-support)
7. [Licensing Requirements](#licensing-requirements)
8. [Development Standards](#development-standards)

---

## Project Overview

Sonorium is a **multi-zone ambient soundscape mixer** that enables users to create immersive audio environments by mixing multiple audio sources and streaming them to network speakers throughout their home or workspace.

### What Sonorium Does

- Discovers network speakers automatically (AirPlay, DLNA, Chromecast, Sonos)
- Mixes multiple ambient audio sources (rain, thunder, wind, music, etc.)
- Streams mixed audio to one or more speakers simultaneously
- Provides a web-based UI for control from any device
- Integrates with Home Assistant for home automation workflows

### Target Users

- Home automation enthusiasts
- People who use ambient soundscapes for focus, relaxation, or sleep
- Users with multi-room audio setups
- Home Assistant users seeking integrated audio control

---

## Goals and Vision

### Primary Goals

1. **Simplicity** - One-click ambient soundscapes without complex audio setup
2. **Multi-Zone** - Stream different or synchronized audio to multiple rooms
3. **Integration** - First-class Home Assistant support with standalone capability
4. **Portability** - Run anywhere: Windows, Linux, Docker, Home Assistant

### Non-Goals

- Sonorium is NOT a general-purpose media player
- Sonorium is NOT a music streaming service
- Sonorium does NOT require cloud connectivity (fully local)

### Vision Statement

> Enable anyone to create beautiful ambient soundscapes throughout their space with zero configuration, using the speakers they already own.

---

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Discover network speakers via mDNS/SSDP automatically | Must Have |
| FR-02 | Support AirPlay 1 (RAOP) audio streaming | Must Have |
| FR-03 | Support DLNA/UPnP audio streaming | Must Have |
| FR-04 | Mix multiple audio sources with independent volume | Must Have |
| FR-05 | Web-based UI accessible from any browser | Must Have |
| FR-06 | REST API for programmatic control | Must Have |
| FR-07 | Preset/theme system for saved configurations | Should Have |
| FR-08 | Support Chromecast audio streaming | Should Have |
| FR-09 | Support Sonos speakers | Should Have |
| FR-10 | Synchronized multi-room playback | Could Have |

### Non-Functional Requirements

#### Portability (MANDATORY)

| ID | Requirement |
|----|-------------|
| NFR-P01 | Core application code MUST run identically on Windows, Linux, macOS, and Docker |
| NFR-P02 | No platform-specific code in core modules (`app/core/`) |
| NFR-P03 | All file paths MUST use `pathlib.Path`, never string concatenation |
| NFR-P04 | No assumptions about filesystem case sensitivity |
| NFR-P05 | No assumptions about line endings (handle both LF and CRLF) |
| NFR-P06 | No subprocess calls to OS-specific tools in core code |
| NFR-P07 | Platform-specific code isolated to launcher modules only |

#### Dependency Requirements (MANDATORY)

| ID | Requirement |
|----|-------------|
| NFR-D01 | All dependencies MUST be installable via pip |
| NFR-D02 | No compiled extensions that aren't available on all platforms |
| NFR-D03 | All dependencies MUST have licenses permitting free use (see [Licensing](#licensing-requirements)) |
| NFR-D04 | Prefer pure Python implementations where performance permits |
| NFR-D05 | Pin dependency versions for reproducible builds |

#### Protocol Compliance (MANDATORY)

| ID | Requirement |
|----|-------------|
| NFR-PC01 | AirPlay implementation MUST follow published RAOP/AirPlay specifications |
| NFR-PC02 | No device-specific hacks or workarounds in core protocol code |
| NFR-PC03 | Protocol implementations MUST work with ANY compliant receiver |
| NFR-PC04 | No protocol fallbacks (don't switch from AirPlay to DLNA on failure) |
| NFR-PC05 | Document any device-specific observations WITHOUT coding around them |

#### Performance Requirements

| ID | Requirement |
|----|-------------|
| NFR-PF01 | Speaker discovery completes within 5 seconds |
| NFR-PF02 | Audio streaming latency under 500ms for local network |
| NFR-PF03 | Memory usage under 256MB for typical operation |
| NFR-PF04 | CPU usage under 10% when streaming to 4 speakers |

#### Security Requirements

| ID | Requirement |
|----|-------------|
| NFR-S01 | No cloud connectivity required (fully local operation) |
| NFR-S02 | Web UI accessible only on local network by default |
| NFR-S03 | No telemetry or data collection |
| NFR-S04 | Credentials never logged or exposed in error messages |

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                          │
├─────────────────┬─────────────────┬─────────────────────────────┤
│    Web UI       │   REST API      │   Home Assistant Integration │
│  (Browser)      │  (JSON/HTTP)    │   (HA Add-on API)           │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         └─────────────────┼───────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE APPLICATION                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Web API    │  │   Config    │  │   Theme/Preset Manager  │  │
│  │  Server     │  │   Manager   │  │                         │  │
│  └──────┬──────┘  └─────────────┘  └─────────────────────────┘  │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────┐    │
│  │                   AUDIO ENGINE                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │    │
│  │  │   Source    │  │    Mixer    │  │    Encoder      │  │    │
│  │  │   Manager   │  │             │  │  (PCM/ALAC)     │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │    │
│  └──────────────────────────┬───────────────────────────────┘    │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐    │
│  │                 STREAMING ENGINE                          │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │    │
│  │  │  Speaker    │  │  Protocol   │  │    Session      │   │    │
│  │  │  Discovery  │  │  Handlers   │  │    Manager      │   │    │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PROTOCOL LAYER                               │
├─────────────┬─────────────┬─────────────┬───────────────────────┤
│   AirPlay   │    DLNA     │ Chromecast  │        Sonos          │
│   (RAOP)    │   (UPnP)    │   (Cast)    │       (SoCo)          │
└─────────────┴─────────────┴─────────────┴───────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NETWORK LAYER                                │
├─────────────────────────┬───────────────────────────────────────┤
│   mDNS/Bonjour          │            SSDP                       │
│   (zeroconf)            │     (async-upnp-client)               │
└─────────────────────────┴───────────────────────────────────────┘
```

### Module Structure

```
sonorium/
├── app/
│   ├── core/                    # Platform-agnostic core (PORTABLE)
│   │   └── sonorium/
│   │       ├── __init__.py
│   │       ├── main.py          # Application entry point
│   │       ├── web_api.py       # REST API + Web UI server
│   │       ├── config.py        # Configuration management
│   │       ├── theme.py         # Preset/theme system
│   │       ├── recording.py     # Audio decoding/mixing
│   │       ├── streaming.py     # Stream session management
│   │       ├── network_speakers.py  # Speaker discovery
│   │       ├── raop_client.py   # AirPlay/RAOP implementation
│   │       ├── dlna_client.py   # DLNA/UPnP implementation
│   │       └── audio_output.py  # Local audio playback
│   │
│   ├── windows/                 # Windows-specific launcher
│   │   └── src/
│   │       └── launcher.py
│   │
│   └── docker/                  # Docker-specific files
│       └── Dockerfile
│
├── sonorium_addon/              # Home Assistant Add-on (SEPARATE)
│   ├── config.yaml
│   ├── run.sh
│   └── ...
│
├── web/                         # Web UI static files
│   ├── index.html
│   ├── css/
│   └── js/
│
└── tests/                       # Test suite
    └── ...
```

### Core Components

#### Web API Server (`web_api.py`)

- aiohttp-based HTTP server
- REST API for all operations
- Serves static web UI files
- WebSocket support for real-time updates

#### Audio Engine (`recording.py`)

- Decodes audio from various sources (MP3, WAV, OGG, streams)
- Mixes multiple sources with independent volume control
- Outputs PCM audio for streaming or local playback

#### Streaming Engine (`streaming.py`)

- Manages active streaming sessions
- Routes audio to appropriate protocol handlers
- Handles session lifecycle (start, stop, error recovery)

#### Speaker Discovery (`network_speakers.py`)

- mDNS discovery for AirPlay speakers
- SSDP discovery for DLNA speakers
- Unified speaker model across protocols

#### Protocol Handlers

Each protocol has a dedicated handler implementing a common interface:

```python
class ProtocolHandler(ABC):
    @abstractmethod
    async def connect(self, speaker: Speaker) -> Session:
        """Establish connection to speaker."""
        pass
    
    @abstractmethod
    async def stream_audio(self, session: Session, audio_data: bytes) -> None:
        """Send audio data to speaker."""
        pass
    
    @abstractmethod
    async def disconnect(self, session: Session) -> None:
        """Close connection to speaker."""
        pass
```

---

## Deployment Targets

### 1. Windows Standalone Application

**Target Users:** Windows desktop users who want a native application

**Packaging:**
- PyInstaller-bundled executable
- Embedded Python interpreter
- All dependencies included
- Single-file or folder distribution

**Requirements:**
- Windows 10/11 (x64)
- No installation required (portable)
- No admin rights required
- No external dependencies

### 2. Docker Container

**Target Users:** Linux/NAS users, self-hosters

**Packaging:**
- Multi-architecture Docker image (amd64, arm64)
- Based on Python slim image
- All dependencies in container

**Requirements:**
- Docker runtime
- Host network mode (for mDNS/SSDP)
- Volume mount for configuration persistence

### 3. Home Assistant Add-on

**Target Users:** Home Assistant users

**Packaging:**
- HA Add-on repository
- Supervisor-managed container
- HA API integration

**Requirements:**
- Home Assistant OS or Supervised
- Add-on store access

**Note:** The Home Assistant Add-on (`sonorium_addon/`) maintains a SEPARATE codebase optimized for HA integration. Core functionality should be synchronized but HA-specific code remains isolated.

---

## Protocol Support

### AirPlay (RAOP) - Primary Focus

**Status:** In Development

**Implementation Requirements:**
1. Standards-compliant AirPlay 1 (RAOP) implementation
2. mDNS service discovery (`_raop._tcp`)
3. RTSP session management
4. Audio encoding (ALAC preferred, PCM fallback)
5. RTP audio packet transmission
6. Timing synchronization

**Compliance Rules:**
- Follow published RAOP specifications
- NO device-specific workarounds
- Must work with ANY AirPlay receiver
- Test against multiple receiver brands

**Library:** Custom implementation or pyatv (MIT License)

### DLNA/UPnP

**Status:** Working

**Implementation:**
- SSDP discovery
- AVTransport service control
- HTTP audio serving (pull model)

**Library:** async-upnp-client (Apache 2.0 License)

### Chromecast

**Status:** Planned

**Library:** pychromecast (MIT License)

### Sonos

**Status:** Planned

**Library:** soco (MIT License)

---

## Licensing Requirements

All dependencies MUST have licenses that permit:
- Free use in open-source projects
- Free use in closed-source projects
- Distribution without royalties
- Modification

### Acceptable Licenses

| License | Acceptable | Notes |
|---------|------------|-------|
| MIT | ✅ Yes | Preferred |
| Apache 2.0 | ✅ Yes | Requires attribution |
| BSD (2/3-clause) | ✅ Yes | |
| ISC | ✅ Yes | |
| LGPL | ⚠️ Conditional | Dynamic linking only |
| MPL 2.0 | ⚠️ Conditional | File-level copyleft |
| GPL | ❌ No | Viral copyleft |
| AGPL | ❌ No | Network copyleft |
| Proprietary | ❌ No | |

### Current Dependencies

| Package | License | Purpose |
|---------|---------|---------|
| aiohttp | Apache 2.0 | HTTP server/client |
| zeroconf | LGPL 2.1 | mDNS discovery |
| async-upnp-client | Apache 2.0 | DLNA/UPnP |
| pyatv | MIT | AirPlay (reference) |
| sounddevice | MIT | Local audio output |
| miniaudio | MIT | Audio decoding |
| PyQt6 | GPL | Windows GUI only* |

*PyQt6 GPL applies only to Windows standalone app. Core library is not affected.

### License Compliance Process

1. Before adding any dependency, verify license compatibility
2. Document license in requirements.txt comments
3. Include license notices in distribution
4. Prefer MIT/Apache licensed alternatives when available

---

## Development Standards

### Code Style

- Python 3.10+ with type hints
- Black formatter (line length 100)
- isort for imports
- flake8 for linting
- docstrings for public APIs

### Git Workflow

- Primary development on Gitea (`origin`)
- GitHub is backup only - never push
- Feature branches: `feature/<description>`
- Bug fixes: `fix/<description>`
- All merges to `main` require explicit approval

### Testing Requirements

- Unit tests for core functionality
- Integration tests for protocol handlers
- Cross-platform CI testing (Windows, Linux)
- Test against multiple speaker brands

### Documentation Requirements

- Architecture document (this file)
- API documentation (OpenAPI/Swagger)
- User guide
- Developer setup guide

### Commit Standards

- Descriptive commit messages
- NO AI attribution (no "Co-authored-by: Claude" etc.)
- Reference issue numbers when applicable
- Atomic commits (one logical change per commit)

---

## Appendix A: AirPlay/RAOP Protocol Summary

### Discovery

- mDNS service type: `_raop._tcp.local.`
- TXT record contains device capabilities

### Session Establishment

1. RTSP OPTIONS - Capability exchange
2. RTSP ANNOUNCE - Session setup with SDP
3. RTSP SETUP - Transport negotiation (UDP ports)
4. RTSP RECORD - Begin streaming
5. RTSP SET_PARAMETER - Volume, progress updates
6. RTSP TEARDOWN - End session

### Audio Streaming

- RTP over UDP
- ALAC encoding (44100 Hz, 16-bit, stereo)
- 352 samples per packet
- Timing synchronization via NTP

### Key Ports

- RTSP: TCP (advertised via mDNS, typically 5000 or 7000)
- Audio: UDP (negotiated in SETUP)
- Control: UDP (negotiated in SETUP)
- Timing: UDP (negotiated in SETUP)

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| ALAC | Apple Lossless Audio Codec |
| mDNS | Multicast DNS (Bonjour/Avahi) |
| RAOP | Remote Audio Output Protocol (AirPlay audio) |
| RTP | Real-time Transport Protocol |
| RTSP | Real-Time Streaming Protocol |
| SDP | Session Description Protocol |
| SSDP | Simple Service Discovery Protocol |
| UPnP | Universal Plug and Play |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Dec 2024 | Chris | Initial architecture document |
