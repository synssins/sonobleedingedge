#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sonos Quick Reference - Common Operations
Demonstrates all essential Sonos operations for Sonorium integration
"""

import soco
import time

# DISCOVERY
# ---------

# Method 1: Discover all Sonos speakers on network
def discover_all_speakers():
    """Scan network for all Sonos speakers (takes 5-10 seconds)"""
    speakers = soco.discover(timeout=5)
    if speakers:
        for speaker in speakers:
            print(f"Found: {speaker.player_name} at {speaker.ip_address}")
    return speakers

# Method 2: Connect to specific IP address
def connect_to_speaker(ip_address):
    """Connect to a specific Sonos speaker by IP address"""
    speaker = soco.SoCo(ip_address)
    return speaker


# DEVICE INFORMATION
# ------------------

def get_device_info(speaker):
    """Get detailed device information"""
    info = speaker.get_speaker_info()
    return {
        'name': info.get('zone_name'),
        'model': info.get('model_name'),
        'model_number': info.get('model_number'),
        'version': info.get('display_version'),
        'serial': info.get('serial_number'),
        'mac': info.get('mac_address'),
        'uid': speaker.uid,
        'ip': speaker.ip_address
    }


# PLAYBACK CONTROL
# ----------------

def play_url(speaker, url, title="Audio Stream"):
    """Play audio from HTTP URL"""
    speaker.play_uri(url, title=title)

def play_url_with_metadata(speaker, url, title, artist="", album=""):
    """Play audio with full metadata"""
    # Create DIDL metadata
    metadata = f'''
    <DIDL-Lite xmlns:dc="http://purl.org/dc/elements/1.1/"
               xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"
               xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/">
        <item id="0" parentID="-1" restricted="true">
            <dc:title>{title}</dc:title>
            <dc:creator>{artist}</dc:creator>
            <upnp:album>{album}</upnp:album>
            <upnp:class>object.item.audioItem.musicTrack</upnp:class>
            <res protocolInfo="http-get:*:audio/mpeg:*">{url}</res>
        </item>
    </DIDL-Lite>
    '''
    speaker.play_uri(url, title=title, meta=metadata)

def stop_playback(speaker):
    """Stop playback"""
    speaker.stop()

def pause_playback(speaker):
    """Pause playback"""
    speaker.pause()

def resume_playback(speaker):
    """Resume playback after pause"""
    speaker.play()


# VOLUME CONTROL
# --------------

def set_volume(speaker, volume):
    """Set volume (0-100)"""
    speaker.volume = volume

def get_volume(speaker):
    """Get current volume"""
    return speaker.volume

def mute(speaker):
    """Mute speaker"""
    speaker.mute = True

def unmute(speaker):
    """Unmute speaker"""
    speaker.mute = False

def is_muted(speaker):
    """Check if speaker is muted"""
    return speaker.mute


# PLAYBACK STATE
# --------------

def get_playback_state(speaker):
    """Get current playback state"""
    transport = speaker.get_current_transport_info()
    return transport['current_transport_state']  # PLAYING, STOPPED, PAUSED, etc.

def is_playing(speaker):
    """Check if speaker is currently playing"""
    return get_playback_state(speaker) == 'PLAYING'

def get_current_track(speaker):
    """Get current track information"""
    track = speaker.get_current_track_info()
    return {
        'title': track.get('title', ''),
        'artist': track.get('artist', ''),
        'album': track.get('album', ''),
        'uri': track.get('uri', ''),
        'position': track.get('position', '0:00:00'),
        'duration': track.get('duration', '0:00:00')
    }


# GROUP OPERATIONS
# ----------------

def get_group_info(speaker):
    """Get zone group information"""
    group = speaker.group
    return {
        'coordinator': group.coordinator.player_name if group.coordinator else None,
        'members': [m.player_name for m in group.members],
        'is_coordinator': speaker.is_coordinator
    }

def join_group(speaker, master_speaker):
    """Join this speaker to another speaker's group"""
    speaker.join(master_speaker)

def leave_group(speaker):
    """Remove this speaker from its group"""
    speaker.unjoin()


# EXAMPLE USAGE FOR SONORIUM
# ---------------------------

def sonorium_integration_example():
    """Example of how to integrate Sonos with Sonorium"""

    # 1. Connect to Sonos speaker
    speaker = soco.SoCo('192.168.1.185')
    print(f"Connected to {speaker.player_name}")

    # 2. Get device info
    info = get_device_info(speaker)
    print(f"Device: {info['name']} ({info['model']})")

    # 3. Set reasonable volume
    set_volume(speaker, 20)
    print(f"Volume set to {get_volume(speaker)}")

    # 4. Play Sonorium stream
    # In real implementation, this would be:
    # stream_url = f"http://{sonorium_ip}:{sonorium_port}/stream/{session_id}"
    stream_url = "http://192.168.1.100:8080/sonorium/stream"  # Example
    play_url(speaker, stream_url, title="Sonorium - Forest Theme")

    # 5. Monitor playback
    for i in range(5):
        state = get_playback_state(speaker)
        print(f"State: {state}")
        time.sleep(1)

    # 6. Stop when done
    stop_playback(speaker)
    print("Stopped playback")


# SONORIUM HTTP SERVER REQUIREMENTS
# ----------------------------------
"""
For Sonos integration, Sonorium's HTTP server must:

1. Serve audio at a stable URL:
   http://{ip}:{port}/stream/{session_id}

2. Set proper HTTP headers:
   Content-Type: audio/wav  (or audio/mpeg, audio/flac, etc.)
   Accept-Ranges: bytes     (optional, for seeking)

3. Stream format options:
   - WAV: Confirmed working, best compatibility
   - MP3: Works with proper headers
   - FLAC: Supported, good for quality
   - AAC: Supported

4. Handle HTTP range requests (optional but recommended)

5. Keep stream alive while speaker is connected

Example Flask endpoint:

@app.route('/stream/<session_id>')
def stream_audio(session_id):
    def generate():
        # Your audio generation code here
        while True:
            audio_chunk = get_next_audio_chunk(session_id)
            if audio_chunk:
                yield audio_chunk
            else:
                break

    return Response(
        generate(),
        mimetype='audio/wav',
        headers={
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'no-cache'
        }
    )
"""


if __name__ == "__main__":
    # Quick test
    print("Sonos Quick Reference")
    print("=" * 50)
    print()
    print("Key Operations:")
    print("1. Discovery: soco.discover() or soco.SoCo(ip)")
    print("2. Play: speaker.play_uri(url, title)")
    print("3. Volume: speaker.volume = 0-100")
    print("4. State: speaker.get_current_transport_info()")
    print("5. Stop: speaker.stop()")
    print()
    print("For full examples, see functions above")
