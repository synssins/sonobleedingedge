================================================================================
AIRPLAY 1 TESTING SUMMARY - December 21, 2025
================================================================================

This document summarizes all AirPlay 1 testing performed and outlines the work
needed to implement AirPlay streaming in both:
  - Windows/Docker Standalone App (app/core/sonorium/)
  - Home Assistant Add-on (sonorium_addon/sonorium/)

================================================================================
SECTION 1: DEVICES TESTED
================================================================================

Device                  | IP Address      | Protocol   | Result
------------------------|-----------------|------------|------------------------
Marantz SR5011          | 192.168.1.13    | AirPlay 1  | SUCCESS - Full streaming
AirConnect (aircast)    | 192.168.1.198   | AirPlay 1  | SUCCESS - Bridge works
Arylic Office           | 192.168.1.74    | AirPlay 1  | FAILED - Firmware bug
Arylic Living Room      | 192.168.1.254   | AirPlay 1  | FAILED - Firmware bug
LG S80QR Soundbar       | 192.168.1.117   | AirPlay 2  | PARTIAL - Drops connection
Sonos Era 300           | 192.168.1.185   | AirPlay 2  | PARTIAL - Drops connection

================================================================================
SECTION 2: SUCCESSFUL AIRPLAY 1 STREAMING
================================================================================

2.1 MARANTZ SR5011 (192.168.1.13)
---------------------------------
- Model: SR5011 (AV Receiver)
- Port: 1024 (RAOP), 1025 (AirPlay)
- Encryption: 0,4
- Protocol: AirPlay 1 with pyatv patches

RTSP Flow (Successful):
  1. GET /info        -> 200 OK (binary plist with device info)
  2. pair-pin-start   -> 200 OK
  3. pair-setup       -> 200 OK (transient auth)
  4. SETUP            -> 200 OK (server ports returned correctly)
  5. SET_PARAMETER    -> 200 OK (volume control)
  6. RECORD           -> 200 OK
  7. Audio streaming  -> SUCCESS

Test Results:
  - 5-second C major chord at 30% volume: User reported "I think I heard it"
  - 20-second chord at 60% volume: Stream completed
  - 15-second funky beat at 70% volume: Not heard (generated audio issue)
  - Real audio file (Kevin MacLeod "Funk Game Loop"): SUCCESS - User confirmed

Key Finding: Real audio files stream successfully. Generated/synthesized tones
may have encoding or volume issues that need investigation.


2.2 AIRCONNECT BRIDGE (192.168.1.198)
-------------------------------------
- Software: AirConnect v1.9.3 (aircast mode)
- Bridges: AirPlay -> Chromecast
- Target: NVIDIA SHIELD (Chromecast) at 192.168.1.155
- Model advertised: "aircast"
- Port: Dynamic (changes on restart)

RTSP Flow (Successful):
  1. GET /info        -> 501 Not Implemented (expected, no CSeq header)
  2. ANNOUNCE         -> 200 OK
  3. SETUP            -> 200 OK (Session: DEADBEEF - hex format)
  4. SET_PARAMETER    -> 200 OK
  5. RECORD           -> 200 OK
  6. FLUSH            -> 200 OK
  7. Audio streaming  -> SUCCESS (via Chromecast)

AirConnect Log Confirmation:
  - "1st audio packet received"
  - "buffer_put_packet: now playing"
  - "CastConnect: SSL connection opened"
  - "Cast setURI http://192.168.1.198:52401/stream-0.flac"
  - "CastPlay: Queuing PLAY"

================================================================================
SECTION 3: FAILED DEVICES - ROOT CAUSE ANALYSIS
================================================================================

3.1 ARYLIC/LINKPLAY SPEAKERS (192.168.1.74, 192.168.1.254)
----------------------------------------------------------
CRITICAL FIRMWARE BUG DISCOVERED

The Arylic/Linkplay speakers have a bug in their RAOP implementation where
they echo back the CLIENT's ports instead of providing SERVER ports.

Test Performed:
  Sent SETUP with: control_port=12345;timing_port=12346
  Arylic returned: control_port=12345;timing_port=12346

Expected Behavior (AirConnect example):
  Sent SETUP with: control_port=56248;timing_port=56249
  AirConnect returned: control_port=58354;timing_port=58355;server_port=58353

Result: UDP audio packets are sent to the wrong ports (client's own ports),
nothing is listening there, so audio goes nowhere.

CONCLUSION: Direct AirPlay to Arylic/Linkplay devices is NOT POSSIBLE due to
firmware bug. Use HTTP API instead (setPlayerCmd:play:{url}).


3.2 AIRPLAY 2 DEVICES (LG Soundbar, Sonos Era 300)
--------------------------------------------------
Both AirPlay 2 devices complete the initial handshake but drop the connection
before audio streaming begins.

LG S80QR (192.168.1.117):
  - GET /info, pair-setup, SETUP all succeed
  - Connection drops during audio streaming phase

Sonos Era 300 (192.168.1.185):
  - GET /info returns proper binary plist
  - pair-pin-start, pair-setup succeed (transient auth)
  - SETUP returns eventPort and timingPort
  - Then: "Control connection lost (None)"
  - Error: OSError: [WinError 121] The semaphore timeout period has expired

CONCLUSION: AirPlay 2 devices require full HomeKit authentication that pyatv
may not fully support for streaming. Consider using native protocols (SoCo for
Sonos) or waiting for pyatv AirPlay 2 improvements.

================================================================================
SECTION 4: PYATV PATCHES REQUIRED
================================================================================

Three patches are required for AirPlay 1 compatibility with AirConnect and
similar non-standard devices. These are implemented in:

  File: app/core/sonorium/pyatv_patches.py

4.1 patch_rtsp_session()
------------------------
Problem: AirConnect returns RTSP responses without CSeq headers
Solution: Match responses to the only pending request when CSeq is missing

4.2 patch_empty_bplist()
------------------------
Problem: Some devices return empty body for GET /info
Solution: Return empty dict instead of raising InvalidFileException

CRITICAL FIX: Must patch BOTH modules:
  - pyatv.support.http.decode_bplist_from_body
  - pyatv.support.rtsp.decode_bplist_from_body

The rtsp module imports this function separately at module load time, so
patching only http.py is insufficient.

4.3 patch_hex_session_id()
--------------------------
Problem: AirConnect returns Session header as hex (e.g., "DEADBEEF")
Solution: Parse hex session IDs with fallback to random

================================================================================
SECTION 5: IMPLEMENTATION REQUIREMENTS
================================================================================

5.1 WINDOWS/DOCKER STANDALONE APP (app/core/sonorium/)
------------------------------------------------------

Files to Modify:
  - streaming.py: Add AirPlay streaming using pyatv
  - network_speakers.py: Already has mDNS discovery for AirPlay

New Files Created:
  - pyatv_patches.py: Already implemented with all three patches

Implementation Steps:
  1. Import and call apply_patches() at startup before any pyatv operations
  2. Add _start_airplay_pyatv() method to StreamingManager
  3. Use pyatv.scan() to discover devices
  4. Use pyatv.connect() and atv.stream.stream_file() for streaming
  5. Detect device type and use appropriate method:
     - Linkplay/Arylic: HTTP API (already implemented)
     - True AirPlay 1: pyatv streaming
     - AirPlay 2: May not work reliably

Code Pattern for Streaming:
```python
from sonorium.pyatv_patches import apply_patches
apply_patches()  # Call once at startup

import pyatv
from pyatv.const import Protocol

async def stream_to_airplay(device_ip, audio_file):
    loop = asyncio.get_event_loop()
    devices = await pyatv.scan(loop, hosts=[device_ip], timeout=10)

    target = None
    for d in devices:
        raop = d.get_service(Protocol.RAOP)
        if raop:
            target = d
            break

    if not target:
        raise Exception("Device not found")

    atv = await pyatv.connect(target, loop)
    try:
        if atv.stream:
            await atv.stream.stream_file(audio_file)
    finally:
        await atv.close()
```


5.2 HOME ASSISTANT ADD-ON (sonorium_addon/sonorium/)
----------------------------------------------------

Current State: The HA addon uses HA's media_player integration, not direct
streaming. However, for standalone speaker support:

Files to Create/Modify:
  - pyatv_patches.py: Copy from app/core/sonorium/ (or share via symlink)
  - streaming.py or new airplay.py: Add AirPlay streaming logic

Considerations:
  1. The HA addon runs in Docker on ARM64 (Raspberry Pi) or x86_64
  2. pyatv is pure Python and works on all platforms
  3. Patches must be applied before any pyatv import
  4. May need to add pyatv to requirements.txt if not already present

Integration Options:
  A. Direct streaming (push audio to speaker)
  B. URL-based streaming (speaker pulls from HA addon's HTTP server)

For Linkplay/Arylic devices, option B with HTTP API is already the best choice.
For true AirPlay devices, option A with pyatv is required.


5.3 DEVICE DETECTION LOGIC
--------------------------

To determine which streaming method to use:

```python
def get_streaming_method(device_properties):
    model = device_properties.get('am', '').lower()

    # AirConnect bridges
    if model in ('airupnp', 'aircast'):
        return 'pyatv'  # Works with patches

    # Arylic/Linkplay - FIRMWARE BUG, use HTTP API
    if 'linkplay' in model or is_linkplay_device(device_name):
        return 'http_api'

    # Check encryption type for AirPlay version
    encryption = device_properties.get('et', '')
    if '4' in encryption:
        return 'airplay2'  # May not work reliably

    return 'pyatv'  # Default to pyatv for AirPlay 1
```

================================================================================
SECTION 6: TEST HARNESS AND DOCUMENTATION
================================================================================

Files Created During Testing:

1. tests/test_airplay_airconnect.py
   - Full test harness for AirConnect development
   - Discovery, connection, and streaming tests
   - Filters to only AirConnect devices
   - Generates test tones for streaming

2. docs/airplay/AIRCONNECT_DEVELOPMENT.md
   - Documentation for using AirConnect as dev environment
   - RTSP protocol flow diagrams
   - Troubleshooting guide
   - Patch descriptions

3. app/core/sonorium/pyatv_patches.py
   - Three patches for AirConnect/AirPlay 1 compatibility
   - apply_patches() function for one-time application
   - is_airconnect_device() helper function

================================================================================
SECTION 7: REMAINING WORK
================================================================================

7.1 IMMEDIATE (Required for AirPlay 1 Support)
----------------------------------------------
[ ] Integrate pyatv_patches.py into Windows app startup
[ ] Add AirPlay streaming method to streaming.py
[ ] Test full Sonorium streaming to Marantz SR5011
[ ] Test full Sonorium streaming via AirConnect

7.2 INVESTIGATION NEEDED
------------------------
[ ] Why generated audio tones not heard on Marantz (real files work)
[ ] Volume control implementation via pyatv
[ ] Graceful handling of connection drops

7.3 FUTURE (AirPlay 2)
----------------------
[ ] Monitor pyatv development for AirPlay 2 improvements
[ ] Consider HomeKit pairing workflow for AirPlay 2 devices
[ ] Alternative: Use native protocols (SoCo for Sonos)

7.4 HA ADDON
------------
[ ] Evaluate whether direct AirPlay streaming is needed in addon
[ ] If needed, port pyatv_patches.py to addon
[ ] Add pyatv to addon requirements if not present
[ ] Test on ARM64 (Raspberry Pi) platform

================================================================================
SECTION 8: DEPENDENCIES
================================================================================

Python Packages Required:
  - pyatv >= 0.14.0 (AirPlay/RAOP protocol)
  - numpy (audio generation for testing)
  - av (PyAV for MP3 encoding)
  - aiohttp (HTTP client for downloading audio)

Already in Core:
  - pyatv (for discovery)
  - numpy
  - av

================================================================================
END OF SUMMARY
================================================================================
