#!/usr/bin/env python3
"""
AirPlay Streaming Test for Arylic Speakers

Tests AirPlay (RAOP) streaming to Arylic/Linkplay speakers using pyatv.
This is a standalone test script - does not require the full Sonorium server.

Test Device: Office_C97a at 192.168.1.74

Usage:
    python tests/test_airplay_streaming.py [--discover] [--stream] [--status] [--all]

Options:
    --discover  Scan for AirPlay devices on the network
    --stream    Stream a test tone to the Office speaker
    --status    Check speaker status via Arylic HTTP API
    --all       Run all tests (default)
"""

import asyncio
import argparse
import logging
import sys
import struct
import math
from typing import Optional

# Third-party imports
try:
    import pyatv
    from pyatv.const import Protocol
except ImportError:
    print("ERROR: pyatv not installed. Run: pip install pyatv")
    sys.exit(1)

try:
    import aiohttp
except ImportError:
    print("ERROR: aiohttp not installed. Run: pip install aiohttp")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
OFFICE_SPEAKER_IP = "192.168.1.74"
OFFICE_SPEAKER_NAME = "Office_C97a"
AIRPLAY_PORT = 7000
RAOP_PORT = 49152

# Audio configuration for test tone
SAMPLE_RATE = 44100
CHANNELS = 2
BITS_PER_SAMPLE = 16
TEST_TONE_FREQUENCY = 440  # A4 note - pleasant tone
TEST_TONE_DURATION = 10    # seconds
TEST_TONE_VOLUME = 0.3     # 30% volume - not too loud


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
                        return await resp.json()
                    return {"error": f"HTTP {resp.status}"}
            except Exception as e:
                return {"error": str(e)}

    async def get_player_status(self) -> dict:
        """Get current playback status."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=getPlayerStatus"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"error": f"HTTP {resp.status}"}
            except Exception as e:
                return {"error": str(e)}

    async def stop_playback(self) -> bool:
        """Stop any current playback."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=setPlayerCmd:stop"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
            except Exception:
                return False

    async def set_volume(self, level: int) -> bool:
        """Set volume (0-100)."""
        level = max(0, min(100, level))
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}?command=setPlayerCmd:vol:{level}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
            except Exception:
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
        return modes.get(mode, f"Unknown ({mode})")


def generate_test_tone_mp3() -> bytes:
    """
    Generate a test tone as MP3 data using PyAV.

    MP3 is required for pyatv streaming because non-seekable streams
    (like StreamReader) only work with MP3 format according to pyatv docs.
    WAV/FLAC/OGG require seekable streams.
    """
    try:
        import av
        import numpy as np
    except ImportError:
        logger.error("PyAV not installed. Run: pip install av numpy")
        return b''

    logger.info(f"Generating {TEST_TONE_DURATION}s MP3 test tone at {TEST_TONE_FREQUENCY}Hz...")

    # Generate stereo sine wave as numpy array
    num_samples = SAMPLE_RATE * TEST_TONE_DURATION
    t = np.linspace(0, TEST_TONE_DURATION, num_samples, dtype=np.float32)
    mono_wave = (TEST_TONE_VOLUME * 32767 * np.sin(2 * np.pi * TEST_TONE_FREQUENCY * t)).astype(np.int16)

    # Stereo: duplicate mono to both channels
    stereo_wave = np.column_stack((mono_wave, mono_wave))

    # Encode to MP3 using PyAV
    import io
    output_buffer = io.BytesIO()

    # Create output container in memory
    output_container = av.open(output_buffer, mode='w', format='mp3')
    output_stream = output_container.add_stream('mp3', rate=SAMPLE_RATE)
    output_stream.channels = CHANNELS
    output_stream.layout = 'stereo'

    # Create audio frame and encode
    # Process in chunks to avoid memory issues
    chunk_size = SAMPLE_RATE  # 1 second chunks
    for i in range(0, len(stereo_wave), chunk_size):
        chunk = stereo_wave[i:i + chunk_size]
        if len(chunk) == 0:
            break

        # Create frame with correct format
        frame = av.AudioFrame.from_ndarray(chunk.T, format='s16', layout='stereo')
        frame.sample_rate = SAMPLE_RATE
        frame.pts = i

        # Encode frame
        for packet in output_stream.encode(frame):
            output_container.mux(packet)

    # Flush encoder
    for packet in output_stream.encode(None):
        output_container.mux(packet)

    output_container.close()

    mp3_data = output_buffer.getvalue()
    logger.info(f"Generated {len(mp3_data)} bytes of MP3 audio")
    return mp3_data


async def test_discover_airplay() -> list:
    """
    Test 1: Discover AirPlay devices on the network.
    """
    print("\n" + "=" * 60)
    print("TEST 1: AirPlay Device Discovery")
    print("=" * 60)

    logger.info("Scanning for AirPlay devices (10 second timeout)...")

    try:
        loop = asyncio.get_event_loop()
        devices = await pyatv.scan(loop, timeout=10)

        if not devices:
            print("\n  No AirPlay devices found!")
            print("  - Check that devices are powered on")
            print("  - Check network connectivity")
            return []

        print(f"\n  Found {len(devices)} device(s):\n")

        airplay_devices = []
        for device in devices:
            # Check for AirPlay or RAOP services
            has_airplay = device.get_service(Protocol.AirPlay) is not None
            has_raop = device.get_service(Protocol.RAOP) is not None

            if has_airplay or has_raop:
                airplay_devices.append(device)
                services = []
                if has_airplay:
                    services.append("AirPlay")
                if has_raop:
                    services.append("RAOP")

                print(f"  [{device.name}]")
                print(f"    IP: {device.address}")
                print(f"    Identifier: {device.identifier[:40]}...")
                print(f"    Services: {', '.join(services)}")
                print()

        # Check for our target device
        target_found = any(str(d.address) == OFFICE_SPEAKER_IP for d in airplay_devices)
        if target_found:
            print(f"  ✓ Target device {OFFICE_SPEAKER_NAME} ({OFFICE_SPEAKER_IP}) FOUND")
        else:
            print(f"  ✗ Target device {OFFICE_SPEAKER_NAME} ({OFFICE_SPEAKER_IP}) NOT FOUND")
            print(f"    Trying direct scan of {OFFICE_SPEAKER_IP}...")

            # Try direct scan
            direct_devices = await pyatv.scan(loop, hosts=[OFFICE_SPEAKER_IP], timeout=10)
            if direct_devices:
                print(f"    ✓ Found via direct scan!")
                airplay_devices.extend(direct_devices)

        return airplay_devices

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return []


async def test_arylic_status() -> dict:
    """
    Test 2: Check Arylic speaker status via HTTP API.
    """
    print("\n" + "=" * 60)
    print("TEST 2: Arylic HTTP API Status Check")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Get device status
    print(f"\n  Checking {OFFICE_SPEAKER_NAME} ({OFFICE_SPEAKER_IP})...\n")

    status = await api.get_status()
    if "error" in status:
        print(f"  ✗ Device status: FAILED ({status['error']})")
        return {}

    print(f"  ✓ Device is reachable")
    print(f"    Firmware: {status.get('firmware', 'Unknown')}")
    print(f"    Hardware: {status.get('hardware', 'Unknown')}")
    print(f"    UUID: {status.get('uuid', 'Unknown')[:30]}...")

    # Get player status
    player = await api.get_player_status()
    if "error" not in player:
        mode = api.decode_mode(player.get("mode", "0"))
        status_str = player.get("status", "unknown")
        volume = player.get("vol", "?")
        muted = "Yes" if player.get("mute") == "1" else "No"

        print(f"\n  Playback Status:")
        print(f"    Mode: {mode}")
        print(f"    Status: {status_str}")
        print(f"    Volume: {volume}%")
        print(f"    Muted: {muted}")

    return status


async def test_airplay_streaming():
    """
    Test 3: Stream audio to the speaker via AirPlay/RAOP.

    This test:
    1. Connects to the speaker via pyatv
    2. Generates a test tone
    3. Streams it using stream_file() with StreamReader
    4. Monitors playback via Arylic HTTP API
    """
    print("\n" + "=" * 60)
    print("TEST 3: AirPlay Streaming Test")
    print("=" * 60)

    api = ArylicAPI(OFFICE_SPEAKER_IP)

    # Set a safe volume first
    print(f"\n  Setting volume to 40%...")
    await api.set_volume(40)

    # Stop any current playback
    print(f"  Stopping any current playback...")
    await api.stop_playback()
    await asyncio.sleep(1)

    # Scan for the device
    print(f"\n  Scanning for {OFFICE_SPEAKER_NAME}...")
    loop = asyncio.get_event_loop()

    devices = await pyatv.scan(loop, hosts=[OFFICE_SPEAKER_IP], timeout=10)
    if not devices:
        print(f"  ✗ Could not find device at {OFFICE_SPEAKER_IP}")
        return False

    device_config = devices[0]
    print(f"  ✓ Found: {device_config.name}")

    # Check for RAOP service (audio streaming)
    raop_service = device_config.get_service(Protocol.RAOP)
    airplay_service = device_config.get_service(Protocol.AirPlay)

    if raop_service:
        print(f"  ✓ RAOP service available (port {raop_service.port})")
    if airplay_service:
        print(f"  ✓ AirPlay service available (port {airplay_service.port})")

    if not raop_service and not airplay_service:
        print(f"  ✗ No AirPlay/RAOP service found on device")
        return False

    # Connect to device
    print(f"\n  Connecting to device...")
    atv = None
    try:
        atv = await pyatv.connect(device_config, loop)
        print(f"  ✓ Connected successfully")

        # Check streaming interface
        if not atv.stream:
            print(f"  ✗ Device does not expose streaming interface")
            return False

        print(f"  ✓ Streaming interface available")

        # Generate test tone
        print(f"\n  Generating test tone...")
        audio_data = generate_test_tone_mp3()
        print(f"  ✓ Generated {len(audio_data)} bytes of audio")

        # Create StreamReader and feed data
        print(f"\n  Starting AirPlay stream...")
        print(f"  (You should hear a {TEST_TONE_FREQUENCY}Hz tone for {TEST_TONE_DURATION} seconds)")
        print(f"  Volume is at 40% with 30% tone amplitude - should be pleasant")

        reader = asyncio.StreamReader()

        # Feed audio data to reader
        async def feed_audio():
            # Feed in chunks to simulate streaming
            chunk_size = 8192
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                reader.feed_data(chunk)
                await asyncio.sleep(0.01)  # Small delay between chunks
            reader.feed_eof()

        # Start feeding in background
        feed_task = asyncio.create_task(feed_audio())

        # Stream to device
        try:
            await atv.stream.stream_file(reader)
            print(f"\n  ✓ Streaming completed successfully!")

            # Check status via Arylic API
            await asyncio.sleep(1)
            player = await api.get_player_status()
            mode = api.decode_mode(player.get("mode", "0"))
            print(f"  Device mode after stream: {mode}")

            return True

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            print(f"\n  ✗ Streaming failed: {e}")
            return False
        finally:
            feed_task.cancel()
            try:
                await feed_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Connection error: {e}")
        print(f"  ✗ Connection failed: {e}")
        return False
    finally:
        if atv:
            print(f"\n  Closing connection...")
            await atv.close()
            print(f"  ✓ Connection closed")


async def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "#" * 60)
    print("# AirPlay Streaming Test Suite")
    print("# Target: Office_C97a (192.168.1.74)")
    print("#" * 60)

    results = {}

    # Test 1: Discovery
    devices = await test_discover_airplay()
    results['discovery'] = len(devices) > 0

    # Test 2: Arylic HTTP API
    status = await test_arylic_status()
    results['http_api'] = 'error' not in status and len(status) > 0

    # Test 3: AirPlay Streaming
    results['streaming'] = await test_airplay_streaming()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"\n  Discovery:    {'✓ PASS' if results['discovery'] else '✗ FAIL'}")
    print(f"  HTTP API:     {'✓ PASS' if results['http_api'] else '✗ FAIL'}")
    print(f"  Streaming:    {'✓ PASS' if results['streaming'] else '✗ FAIL'}")

    all_passed = all(results.values())
    print(f"\n  Overall:      {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    print()

    return all_passed


def main():
    parser = argparse.ArgumentParser(
        description="Test AirPlay streaming to Arylic speakers"
    )
    parser.add_argument('--discover', action='store_true', help='Run discovery test only')
    parser.add_argument('--status', action='store_true', help='Run HTTP API status test only')
    parser.add_argument('--stream', action='store_true', help='Run streaming test only')
    parser.add_argument('--all', action='store_true', help='Run all tests (default)')

    args = parser.parse_args()

    # Default to all tests if nothing specified
    if not any([args.discover, args.status, args.stream, args.all]):
        args.all = True

    async def run():
        if args.all:
            return await run_all_tests()

        if args.discover:
            devices = await test_discover_airplay()
            return len(devices) > 0

        if args.status:
            status = await test_arylic_status()
            return 'error' not in status

        if args.stream:
            return await test_airplay_streaming()

    try:
        result = asyncio.run(run())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
