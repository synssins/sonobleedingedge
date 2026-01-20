================================================================================
SONORIUM FEATURE PARITY ANALYSIS
December 22, 2025
================================================================================

SUMMARY
================================================================================

Component            | Version      | Status
---------------------|--------------|------------------------------------------
Windows App          | v0.2.48-dev  | LATEST - Has all features
Docker Container     | v0.2.48-dev  | SAME CODE as Windows (shares app/core/)
HA Addon             | v1.2.42-dev  | SEPARATE CODEBASE - Different architecture

================================================================================
WINDOWS APP & DOCKER (app/core/sonorium/) - FEATURE COMPLETE
================================================================================

Both share the SAME core code. Docker's Dockerfile copies from core/sonorium/.

SPEAKER PROTOCOLS IMPLEMENTED:
--------------------------------------------------------------------------------
Protocol         | Discovery          | Streaming           | Notes
-----------------|--------------------|--------------------|--------------------
DLNA             | SSDP               | async-upnp-client  | Pull model
Chromecast       | pychromecast       | pychromecast       | Pull model
Sonos            | soco               | soco               | Pull, force_radio
AirPlay          | pyatv/mDNS         | pyatv              | Push model (RAOP)
HEOS             | SSDP/mDNS/Telnet   | Telnet CLI         | Pull, port 1255
Linkplay/Arylic  | mDNS               | HTTP API           | Pull, setPlayerCmd

KEY FILES:
- network_speakers.py  - Discovery for all protocols (~1400 lines)
- streaming.py         - Streaming for all protocols (~950 lines)
- pyatv_patches.py     - AirPlay 1 compatibility patches (NEW)

DIFFERENCES BETWEEN WINDOWS & DOCKER:
--------------------------------------------------------------------------------
Feature                    | Windows | Docker
---------------------------|---------|--------
Local audio (sounddevice)  | YES     | NO (not included in requirements)
GUI (PyQt6)                | YES     | NO (headless)
All network speakers       | YES     | YES

================================================================================
HA ADDON (sonorium_addon/) - SEPARATE CODEBASE
================================================================================

The HA Addon is a COMPLETELY DIFFERENT architecture.

HOW IT WORKS:
- Delegates to Home Assistant - Uses HA's media_player.play_media service
- No direct speaker control - Relies on HA's integrations (HEOS, Sonos, etc.)
- Exception: Sonos - Has direct soco support for multi-room sync

WHAT'S MISSING (vs Core):
--------------------------------------------------------------------------------
Feature                      | Core (Windows/Docker) | HA Addon
-----------------------------|----------------------|-------------------------
Direct DLNA streaming        | YES                  | NO - Uses HA integration
Direct Chromecast streaming  | YES                  | NO - Uses HA integration
Direct AirPlay streaming     | YES (pyatv)          | NO - Uses HA integration
Direct HEOS streaming        | YES (Telnet CLI)     | NO - Uses HA integration
Direct Linkplay/Arylic       | YES (HTTP API)       | NO - Uses HA integration
pyatv_patches.py             | YES                  | NO - Not present
Speaker discovery            | YES (own impl)       | NO - Uses HA registry

WHAT HA ADDON HAS THAT CORE DOESN'T:
- MQTT entity discovery for HA dashboards
- Session/Channel management for multi-zone
- Theme cycling automation
- HA supervisor integration
- Floor/area/speaker hierarchy

================================================================================
CONCLUSION
================================================================================

1. WINDOWS/DOCKER ARE FEATURE-COMPLETE AND IN SYNC
   - They share app/core/sonorium/
   - Both have HEOS, AirPlay, DLNA, Sonos, Chromecast, Linkplay support
   - Docker just lacks local audio output (intentional for headless container)

2. HA ADDON IS INTENTIONALLY DIFFERENT
   - Leverages Home Assistant's speaker integrations
   - Does NOT implement direct protocols (except Sonos multi-room)
   - This is by design since HA already has mature integrations

3. IF YOU WANT NEW AIRPLAY PATCHES IN HA ADDON:
   - Would need to port pyatv_patches.py to the addon
   - Would need to add direct AirPlay streaming code
   - This would be a significant architectural change
   - Currently HA addon relies on HA's AirPlay integration

================================================================================
RECOMMENDATION
================================================================================

The Windows/Docker standalone app is the most feature-complete for direct
speaker control. The HA Addon is designed to work within Home Assistant's
ecosystem and delegates speaker control to HA's integrations.

For users who want:
- Direct speaker control without HA -> Use Windows App or Docker
- Integration with HA dashboards/automations -> Use HA Addon

================================================================================
