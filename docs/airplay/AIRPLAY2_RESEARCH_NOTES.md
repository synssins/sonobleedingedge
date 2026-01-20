AIRPLAY RESEARCH NOTES
======================
Created: 2024-12-19
Purpose: Document AirPlay 2 findings for Sonorium


SONOS AIRPLAY 2 TEST RESULTS
============================

Device Tested: Sonos Era 300 at 192.168.1.185

Discovery: SUCCESS
- mDNS discovery works
- Device found as "Office"
- AirPlay and RAOP services on port 7000
- Model: Era 300, Manufacturer: Sonos

Connection: PARTIAL
- RTSP handshake completes
- SETUP phase works
- Keys exchanged for encryption
- Then connection times out / drops

Streaming: FAILED
- stream_file() times out after ~18 seconds
- No audio plays on speaker


ROOT CAUSE: pyatv DOESN'T SUPPORT AIRPLAY 2 STREAMING
=====================================================

From pyatv issue #1259 (https://github.com/postlund/pyatv/issues/1259):

"The AirPlay receiver in question is an AirPlay 2-only receiver, so it
doesn't support the AirPlay 1 protocol which is the only one implemented
in pyatv."

Key points:
1. Sonos (and many modern speakers) are AirPlay 2-ONLY devices
2. pyatv only implements AirPlay 1 for audio streaming
3. AirPlay 2 requires HAP (HomeKit) authentication with full encryption
4. pyatv has NOT implemented full AirPlay 2 streaming support
5. No workaround exists - this is a fundamental library limitation
6. Volume control works (uses different protocol), but streaming doesn't


WHAT WORKS vs WHAT DOESN'T
==========================

Works with pyatv:
- Device discovery (mDNS)
- Volume control
- Basic device info
- Streaming to AirPlay 1 devices (older receivers)

Doesn't work with pyatv:
- Audio streaming to AirPlay 2-only devices (Sonos, HomePod, modern speakers)
- PlayURL to AirPlay 2 devices
- stream_file() to AirPlay 2 devices


ALTERNATIVE LIBRARIES RESEARCHED
================================

1. pyatv (current)
   - Most complete Python AirPlay library
   - AirPlay 1 streaming only
   - No full AirPlay 2 sender support

2. openairplay/airplay2-receiver
   - AirPlay 2 RECEIVER implementation
   - Makes your device receive streams
   - Not useful for sending TO speakers

3. open-airplay
   - Collection of libraries
   - No active Python AirPlay 2 sender

Conclusion: No Python library exists for sending AirPlay 2 streams


SOLUTION FOR SONOS: USE SOCO (ALREADY IMPLEMENTED)
=================================================

We already solved Sonos streaming in v1.2.17:
- SoCo library with force_radio=True
- Speaker fetches audio from HTTP stream URL
- IP discovered from HA device registry configuration_url
- Works perfectly!

This is the correct approach for Sonos because:
1. SoCo speaks native Sonos/UPnP protocol
2. No AirPlay 2 encryption issues
3. Simple HTTP pull model (speaker fetches stream)
4. HA can still control pause/stop/volume


AIRPLAY STATUS FOR SONORIUM
===========================

For Sonos speakers:
  -> Use SoCo (implemented, working)

For AirPlay 1 devices (AirPort Express, older receivers):
  -> pyatv may work, needs testing
  -> Try devices with 'et': '0,3,5' (includes type 3 = legacy)

For AirPlay 2-only devices (HomePod, modern speakers):
  -> No Python solution currently exists
  -> Would need native implementation or different approach


NEXT STEPS IF AIRPLAY 2 IS NEEDED
=================================

Options:
1. Wait for pyatv to implement AirPlay 2 (uncertain timeline)
2. Use platform-specific tools (not portable)
3. Use HTTP streaming where supported (like Sonos/SoCo)
4. Contribute to pyatv AirPlay 2 implementation (significant work)

For Sonorium, the practical approach is:
- Use SoCo for Sonos (done)
- Use pyatv for AirPlay 1 devices (Arylic/Linkplay etc)
- Document that AirPlay 2-only devices need alternate protocols


REFERENCES
==========

- pyatv issue #1259: https://github.com/postlund/pyatv/issues/1259
- pyatv FAQ: https://pyatv.dev/support/faq/
- pyatv streaming docs: https://pyatv.dev/development/stream/
- Sonos AirPlay support: https://support.sonos.com/en/article/stream-airplay-audio-to-sonos
