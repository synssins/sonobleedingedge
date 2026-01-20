================================================================================
HA ADDON CORE FILES - WHAT THEY DO
================================================================================

These files exist in sonorium_addon/sonorium/core/ but NOT in
app/core/sonorium/core/ (Windows/Docker standalone).

================================================================================
1. CYCLE_MANAGER.PY - Automatic Theme Rotation
================================================================================

PURPOSE:
Automatically changes themes on a timer while playing.

FEATURES:
- Background task monitors all playing sessions
- Changes theme every N minutes (configurable per session)
- Supports sequential or random theme selection
- Can limit to specific themes or use all themes
- Resets timer when manually changing theme
- Crossfades between themes (no audio gap)

EXAMPLE USE CASE:
"Play random ambient themes in the living room, switching every 30 minutes"

KEY SETTINGS:
- enabled: true/false
- interval_minutes: how often to change (e.g., 30)
- randomize: true = random order, false = sequential
- theme_ids: optional list to limit which themes are cycled

WINDOWS/DOCKER HAS: NOTHING EQUIVALENT
- Single theme only, manual switching via API

================================================================================
2. SESSION_MANAGER.PY - Multi-Zone Playback Control
================================================================================

PURPOSE:
Manages multiple simultaneous playback sessions, each with its own theme,
speakers, volume, and settings.

FEATURES:
- Create/update/delete sessions
- Each session = one theme playing to one set of speakers
- Multiple sessions can run simultaneously on different channels
- Auto-naming based on speaker selection (floor, area, or speaker name)
- Preset application (applies track settings to themes)
- Channel-based streaming (assigns audio channels to sessions)
- Seamless theme crossfade when changing themes mid-playback
- Volume control per session
- Play/pause/stop per session
- Live speaker changes (add/remove speakers while playing)

EXAMPLE USE CASE:
"Session 1: 'Forest Rain' in Bedroom at 30%"
"Session 2: 'Ocean Waves' in Living Room at 50%"
"Session 3: 'Fireplace' in Kitchen at 40%"
All playing simultaneously, independently controlled.

WINDOWS/DOCKER HAS: SINGLE SESSION ONLY
- One theme, one set of speakers
- No multi-zone simultaneous playback

================================================================================
3. GROUP_MANAGER.PY - Saved Speaker Configurations
================================================================================

PURPOSE:
Save and reuse speaker selection configurations.

FEATURES:
- Create named speaker groups (e.g., "Downstairs", "Bedroom Level")
- Include by: floor, area, or individual speakers
- Exclude specific areas or speakers from the group
- Reuse across multiple sessions
- "Save as Group" from ad-hoc selection

EXAMPLE USE CASE:
- Group "Bedroom Level": All speakers on floor 2
- Group "Party Mode": Living Room + Kitchen + Dining (exclude Office)
- Group "Master Suite": Master Bedroom + Master Bath

SPEAKER RESOLUTION:
- include_floors: ["floor_2"] -> all speakers on floor 2
- include_areas: ["living_room", "kitchen"] -> speakers in those areas
- include_speakers: ["media_player.office_echo"] -> specific devices
- exclude_areas: ["bathroom"] -> remove bathroom from selection
- exclude_speakers: ["media_player.old_speaker"] -> remove specific device

WINDOWS/DOCKER HAS: NOTHING EQUIVALENT
- Direct speaker selection only, not saved/reusable

================================================================================
4. STATE.PY - Persistent State Storage
================================================================================

PURPOSE:
Data models and persistence for all session/group state.

FEATURES:
- Session model with all settings
- SpeakerGroup model
- SpeakerSelection model (for ad-hoc selections)
- CycleConfig model (theme cycling settings)
- Settings model (app defaults)
- JSON persistence to disk
- Survives restarts

DATA MODELS:
- Session: id, name, theme_id, preset_id, speaker_group_id, volume,
           is_playing, cycle_config, created_at, last_played
- SpeakerGroup: id, name, icon, include/exclude floors/areas/speakers
- CycleConfig: enabled, interval_minutes, randomize, theme_ids

WINDOWS/DOCKER HAS: config.py
- Simpler config storage, no multi-session state

================================================================================
5. THEME_METADATA.PY - Theme/Preset Information Cache
================================================================================

PURPOSE:
Manages theme metadata and presets from metadata.json files.

FEATURES:
- Scans theme folders for metadata.json
- Caches theme info (name, description, category, etc.)
- Manages presets (saved track configurations per theme)
- UUID-based theme identification
- Folder-to-ID mapping

PRESETS:
Each theme can have multiple presets that save:
- Which tracks are enabled/muted
- Volume per track
- Presence per track
- Playback mode per track
- Exclusive flag per track

EXAMPLE:
Theme "Forest" might have presets:
- "Dawn": birds loud, rain quiet
- "Storm": rain loud, thunder, birds off
- "Night": crickets, owl, no birds

WINDOWS/DOCKER HAS: theme.py
- Basic theme loading, simpler preset handling

================================================================================
6. CHANNEL.PY - Audio Channel Management
================================================================================

PURPOSE:
Manages audio streaming channels for multi-session support.

FEATURES:
- Multiple audio channels (channel1, channel2, etc.)
- Each channel generates independent audio stream
- Sessions are assigned to channels
- Seamless crossfade when changing themes on a channel
- Channel pooling (reuse channels when sessions stop)

WHY CHANNELS:
- Each session needs its own audio stream
- Speakers pull from different URLs (/stream/channel1, /stream/channel2)
- Allows different themes on different speaker groups simultaneously

WINDOWS/DOCKER HAS: channel.py
- Exists but simpler, single-channel focused

================================================================================
SUMMARY: WHAT WINDOWS/DOCKER IS MISSING
================================================================================

| Feature                    | HA Addon | Windows/Docker |
|----------------------------|----------|----------------|
| Theme Cycling (auto)       | YES      | NO             |
| Multi-Session Playback     | YES      | NO             |
| Saved Speaker Groups       | YES      | NO             |
| Floor/Area/Speaker Hierarchy| YES     | NO             |
| Per-Session Presets        | YES      | PARTIAL        |
| Persistent State Store     | YES      | SIMPLER        |
| Live Speaker Changes       | YES      | NO             |
| Auto-Naming Sessions       | YES      | NO             |

================================================================================
EFFORT TO PORT TO WINDOWS/DOCKER
================================================================================

LOW EFFORT:
- cycle_manager.py (standalone, could work with simple session)

MEDIUM EFFORT:
- group_manager.py (needs speaker hierarchy from HA)
- theme_metadata.py (mostly standalone)

HIGH EFFORT:
- session_manager.py (deep integration with channels, state, HA)
- state.py (new data models, migration needed)

The session_manager is tightly integrated with Home Assistant's registry
for speaker discovery and media control. Porting it would require either:
1. Creating an equivalent speaker registry for standalone
2. Simplifying to direct speaker control (losing HA features)

================================================================================
