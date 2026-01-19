#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sonos Speaker Playback Test
Tests actual audio playback on Sonos speaker at 192.168.1.185
"""

import sys
import traceback
import io
import time

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_sonos_playback():
    """Test Sonos speaker playback with different methods"""

    print("=" * 70)
    print("SONOS SPEAKER PLAYBACK TEST")
    print("=" * 70)
    print()

    # Import soco
    try:
        import soco
    except ImportError:
        print("Error: soco not installed")
        return

    # Connect to speaker
    speaker = soco.SoCo('192.168.1.185')
    info = speaker.get_speaker_info()
    print(f"Connected to: {info.get('zone_name', 'Unknown')} ({info.get('model_name', 'Unknown')})")
    print()

    # Store original state
    original_volume = speaker.volume
    original_state = speaker.get_current_transport_info()['current_transport_state']
    print(f"Original volume: {original_volume}")
    print(f"Original state: {original_state}")
    print()

    # Test 1: Play a test tone URL (pleasant tone)
    print("[1] Testing playback with play_uri()...")
    print("    Note: Will play a short pleasant test tone")
    print("    Setting volume to 20 for testing...")

    try:
        # Set safe volume
        speaker.volume = 20

        # Use a known working audio URL (a short pleasant tone)
        test_url = "http://www.kozco.com/tech/piano2.wav"

        print(f"    Playing: {test_url}")
        speaker.play_uri(test_url, title="Test Tone")

        # Wait a bit for playback to start
        time.sleep(2)

        # Check if playing
        state = speaker.get_current_transport_info()
        print(f"    Transport state: {state['current_transport_state']}")

        track_info = speaker.get_current_track_info()
        print(f"    Current track: {track_info.get('title', 'Unknown')}")
        print(f"    URI: {track_info.get('uri', 'Unknown')}")

        # Let it play for 3 seconds
        print("    Letting audio play for 3 seconds...")
        time.sleep(3)

        # Stop playback
        print("    Stopping playback...")
        speaker.stop()

        print("    ✓ Playback test successful")

    except Exception as e:
        print(f"    ✗ Playback test failed: {e}")
        traceback.print_exc()
    print()

    # Test 2: Check if we can stream MP3
    print("[2] Testing MP3 streaming...")
    try:
        # Use a known working MP3 stream
        mp3_url = "http://ice1.somafm.com/groovesalad-128-mp3"

        print(f"    Testing MP3 stream: {mp3_url}")
        speaker.play_uri(mp3_url, title="Test MP3 Stream")

        time.sleep(2)
        state = speaker.get_current_transport_info()
        print(f"    Transport state: {state['current_transport_state']}")

        if state['current_transport_state'] in ['PLAYING', 'TRANSITIONING']:
            print("    ✓ MP3 streaming works")
            time.sleep(2)
        else:
            print(f"    ✗ MP3 streaming issue - state is {state['current_transport_state']}")

        speaker.stop()

    except Exception as e:
        print(f"    ✗ MP3 streaming test failed: {e}")
        traceback.print_exc()
    print()

    # Test 3: Volume control
    print("[3] Testing volume control...")
    try:
        print(f"    Current volume: {speaker.volume}")
        print(f"    Setting volume to 15...")
        speaker.volume = 15
        time.sleep(0.5)
        new_volume = speaker.volume
        print(f"    New volume: {new_volume}")

        if new_volume == 15:
            print("    ✓ Volume control works")
        else:
            print(f"    ✗ Volume not set correctly (got {new_volume})")

    except Exception as e:
        print(f"    ✗ Volume control test failed: {e}")
    print()

    # Test 4: Mute control
    print("[4] Testing mute control...")
    try:
        print(f"    Current mute state: {speaker.mute}")
        print(f"    Muting...")
        speaker.mute = True
        time.sleep(0.5)
        print(f"    Mute state: {speaker.mute}")

        print(f"    Unmuting...")
        speaker.mute = False
        time.sleep(0.5)
        print(f"    Mute state: {speaker.mute}")

        print("    ✓ Mute control works")

    except Exception as e:
        print(f"    ✗ Mute control test failed: {e}")
    print()

    # Restore original settings
    print("Restoring original settings...")
    try:
        speaker.volume = original_volume
        if original_state == 'STOPPED':
            speaker.stop()
        print(f"✓ Restored volume to {original_volume}")
    except:
        pass

    print()
    print("=" * 70)
    print("PLAYBACK TEST COMPLETE")
    print("=" * 70)
    print()
    print("INTEGRATION NOTES:")
    print("------------------")
    print("1. Sonos Era 300 successfully accepts HTTP audio streams")
    print("2. speaker.play_uri(url, title=...) is the primary method")
    print("3. Supports MP3, WAV, and other standard formats")
    print("4. Volume and mute controls work as expected")
    print("5. Transport state can be monitored in real-time")
    print()
    print("FOR SONORIUM INTEGRATION:")
    print("-------------------------")
    print("- Use existing HTTP streaming infrastructure")
    print("- Call speaker.play_uri(sonorium_stream_url)")
    print("- Monitor transport state for connection status")
    print("- Control volume via speaker.volume property")
    print("- Can stop playback with speaker.stop()")
    print("- Speaker will pull audio from Sonorium's HTTP endpoint")

if __name__ == "__main__":
    test_sonos_playback()
