MUSIC ASSISTANT AIRPLAY IMPLEMENTATION ANALYSIS
===============================================
Created: 2024-12-19
Purpose: Understand how Music Assistant implements AirPlay 2


KEY FINDING: NOT PURE PYTHON
============================

Music Assistant does NOT implement AirPlay 2 in Python.

They use pre-compiled C binaries:
- cliap2: AirPlay 2 streaming (based on OwnTone)
- cliraop: RAOP/AirPlay 1 streaming (based on philippe44's libraop)

Python just coordinates:
1. Spawns the C binary as subprocess
2. Pipes PCM audio to stdin/named pipe
3. Sends commands via named pipe
4. Monitors stderr for status updates


ARCHITECTURE
============

Files:
  music_assistant/providers/airplay/
  ├── bin/
  │   ├── cliap2-linux-aarch64
  │   ├── cliap2-linux-x86_64
  │   ├── cliap2-macos-arm64
  │   ├── cliap2-macos-x86_64
  │   ├── cliraop-linux-aarch64
  │   ├── cliraop-linux-x86_64
  │   └── cliraop-macos-arm64
  ├── protocols/
  │   ├── airplay2.py    (spawns cliap2 binary)
  │   └── raop.py        (spawns cliraop binary)
  └── player.py          (chooses protocol)

Flow:
  Python Player -> Selects Protocol -> Spawns C Binary -> Streams Audio


BINARY SOURCES
==============

cliap2 (AirPlay 2):
  Based on: OwnTone server (https://github.com/owntone/owntone-server)
  Written in: C
  Features: Full AirPlay 2 support including encryption

cliraop (RAOP/AirPlay 1):
  Based on: philippe44's libraop
  Written in: C
  Features: RAOP streaming with optional encryption


PLATFORM SUPPORT
================

Binaries provided for:
  - Linux x86_64 (amd64)
  - Linux aarch64 (arm64)
  - macOS x86_64 (Intel)
  - macOS arm64 (Apple Silicon)

NOT SUPPORTED:
  - Windows (no binaries provided!)


CAN WE USE THIS FOR SONORIUM?
=============================

PROBLEMS:

1. NO WINDOWS BINARIES
   - Sonorium Windows app would not work
   - Would need to compile cliap2 for Windows (complex)

2. BINARY DISTRIBUTION
   - Would need to bundle C binaries with Python package
   - Increases package size significantly
   - Platform-specific builds required

3. LICENSING
   - Need to check OwnTone license (GPL v2)
   - May have implications for Sonorium

4. COMPLEXITY
   - Need named pipes, subprocess management
   - Cross-platform pipe handling differs


ALTERNATIVES FOR SONORIUM
=========================

For Sonos specifically:
  -> SoCo library (ALREADY WORKING in v1.2.17!)
  -> Native Sonos protocol, no AirPlay needed

For AirPlay 1 devices:
  -> pyatv works for devices with et=0,3,5

For AirPlay 2-only devices (non-Sonos):
  -> No good pure-Python solution exists
  -> Would need C binaries like Music Assistant
  -> Or wait for pyatv to implement AirPlay 2


RECOMMENDATION
==============

For Sonorium:

1. Keep SoCo for Sonos (already working)
2. Keep pyatv for AirPlay 1 devices
3. Document that AirPlay 2-only devices (other than Sonos) are limited
4. Consider OwnTone/cliap2 approach for future if cross-platform isn't needed


REFERENCES
==========

- Music Assistant: https://github.com/music-assistant/server
- OwnTone: https://github.com/owntone/owntone-server
- Music Assistant AirPlay docs: https://www.music-assistant.io/player-support/airplay/
