================================================================================
DETAILED FEATURE PARITY: THEME/PRESET/CYCLING/CROSSFADE
December 22, 2025
================================================================================

EXECUTIVE SUMMARY
================================================================================

NO - Windows/Docker and HA Addon do NOT have feature parity for audio features.

The codebases have DIVERGED. Each has different bug fixes and features that
the other is missing.

================================================================================
CORE ARCHITECTURE DIFFERENCES
================================================================================

WINDOWS/DOCKER (app/core/sonorium/core/):
-----------------------------------------
Files:
  - channel.py
  - __init__.py

That's it. Very simple single-channel architecture.


HA ADDON (sonorium_addon/sonorium/core/):
-----------------------------------------
Files:
  - channel.py
  - cycle_manager.py      <-- MISSING FROM CORE
  - group_manager.py      <-- MISSING FROM CORE
  - session_manager.py    <-- MISSING FROM CORE
  - state.py              <-- MISSING FROM CORE
  - theme_metadata.py     <-- MISSING FROM CORE
  - __init__.py

Much more complex multi-session, multi-zone architecture.


================================================================================
RECORDING.PY DIFFERENCES (AUDIO PLAYBACK ENGINE)
================================================================================

FEATURES IN WINDOWS/DOCKER ONLY:
--------------------------------
1. random_start parameter
   - Allows starting tracks at random positions (0-80% of track)
   - Prevents all tracks from starting at the beginning together
   - Code: get_stream(exclusion_coordinator, random_start=False)

2. Better error handling
   - Retry logic with max_errors counter
   - Yields silence chunks when audio fails to decode
   - Graceful degradation instead of crashing

3. Cleaner PyAV import handling
   - try/except with helpful error message


FEATURES IN HA ADDON ONLY:
--------------------------
1. Simpler, cleaner code (less error handling overhead)

2. May have different crossfade behavior (needs investigation)


================================================================================
GIT COMMIT HISTORY ANALYSIS
================================================================================

HA ADDON recording.py commits (most recent first):
--------------------------------------------------
a8f13ac Replace HACO with paho-mqtt for HA entity management
f80a010 Fix sparse playback and exclusive tracks playing immediately at theme start
bab7dc8 Add exclusive playback for tracks (mutual exclusion group)
4b5ac85 Add per-track playback mode and volume controls
08c2ce3 Add configurable short_file_threshold per theme
37a434d Add sparse playback for short audio files
174016e Reduce loop crossfade and improve track mixer UI (v1.1.2-dev)
4fed186 Implement track presence control (v1.1.1-dev)
96c2681 fix: Copy recording.py with crossfade into addon folder


WINDOWS/DOCKER recording.py commits (most recent first):
---------------------------------------------------------
883cbeb Fix sparse playback playing all tracks at stream start
503a01b Add standalone Windows app structure

KEY OBSERVATION:
The HA addon has commit f80a010 "Fix sparse playback and exclusive tracks
playing immediately at theme start" which is NOT in the Windows/Docker core.

The Windows/Docker core has commit 883cbeb which is a DIFFERENT fix for a
similar issue.

================================================================================
SPECIFIC BUG FIX STATUS
================================================================================

| Bug/Feature                              | Windows/Docker | HA Addon |
|------------------------------------------|----------------|----------|
| Sparse playback basic                    | YES            | YES      |
| Exclusive tracks                         | YES            | YES      |
| Presence-based playback                  | YES            | YES      |
| Fix: tracks playing immediately at start | PARTIAL        | YES      |
| Random start position                    | YES            | NO       |
| Theme cycling                            | NO             | YES      |
| Multi-session support                    | NO             | YES      |
| Group/zone management                    | NO             | YES      |
| Error recovery with silence fallback     | YES            | NO       |


================================================================================
CROSSFADE STATUS
================================================================================

Both have CrossfadeRecordingStream class.
Both have crossfade logic for seamless looping.

However, the implementations may differ in details. The Windows/Docker version
passes random_start to CrossfadeRecordingStream, which the HA addon does not.


================================================================================
THEME CYCLING STATUS
================================================================================

WINDOWS/DOCKER: NO THEME CYCLING
- No cycle_manager.py
- Single theme playback only
- Manual theme switching via API

HA ADDON: FULL THEME CYCLING
- cycle_manager.py implements automatic theme rotation
- Configurable cycle intervals
- Supports multiple sessions with independent cycling


================================================================================
PRESET STATUS
================================================================================

Both have preset support in theme.py, but:
- Windows/Docker: Basic preset loading
- HA Addon: Full preset management with MQTT entities


================================================================================
RECOMMENDATIONS
================================================================================

TO ACHIEVE FEATURE PARITY:

1. SYNC RECORDING.PY BUG FIXES
   - Port the "Fix sparse playback and exclusive tracks playing immediately"
     fix from HA addon to Windows/Docker
   - Port the random_start feature from Windows/Docker to HA addon
   - Port the error recovery logic from Windows/Docker to HA addon

2. ADD THEME CYCLING TO WINDOWS/DOCKER
   - Port cycle_manager.py from HA addon
   - This is a significant feature gap

3. CONSIDER SESSION MANAGEMENT
   - Windows/Docker currently single-session only
   - HA addon has full multi-session support
   - May or may not want this in standalone app

4. UNIFY CODEBASE?
   - The codebases have diverged significantly
   - Consider extracting shared audio engine to common library
   - Or pick one as "source of truth" and sync features

================================================================================
