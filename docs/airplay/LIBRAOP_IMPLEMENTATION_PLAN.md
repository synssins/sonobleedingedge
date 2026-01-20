AIRPLAY IMPLEMENTATION PLAN FOR SONORIUM
========================================
Created: 2024-12-19
Purpose: Feasibility analysis for cross-platform AirPlay support


SUMMARY
=======

Two separate solutions exist:

1. AirPlay 1 (RAOP): philippe44/libraop
   - Supports: Windows, macOS, Linux (x86, ARM)
   - For devices with et=0,3,5 (includes legacy type 3)
   - Example: Arylic/Linkplay speakers

2. AirPlay 2: music-assistant/cliairplay
   - Supports: Linux, macOS only
   - NO WINDOWS SUPPORT
   - For devices with et=0,4 only (no legacy)


WHAT'S FEASIBLE
===============

✓ SONOS: Already working with SoCo (v1.2.17)
   - No AirPlay needed
   - Native Sonos/UPnP protocol

✓ AIRPLAY 1 DEVICES: Feasible with libraop
   - Cross-platform (Windows, macOS, Linux)
   - Need to compile binaries
   - Devices like Arylic, older AirPort Express

✗ AIRPLAY 2-ONLY (non-Sonos): NOT feasible cross-platform
   - No Windows binary available
   - HomePod, some newer speakers
   - Would only work on Linux/macOS


LIBRAOP IMPLEMENTATION PLAN
===========================

Source: https://github.com/philippe44/libraop

Step 1: Build Binaries
----------------------
Need to compile for each platform:
- Windows x64 (VS2022 project files available)
- Linux x86_64 (CMake)
- Linux aarch64/ARM (CMake cross-compile)
- macOS x86_64 (CMake)
- macOS ARM64 (CMake)

Dependencies:
- OpenSSL
- ALAC codec (macosforge/alac)
- Curve25519 crypto
- pthreads (Windows needs pthreads-win32)

Step 2: Create Python Wrapper
-----------------------------
Similar to Music Assistant's approach:
- Spawn raop_play binary as subprocess
- Pipe PCM audio to stdin
- Send commands via named pipe or stdin
- Monitor stderr for status

Step 3: Integration with Sonorium
---------------------------------
- Add binary selection logic (platform detection)
- Bundle binaries in distribution
- Integrate with streaming.py


RAOP_PLAY USAGE
===============

From libraop README:

  raop_play <ip> [options]

  Options:
    -v <volume>     Volume (0-100)
    -l <latency>    Latency in frames
    -e              Enable encryption
    -p <port>       RAOP port (default 5000)
    -i              Interactive mode (stdin commands)
    -f <file>       Audio file (or use stdin)

Audio Input:
  Accepts raw PCM from stdin
  Format: 16-bit, 44.1kHz, stereo

Commands (interactive mode):
  p = pause
  r = resume
  s = stop
  q = quit
  + = volume up
  - = volume down


ESTIMATED EFFORT
================

Building binaries:
  - Windows: 2-4 hours (VS2022 setup, dependencies)
  - Linux: 1-2 hours (straightforward CMake)
  - macOS: 1-2 hours (CMake)
  - Cross-compilation: 2-4 hours

Python wrapper: 4-8 hours
  - Process management
  - Audio piping
  - Command interface
  - Error handling

Integration: 4-8 hours
  - Platform detection
  - Binary bundling
  - Streaming.py integration
  - Testing

Total: ~20-30 hours of work


ALTERNATIVE: USE EXISTING MUSIC ASSISTANT BINARIES
=================================================

For Linux/macOS only, we could use:
- cliraop binaries from Music Assistant (already built)
- Their Python wrapper code as reference

But this won't help Windows users.


RECOMMENDATION
==============

Priority 1 (DONE): Sonos via SoCo ✓

Priority 2 (FEASIBLE): AirPlay 1 via libraop
  - Build binaries for all platforms
  - Create Python wrapper
  - Covers Arylic, Linkplay, older devices

Priority 3 (LIMITED): AirPlay 2
  - Linux/macOS only via cliairplay
  - Skip Windows (no solution exists)
  - Or wait for future developments


NEXT STEPS
==========

If you want to proceed with AirPlay 1 support:

1. Set up build environment
   - Windows: VS2022 + vcpkg for dependencies
   - Linux: Docker with build tools
   - macOS: Xcode command line tools

2. Clone and build libraop
   git clone https://github.com/philippe44/libraop
   git submodule update --force --recursive --init --remote

3. Test binary with Arylic at 192.168.1.74

4. Create Python wrapper

5. Integrate into Sonorium


QUESTIONS FOR USER
==================

1. Do you want to proceed with libraop for AirPlay 1?
2. Should we skip AirPlay 2 entirely (since Sonos works via SoCo)?
3. Do you have VS2022 for Windows builds?
4. Should I create the Python wrapper first (using existing binaries
   from Music Assistant for testing on Linux)?
