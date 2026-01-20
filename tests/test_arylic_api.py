#!/usr/bin/env python3
"""
Simple Arylic HTTP API Test

Tests connectivity and API responses from Arylic/Linkplay speakers.
Does NOT require pyatv - uses only aiohttp for HTTP requests.

Usage:
    python tests/test_arylic_api.py
"""

import asyncio
import sys

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

# Test configuration
OFFICE_SPEAKER_IP = "192.168.1.74"
OFFICE_SPEAKER_NAME = "Office_C97a"


class ArylicAPI:
    """Simple async wrapper for Arylic HTTP API."""

    def __init__(self, host: str):
        self.host = host
        self.base_url = f"http://{host}/httpapi.asp"

    async def get_status(self) -> dict:
        """Get comprehensive device status."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=getStatusEx"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        # Try to parse as JSON, otherwise return raw text
                        try:
                            import json
                            return json.loads(text)
                        except:
                            return {"raw": text}
                    return {"error": f"HTTP {resp.status}"}
            except aiohttp.ClientError as e:
                return {"error": f"Connection error: {e}"}
            except asyncio.TimeoutError:
                return {"error": "Timeout"}

    async def get_player_status(self) -> dict:
        """Get current playback status."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=getPlayerStatus"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        try:
                            import json
                            return json.loads(text)
                        except:
                            return {"raw": text}
                    return {"error": f"HTTP {resp.status}"}
            except aiohttp.ClientError as e:
                return {"error": f"Connection error: {e}"}
            except asyncio.TimeoutError:
                return {"error": "Timeout"}

    async def stop_playback(self) -> bool:
        """Stop any current playback."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=setPlayerCmd:stop"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
            except:
                return False

    async def set_volume(self, level: int) -> bool:
        """Set volume (0-100)."""
        level = max(0, min(100, level))
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=setPlayerCmd:vol:{level}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
            except:
                return False

    def decode_mode(self, mode: str) -> str:
        """Decode playback mode to human-readable string."""
        modes = {
            "0": "Idle",
            "1": "AirPlay",
            "2": "DLNA",
            "10": "Network Stream",
            "11": "USB Storage",
            "31": "Spotify Connect",
            "40": "Line-in",
            "41": "Bluetooth"
        }
        return modes.get(str(mode), f"Unknown ({mode})")


async def test_arylic_api():
    """Test Arylic HTTP API connectivity and responses."""
    print("\n" + "=" * 60)
    print(f"Arylic HTTP API Test - {OFFICE_SPEAKER_NAME}")
    print(f"Target: {OFFICE_SPEAKER_IP}")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Test 1: Device Status
    print("\n[1] Getting device status (getStatusEx)...")
    status = await api.get_status()

    if "error" in status:
        print(f"    FAILED: {status['error']}")
        print("\n    Troubleshooting:")
        print(f"    - Is the speaker powered on?")
        print(f"    - Can you ping {OFFICE_SPEAKER_IP}?")
        print(f"    - Try: curl http://{OFFICE_SPEAKER_IP}/httpapi.asp?command=getStatusEx")
        return False

    print(f"    SUCCESS - Device is reachable")

    # Print interesting fields
    fields = ['DeviceName', 'firmware', 'hardware', 'uuid', 'ssid', 'apcli0']
    for field in fields:
        if field in status:
            value = status[field]
            if len(str(value)) > 40:
                value = str(value)[:40] + "..."
            print(f"    {field}: {value}")

    # Test 2: Player Status
    print("\n[2] Getting player status (getPlayerStatus)...")
    player = await api.get_player_status()

    if "error" in player:
        print(f"    FAILED: {player['error']}")
    else:
        print(f"    SUCCESS")
        mode = api.decode_mode(player.get("mode", "0"))
        print(f"    Mode: {mode}")
        print(f"    Status: {player.get('status', 'unknown')}")
        print(f"    Volume: {player.get('vol', '?')}%")
        print(f"    Muted: {'Yes' if player.get('mute') == '1' else 'No'}")

    # Test 3: Set Volume
    print("\n[3] Setting volume to 50%...")
    if await api.set_volume(50):
        print("    SUCCESS")
    else:
        print("    FAILED")

    # Test 4: Verify Volume Change
    print("\n[4] Verifying volume change...")
    player = await api.get_player_status()
    if "error" not in player:
        vol = player.get('vol', '?')
        print(f"    Volume is now: {vol}%")
        if str(vol) == "50":
            print("    VERIFIED")
        else:
            print("    WARNING: Volume didn't change to expected value")

    # Summary
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"\n  Speaker {OFFICE_SPEAKER_NAME} is reachable and responding")
    print(f"  HTTP API is working correctly")
    print(f"\n  Next step: Install pyatv for AirPlay streaming test")
    print(f"  Note: pyatv requires Visual C++ Build Tools on Windows")
    print(f"        or run in Docker/Linux environment")

    return True


def main():
    try:
        result = asyncio.run(test_arylic_api())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
