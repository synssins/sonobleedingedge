#!/usr/bin/env python3
"""
Arylic Speaker Streaming Test

Tests audio streaming to Arylic/Linkplay speakers using their native HTTP API.
This bypasses pyatv and uses the device's built-in streaming capabilities.

The Arylic HTTP API supports:
- Direct URL playback (DLNA-style)
- M3U stream playback
- Various input sources

This test verifies we can stream audio to the speaker without needing
the full AirPlay/RAOP implementation.

Usage:
    python tests/test_arylic_streaming.py
"""

import asyncio
import sys
import time
from typing import Optional

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

# Test configuration
OFFICE_SPEAKER_IP = "192.168.1.74"
OFFICE_SPEAKER_NAME = "Office_C97a"

# Test audio URLs (public, royalty-free streams)
TEST_STREAMS = [
    {
        "name": "SomaFM Drone Zone",
        "url": "https://ice2.somafm.com/dronezone-128-mp3",
        "type": "mp3"
    },
    {
        "name": "SomaFM Space Station",
        "url": "https://ice2.somafm.com/spacestation-128-mp3",
        "type": "mp3"
    },
    {
        "name": "Ambient Sleeping Pill",
        "url": "http://radio.stereoscenic.com/asp-s",
        "type": "mp3"
    }
]


class ArylicAPI:
    """Async wrapper for Arylic HTTP API with streaming support."""

    def __init__(self, host: str):
        self.host = host
        self.base_url = f"http://{host}/httpapi.asp"

    async def _request(self, command: str, timeout: float = 5.0) -> str:
        """Make an HTTP request to the device."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command={command}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return await resp.text()
            except Exception as e:
                return f"ERROR: {e}"

    async def get_status(self) -> dict:
        """Get device status."""
        import json
        text = await self._request("getStatusEx")
        try:
            return json.loads(text)
        except:
            return {"raw": text, "error": "Not JSON"}

    async def get_player_status(self) -> dict:
        """Get playback status."""
        import json
        text = await self._request("getPlayerStatus")
        try:
            return json.loads(text)
        except:
            return {"raw": text, "error": "Not JSON"}

    async def play_url(self, url: str) -> bool:
        """Play audio from URL."""
        # URL encode the stream URL
        import urllib.parse
        encoded_url = urllib.parse.quote(url, safe='')
        result = await self._request(f"setPlayerCmd:play:{encoded_url}")
        return "OK" in result.upper() or result.strip() == ""

    async def play_m3u(self, url: str) -> bool:
        """Play M3U stream URL."""
        import urllib.parse
        encoded_url = urllib.parse.quote(url, safe='')
        result = await self._request(f"setPlayerCmd:m3u:play:{encoded_url}")
        return "OK" in result.upper() or result.strip() == ""

    async def stop(self) -> bool:
        """Stop playback."""
        result = await self._request("setPlayerCmd:stop")
        return "OK" in result.upper() or result.strip() == ""

    async def pause(self) -> bool:
        """Pause playback."""
        result = await self._request("setPlayerCmd:pause")
        return "OK" in result.upper() or result.strip() == ""

    async def resume(self) -> bool:
        """Resume playback."""
        result = await self._request("setPlayerCmd:resume")
        return "OK" in result.upper() or result.strip() == ""

    async def set_volume(self, level: int) -> bool:
        """Set volume (0-100)."""
        level = max(0, min(100, level))
        result = await self._request(f"setPlayerCmd:vol:{level}")
        return "OK" in result.upper() or result.strip() == ""

    async def get_volume(self) -> int:
        """Get current volume."""
        status = await self.get_player_status()
        return int(status.get("vol", 50))

    def decode_mode(self, mode: str) -> str:
        """Decode playback mode."""
        modes = {
            "0": "Idle",
            "1": "AirPlay",
            "2": "DLNA",
            "10": "Network Stream",
            "11": "USB",
            "31": "Spotify",
            "40": "Line-in",
            "41": "Bluetooth"
        }
        return modes.get(str(mode), f"Unknown ({mode})")


async def test_connectivity():
    """Test basic connectivity to the speaker."""
    print("\n" + "=" * 60)
    print("TEST 1: Connectivity Check")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)
    status = await api.get_status()

    if "error" in status and "raw" not in status:
        print(f"\n  FAILED: Cannot connect to {OFFICE_SPEAKER_IP}")
        print(f"  Error: {status.get('error')}")
        return False

    print(f"\n  SUCCESS: Connected to {status.get('DeviceName', 'Unknown')}")
    print(f"  Firmware: {status.get('firmware', 'Unknown')}")
    print(f"  Hardware: {status.get('hardware', 'Unknown')}")

    return True


async def test_volume_control():
    """Test volume control."""
    print("\n" + "=" * 60)
    print("TEST 2: Volume Control")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Get current volume
    original_vol = await api.get_volume()
    print(f"\n  Current volume: {original_vol}%")

    # Set to 40% (safe level)
    print(f"  Setting volume to 40%...")
    await api.set_volume(40)
    await asyncio.sleep(0.5)

    # Verify
    new_vol = await api.get_volume()
    print(f"  Volume is now: {new_vol}%")

    if new_vol == 40:
        print("  SUCCESS: Volume control working")
        return True
    else:
        print("  WARNING: Volume may not have changed")
        return False


async def test_stream_playback():
    """Test streaming audio to the speaker."""
    print("\n" + "=" * 60)
    print("TEST 3: Audio Streaming")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Ensure volume is at a safe level
    await api.set_volume(40)
    print(f"\n  Volume set to 40% for testing")

    # Stop any current playback
    print(f"  Stopping current playback...")
    await api.stop()
    await asyncio.sleep(1)

    # Try each test stream
    for stream in TEST_STREAMS:
        print(f"\n  Trying: {stream['name']}")
        print(f"  URL: {stream['url'][:50]}...")

        # Start playback
        success = await api.play_url(stream['url'])

        if not success:
            print(f"  Failed to start stream, trying next...")
            continue

        # Wait for playback to start
        print(f"  Waiting for playback to start...")
        await asyncio.sleep(3)

        # Check status
        status = await api.get_player_status()
        mode = api.decode_mode(status.get("mode", "0"))
        play_status = status.get("status", "unknown")

        print(f"  Mode: {mode}")
        print(f"  Status: {play_status}")

        if play_status == "play":
            print(f"\n  SUCCESS: Audio is playing!")
            print(f"  You should hear ambient music from the speaker")
            print(f"\n  Letting it play for 10 seconds...")

            # Play for 10 seconds
            for i in range(10, 0, -1):
                print(f"    {i} seconds remaining...", end='\r')
                await asyncio.sleep(1)

            print(f"    Stopping playback...      ")
            await api.stop()
            await asyncio.sleep(1)

            print(f"  Playback stopped")
            return True
        else:
            print(f"  Playback did not start, trying next stream...")

    print(f"\n  FAILED: Could not play any test streams")
    return False


async def test_playback_control():
    """Test pause/resume functionality."""
    print("\n" + "=" * 60)
    print("TEST 4: Playback Control (Pause/Resume)")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Start a stream
    stream = TEST_STREAMS[0]
    print(f"\n  Starting stream: {stream['name']}")

    await api.set_volume(40)
    await api.play_url(stream['url'])
    await asyncio.sleep(3)

    # Check if playing
    status = await api.get_player_status()
    if status.get("status") != "play":
        print(f"  Could not start playback for control test")
        return False

    # Test pause
    print(f"  Testing pause...")
    await api.pause()
    await asyncio.sleep(1)

    status = await api.get_player_status()
    paused = status.get("status") == "pause"
    print(f"  Pause status: {'SUCCESS' if paused else 'FAILED'}")

    # Test resume
    print(f"  Testing resume...")
    await api.resume()
    await asyncio.sleep(1)

    status = await api.get_player_status()
    resumed = status.get("status") == "play"
    print(f"  Resume status: {'SUCCESS' if resumed else 'FAILED'}")

    # Stop
    await api.stop()

    return paused and resumed


async def run_all_tests():
    """Run all streaming tests."""
    print("\n" + "#" * 60)
    print("# Arylic Speaker Streaming Test Suite")
    print(f"# Target: {OFFICE_SPEAKER_NAME} ({OFFICE_SPEAKER_IP})")
    print("#" * 60)

    results = {}

    # Test 1: Connectivity
    results['connectivity'] = await test_connectivity()
    if not results['connectivity']:
        print("\n\nABORTING: Cannot connect to speaker")
        return False

    # Test 2: Volume Control
    results['volume'] = await test_volume_control()

    # Test 3: Stream Playback
    results['streaming'] = await test_stream_playback()

    # Test 4: Playback Control
    if results['streaming']:
        results['control'] = await test_playback_control()
    else:
        results['control'] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"\n  Connectivity:   {'PASS' if results['connectivity'] else 'FAIL'}")
    print(f"  Volume Control: {'PASS' if results['volume'] else 'FAIL'}")
    print(f"  Streaming:      {'PASS' if results['streaming'] else 'FAIL'}")
    print(f"  Playback Ctrl:  {'PASS' if results['control'] else 'FAIL'}")

    all_passed = all(results.values())
    print(f"\n  Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

    if results['streaming']:
        print(f"\n  The speaker successfully played audio from a network stream.")
        print(f"  This confirms the device's streaming capabilities work.")
        print(f"\n  Next steps for AirPlay testing:")
        print(f"  - Install Visual C++ Build Tools for pyatv/miniaudio")
        print(f"  - Or run tests in Docker/Linux environment")
        print(f"  - Or use the Sonorium Windows app which bundles dependencies")

    return all_passed


def main():
    print("\n" + "=" * 60)
    print("Arylic Speaker Streaming Test")
    print("=" * 60)
    print(f"\nThis test will play audio to your speaker.")
    print(f"Volume will be set to 40% for safety.")
    print(f"Press Ctrl+C to abort at any time.\n")

    try:
        result = asyncio.run(run_all_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest aborted by user")
        # Try to stop playback
        async def cleanup():
            api = ArylicAPI(OFFICE_SPEAKER_IP)
            await api.stop()
        asyncio.run(cleanup())
        sys.exit(130)


if __name__ == "__main__":
    main()
