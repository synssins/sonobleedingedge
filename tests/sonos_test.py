#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sonos Speaker Connectivity Test
Tests connection to Sonos speaker at 192.168.1.185
"""

import sys
import traceback
import io

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_sonos_connectivity():
    """Test Sonos speaker connectivity and capabilities"""

    print("=" * 70)
    print("SONOS SPEAKER CONNECTIVITY TEST")
    print("=" * 70)
    print()

    # Test 1: Import soco
    print("[1] Testing SoCo import...")
    try:
        import soco
        print(f"    ✓ SoCo version: {soco.__version__}")
    except ImportError as e:
        print(f"    ✗ Failed to import soco: {e}")
        print("    Installing soco...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "soco"])
        import soco
        print(f"    ✓ SoCo installed and imported: {soco.__version__}")
    print()

    # Test 2: Connect to specific device
    print("[2] Connecting to Sonos speaker at 192.168.1.185...")
    try:
        speaker = soco.SoCo('192.168.1.185')
        print(f"    ✓ Connected to device")
    except Exception as e:
        print(f"    ✗ Failed to connect: {e}")
        traceback.print_exc()
        return
    print()

    # Test 3: Get device info
    print("[3] Getting device information...")
    try:
        info = speaker.get_speaker_info()
        print(f"    Device Name:     {info.get('zone_name', 'Unknown')}")
        print(f"    Model:           {info.get('model_name', 'Unknown')}")
        print(f"    Model Number:    {info.get('model_number', 'Unknown')}")
        print(f"    Display Version: {info.get('display_version', 'Unknown')}")
        print(f"    Hardware:        {info.get('hardware_version', 'Unknown')}")
        print(f"    Serial:          {info.get('serial_number', 'Unknown')}")
        print(f"    MAC Address:     {info.get('mac_address', 'Unknown')}")
        print(f"    UID:             {speaker.uid}")
    except Exception as e:
        print(f"    ✗ Failed to get device info: {e}")
        traceback.print_exc()
    print()

    # Test 4: Check current playback state
    print("[4] Checking current playback state...")
    try:
        state = speaker.get_current_transport_info()
        print(f"    Transport State: {state.get('current_transport_state', 'Unknown')}")
        print(f"    Transport Status: {state.get('current_transport_status', 'Unknown')}")
        print(f"    Speed:           {state.get('current_speed', 'Unknown')}")
    except Exception as e:
        print(f"    ✗ Failed to get transport state: {e}")
        traceback.print_exc()
    print()

    # Test 5: Get volume
    print("[5] Checking volume settings...")
    try:
        volume = speaker.volume
        muted = speaker.mute
        print(f"    Volume:          {volume}")
        print(f"    Muted:           {muted}")
    except Exception as e:
        print(f"    ✗ Failed to get volume: {e}")
        traceback.print_exc()
    print()

    # Test 6: Get current track info (if playing)
    print("[6] Getting current track info...")
    try:
        track = speaker.get_current_track_info()
        print(f"    Title:           {track.get('title', 'N/A')}")
        print(f"    Artist:          {track.get('artist', 'N/A')}")
        print(f"    Album:           {track.get('album', 'N/A')}")
        print(f"    URI:             {track.get('uri', 'N/A')}")
        print(f"    Position:        {track.get('position', 'N/A')}")
        print(f"    Duration:        {track.get('duration', 'N/A')}")
    except Exception as e:
        print(f"    ✗ Failed to get track info: {e}")
        traceback.print_exc()
    print()

    # Test 7: Check zone grouping
    print("[7] Checking zone group information...")
    try:
        group = speaker.group
        if group:
            print(f"    Group Coordinator: {group.coordinator.player_name if group.coordinator else 'None'}")
            print(f"    Group Members:     {len(group.members)}")
            for member in group.members:
                print(f"      - {member.player_name} ({member.ip_address})")
        else:
            print(f"    Not in a group")
    except Exception as e:
        print(f"    ✗ Failed to get group info: {e}")
        traceback.print_exc()
    print()

    # Test 8: Test basic command (get speaker info again as safe test)
    print("[8] Testing basic command response...")
    try:
        # Just test that we can execute a command
        speaker.get_speaker_info()
        print(f"    ✓ Device responds to commands")
    except Exception as e:
        print(f"    ✗ Device did not respond: {e}")
        traceback.print_exc()
    print()

    # Test 9: Discovery test
    print("[9] Testing network discovery...")
    try:
        print("    Discovering Sonos devices on network (this may take 5-10 seconds)...")
        devices = soco.discover(timeout=10)
        if devices:
            print(f"    ✓ Found {len(devices)} Sonos device(s):")
            for device in devices:
                try:
                    name = device.player_name
                    print(f"      - {name} ({device.ip_address})")
                except:
                    print(f"      - Unknown ({device.ip_address})")
        else:
            print(f"    ✗ No Sonos devices discovered")
    except Exception as e:
        print(f"    ✗ Discovery failed: {e}")
        traceback.print_exc()
    print()

    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_sonos_connectivity()
