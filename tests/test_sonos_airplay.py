#!/usr/bin/env python3
"""
Sonos AirPlay 2 Streaming Test

Tests AirPlay 2 streaming to Sonos speaker using pyatv.
Sonos supports AirPlay 2 which should be backwards compatible with AirPlay.

Usage:
    python tests/test_sonos_airplay.py

Target: Sonos Office at 192.168.1.185
"""

import asyncio
import sys
import io
import logging
import tempfile
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Debug level to see all pyatv internals
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
SONOS_IP = "192.168.1.185"
TEST_DURATION = 3  # seconds - short test
TONE_FREQUENCY = 440  # Hz (A4 note) - pleasant tone
SAMPLE_RATE = 44100
VOLUME = 0.2  # 20% volume - quiet!


def generate_quiet_tone(duration: float, frequency: float) -> bytes:
    """Generate a quiet stereo MP3 test tone using PyAV."""
    import av
    import numpy as np

    logger.info(f"Generating {duration}s quiet tone at {frequency}Hz ({VOLUME*100:.0f}% volume)...")

    # Generate stereo sine wave
    num_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, num_samples, dtype=np.float32)
    mono = (VOLUME * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

    # Create stereo (planar format: channels, samples)
    stereo_planar = np.vstack([mono, mono])

    # Encode to MP3 in memory
    buffer = io.BytesIO()
    container = av.open(buffer, mode='w', format='mp3')
    stream = container.add_stream('mp3', rate=SAMPLE_RATE)
    stream.bit_rate = 128000

    # Encode in chunks
    chunk_size = SAMPLE_RATE
    for i in range(0, stereo_planar.shape[1], chunk_size):
        chunk = stereo_planar[:, i:i + chunk_size]
        if chunk.shape[1] == 0:
            break
        frame = av.AudioFrame.from_ndarray(chunk, format='s16p', layout='stereo')
        frame.sample_rate = SAMPLE_RATE
        frame.pts = i
        for packet in stream.encode(frame):
            container.mux(packet)

    for packet in stream.encode(None):
        container.mux(packet)
    container.close()

    mp3_data = buffer.getvalue()
    logger.info(f"Generated {len(mp3_data)} bytes of MP3 audio")
    return mp3_data


async def scan_for_sonos():
    """Scan for the Sonos device via AirPlay/RAOP."""
    import pyatv
    from pyatv.const import Protocol

    print("\n" + "=" * 60)
    print(f"SCANNING FOR SONOS AT {SONOS_IP}")
    print("=" * 60)

    loop = asyncio.get_event_loop()

    # Method 1: Direct IP scan
    print(f"\n1. Direct scan of {SONOS_IP}...")
    try:
        devices = await pyatv.scan(loop, hosts=[SONOS_IP], timeout=10)
        if devices:
            device = devices[0]
            print(f"   Found: {device.name}")
            print(f"   Address: {device.address}")
            print(f"   Services:")
            for service in device.services:
                print(f"     - {service.protocol.name}: port {service.port}")
                if hasattr(service, 'properties') and service.properties:
                    print(f"       Properties: {dict(service.properties)}")
            return device
        else:
            print(f"   No device found at {SONOS_IP}")
    except Exception as e:
        print(f"   Direct scan failed: {e}")

    # Method 2: Broadcast scan looking for Sonos
    print(f"\n2. Broadcast mDNS scan (looking for Sonos)...")
    try:
        all_devices = await pyatv.scan(loop, timeout=10)
        print(f"   Found {len(all_devices)} device(s)")
        for d in all_devices:
            print(f"   - {d.name} ({d.address})")
            if str(d.address) == SONOS_IP or 'sonos' in d.name.lower():
                print(f"     ^ This is our Sonos!")
                return d
    except Exception as e:
        print(f"   Broadcast scan failed: {e}")

    return None


async def test_airplay_stream(device_config, mp3_data: bytes):
    """Test AirPlay streaming to the Sonos."""
    import pyatv

    print("\n" + "=" * 60)
    print(f"TESTING AIRPLAY STREAMING TO {device_config.name}")
    print("=" * 60)

    loop = asyncio.get_event_loop()

    # Connect to device
    print("\nConnecting to device...")
    try:
        atv = await pyatv.connect(device_config, loop)
        print(f"  Connected: {atv}")
    except Exception as e:
        print(f"  Connection failed: {e}")
        return False

    # Check for stream interface
    print(f"\nStream interface: {atv.stream}")
    if not atv.stream:
        print("  ERROR: No stream interface available!")
        print("  This device may not support AirPlay streaming via pyatv")
        await atv.close()
        return False

    # Save MP3 to temp file
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    temp_file.write(mp3_data)
    temp_file.close()
    print(f"\nTemp file: {temp_file.name}")

    # Try streaming
    print("\nAttempting to stream audio...")
    print("  (You should hear a 440Hz tone for 3 seconds)")

    try:
        await asyncio.wait_for(
            atv.stream.stream_file(temp_file.name),
            timeout=TEST_DURATION + 15  # Extra time for connection setup
        )
        print("\n  SUCCESS! Stream completed without error.")
        success = True
    except asyncio.TimeoutError:
        print("\n  TIMEOUT: Stream timed out")
        print("  This could mean:")
        print("    - The stream is working but takes longer than expected")
        print("    - The device didn't respond")
        success = False
    except Exception as e:
        print(f"\n  FAILED: {e}")
        print(f"  Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        success = False
    finally:
        os.unlink(temp_file.name)
        atv.close()  # Not awaitable

    return success


async def test_manual_raop_connection():
    """Try connecting with manually configured RAOP service."""
    import pyatv
    from pyatv import conf
    from pyatv.const import Protocol

    print("\n" + "=" * 60)
    print("TESTING MANUAL RAOP CONFIGURATION")
    print("=" * 60)

    loop = asyncio.get_event_loop()

    # Common AirPlay/RAOP ports
    ports_to_try = [7000, 5000, 49152, 4515, 7100]

    for port in ports_to_try:
        print(f"\nTrying RAOP on port {port}...")

        # Build manual config
        config = conf.AppleTV(address=SONOS_IP, name=f"Sonos_Manual")

        # Add RAOP service with AirPlay 2 properties
        raop_props = {
            'am': 'Sonos',  # Model
            'et': '0,3,5',  # Encryption types
            'cn': '0,1,2,3',  # Codecs
            'sf': '0x4',  # Features
        }

        try:
            from pyatv.protocols.raop import RaopService
            raop_service = RaopService(port=port, properties=raop_props)
            config.add_service(raop_service)
        except ImportError:
            # Try alternative import path
            try:
                from pyatv.protocols.raop.raop import RaopService
                raop_service = RaopService(port=port, properties=raop_props)
                config.add_service(raop_service)
            except Exception as e:
                print(f"  Could not create RaopService: {e}")
                continue

        try:
            atv = await asyncio.wait_for(
                pyatv.connect(config, loop),
                timeout=5
            )
            print(f"  Connected on port {port}!")
            print(f"  Stream interface: {atv.stream}")
            await atv.close()
            return port
        except asyncio.TimeoutError:
            print(f"  Port {port}: Connection timed out")
        except Exception as e:
            print(f"  Port {port}: {e}")

    return None


async def main():
    """Main test function."""
    print("\n" + "#" * 60)
    print("# SONOS AIRPLAY 2 STREAMING TEST")
    print("#" * 60)
    print(f"\nTarget: Sonos at {SONOS_IP}")
    print("Note: Sonos supports AirPlay 2")

    # Step 1: Generate test audio
    print("\n[1/4] Generating test audio...")
    mp3_data = generate_quiet_tone(TEST_DURATION, TONE_FREQUENCY)
    print(f"      Audio: {len(mp3_data)} bytes, {TEST_DURATION}s, {TONE_FREQUENCY}Hz")
    print(f"      Volume: {VOLUME*100:.0f}% (quiet)")

    # Step 2: Scan for device
    print("\n[2/4] Scanning for Sonos...")
    device = await scan_for_sonos()

    # Step 3: Test streaming if device found
    if device:
        print("\n[3/4] Testing AirPlay streaming...")
        success = await test_airplay_stream(device, mp3_data)
    else:
        print("\n[3/4] Device not found via scan, trying manual connection...")
        working_port = await test_manual_raop_connection()
        if working_port:
            print(f"\nFound working RAOP port: {working_port}")
            # TODO: Could retry streaming with manual config
        success = False

    # Step 4: Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    if device:
        print(f"Device discovered: YES ({device.name})")
    else:
        print("Device discovered: NO")

    print(f"Stream test: {'PASSED' if success else 'FAILED'}")

    if not success:
        print("\nPossible issues:")
        print("  1. Sonos AirPlay 2 may require authentication")
        print("  2. pyatv may not fully support AirPlay 2 protocol")
        print("  3. Network/firewall blocking RAOP ports")
        print("  4. Sonos may need to be in a specific state")
        print("\nNext steps to try:")
        print("  - Check if Sonos is playing something (may need to stop first)")
        print("  - Try pairing/authentication")
        print("  - Check pyatv version and AirPlay 2 support status")

    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
