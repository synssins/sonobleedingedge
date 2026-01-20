#!/usr/bin/env python3
"""
Direct AirPlay Streaming Test

Tests AirPlay streaming directly to speakers without the full Sonorium server.
Uses pyatv to push MP3 audio to AirPlay/RAOP devices.

Usage:
    python tests/test_airplay_direct.py [--scan] [--ip IP]

Options:
    --scan      Scan for all AirPlay devices on the network
    --ip IP     Target a specific IP address (default: 192.168.1.74)
"""

import asyncio
import sys
import io
import logging
import argparse
import tempfile
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
DEFAULT_TARGET_IP = "192.168.1.74"
TEST_DURATION = 5  # seconds
TONE_FREQUENCY = 440  # Hz (A4 note)
SAMPLE_RATE = 44100
VOLUME = 0.3  # 30% volume


def generate_stereo_mp3(duration: float, frequency: float) -> bytes:
    """Generate a stereo MP3 test tone using PyAV."""
    import av
    import numpy as np

    logger.info(f"Generating {duration}s stereo MP3 at {frequency}Hz...")

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


async def discover_devices(target_ip: str = None, timeout: int = 10):
    """
    Discover AirPlay devices using multiple methods.
    Returns list of device configs.
    """
    import pyatv
    from pyatv.const import Protocol

    print("\n" + "=" * 60)
    print("DEVICE DISCOVERY")
    print("=" * 60)

    devices = []
    loop = asyncio.get_event_loop()

    # Method 1: Broadcast scan (finds all devices)
    print("\n1. Broadcast mDNS scan (10s timeout)...")
    try:
        broadcast_devices = await pyatv.scan(loop, timeout=timeout)
        print(f"   Found {len(broadcast_devices)} device(s) via broadcast")
        for d in broadcast_devices:
            raop = d.get_service(Protocol.RAOP)
            airplay = d.get_service(Protocol.AirPlay)
            services = []
            if raop:
                services.append(f"RAOP:{raop.port}")
            if airplay:
                services.append(f"AirPlay:{airplay.port}")
            print(f"   - {d.name} ({d.address}) [{', '.join(services) or 'no services'}]")
            if raop or airplay:
                devices.append(d)
    except Exception as e:
        print(f"   Broadcast scan failed: {e}")

    # Method 2: Direct IP scan (if target specified)
    if target_ip:
        print(f"\n2. Direct scan of {target_ip}...")
        try:
            direct_devices = await pyatv.scan(loop, hosts=[target_ip], timeout=timeout)
            if direct_devices:
                print(f"   Found device at {target_ip}: {direct_devices[0].name}")
                # Add if not already in list
                existing_ips = [str(d.address) for d in devices]
                for d in direct_devices:
                    if str(d.address) not in existing_ips:
                        devices.append(d)
            else:
                print(f"   No device responded at {target_ip}")
        except Exception as e:
            print(f"   Direct scan failed: {e}")

    # Method 3: Manual config build (if we have stored info)
    if target_ip and not any(str(d.address) == target_ip for d in devices):
        print(f"\n3. Building manual config for {target_ip}...")
        try:
            from pyatv import conf
            from pyatv.const import Protocol
            from pyatv.protocols.raop.raop import RaopService

            # Try common RAOP ports
            for port in [7000, 5000, 49152, 4515]:
                print(f"   Trying port {port}...")
                config = conf.AppleTV(address=target_ip, name=f"Manual_{target_ip}")

                # Add RAOP service
                raop_service = RaopService(
                    port=port,
                    properties={
                        'am': 'AudioAccessory5,1',
                        'et': '0,3,5',
                        'cn': '0,1,2,3',
                    }
                )
                config.add_service(raop_service)

                # Test connection
                try:
                    atv = await pyatv.connect(config, loop)
                    if atv.stream:
                        print(f"   SUCCESS: Connected on port {port}")
                        devices.append(config)
                        await atv.close()
                        break
                    await atv.close()
                except Exception as conn_err:
                    print(f"   Port {port}: {conn_err}")
        except Exception as e:
            print(f"   Manual config failed: {e}")

    print(f"\n   Total usable devices: {len(devices)}")
    return devices


async def test_streaming_to_device(config, mp3_data: bytes):
    """
    Test streaming to a single device using multiple methods.
    Returns (method_name, success, error_message)
    """
    import pyatv

    device_name = config.name
    print(f"\n" + "-" * 40)
    print(f"Testing: {device_name} ({config.address})")
    print("-" * 40)

    loop = asyncio.get_event_loop()
    results = []

    # Connect to device
    print("\nConnecting...")
    try:
        atv = await pyatv.connect(config, loop)
    except Exception as e:
        print(f"  Connection failed: {e}")
        return [("connection", False, str(e))]

    if not atv.stream:
        print("  No stream interface available")
        await atv.close()
        return [("stream_interface", False, "No stream interface")]

    print("  Connected, stream interface available")

    # Method 1: File streaming
    print("\nMethod 1: File streaming...")
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    temp_file.write(mp3_data)
    temp_file.close()
    try:
        await asyncio.wait_for(
            atv.stream.stream_file(temp_file.name),
            timeout=TEST_DURATION + 10
        )
        print("  SUCCESS: File streaming completed")
        results.append(("file", True, None))
    except asyncio.TimeoutError:
        print("  TIMEOUT: File streaming timed out")
        results.append(("file", False, "Timeout"))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("file", False, str(e)))
    finally:
        os.unlink(temp_file.name)

    # Method 2: Buffer streaming (BytesIO)
    print("\nMethod 2: Buffer streaming (BytesIO)...")
    buffer = io.BytesIO(mp3_data)
    try:
        await asyncio.wait_for(
            atv.stream.stream_file(buffer),
            timeout=TEST_DURATION + 10
        )
        print("  SUCCESS: Buffer streaming completed")
        results.append(("buffer", True, None))
    except asyncio.TimeoutError:
        print("  TIMEOUT: Buffer streaming timed out")
        results.append(("buffer", False, "Timeout"))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("buffer", False, str(e)))

    # Method 3: StreamReader streaming
    print("\nMethod 3: StreamReader streaming...")
    reader = asyncio.StreamReader()
    reader.feed_data(mp3_data)
    reader.feed_eof()
    try:
        await asyncio.wait_for(
            atv.stream.stream_file(reader),
            timeout=TEST_DURATION + 10
        )
        print("  SUCCESS: StreamReader streaming completed")
        results.append(("streamreader", True, None))
    except asyncio.TimeoutError:
        print("  TIMEOUT: StreamReader streaming timed out")
        results.append(("streamreader", False, "Timeout"))
    except Exception as e:
        print(f"  FAILED: {e}")
        results.append(("streamreader", False, str(e)))

    await atv.close()
    return results


async def main(target_ip: str = None, scan_only: bool = False):
    """Main test function."""
    print("\n" + "#" * 60)
    print("# AirPlay Direct Streaming Tests")
    print("#" * 60)

    # Step 1: Generate test audio
    print("\nGenerating test audio...")
    mp3_data = generate_stereo_mp3(TEST_DURATION, TONE_FREQUENCY)
    print(f"Test audio: {len(mp3_data)} bytes, {TEST_DURATION}s, {TONE_FREQUENCY}Hz stereo")

    # Step 2: Discover devices
    devices = await discover_devices(target_ip, timeout=10)

    if scan_only:
        print("\nScan complete (--scan mode)")
        return len(devices) > 0

    if not devices:
        print("\nNo AirPlay devices found!")
        print("Suggestions:")
        print("  - Ensure devices are powered on")
        print("  - Check network connectivity")
        print("  - Try specifying IP with --ip option")
        return False

    # Step 3: Test streaming to each device
    all_results = {}
    for config in devices:
        results = await test_streaming_to_device(config, mp3_data)
        all_results[config.name] = results

    # Step 4: Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    overall_success = False
    for device_name, results in all_results.items():
        print(f"\n{device_name}:")
        for method, success, error in results:
            status = "PASS" if success else f"FAIL ({error})"
            print(f"  {method:15} {status}")
            if success:
                overall_success = True

    print(f"\nOverall: {'AT LEAST ONE METHOD WORKED' if overall_success else 'ALL METHODS FAILED'}")
    return overall_success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AirPlay streaming")
    parser.add_argument('--scan', action='store_true', help='Scan for devices only')
    parser.add_argument('--ip', type=str, default=DEFAULT_TARGET_IP, help=f'Target IP (default: {DEFAULT_TARGET_IP})')
    args = parser.parse_args()

    try:
        success = asyncio.run(main(args.ip, args.scan))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        sys.exit(130)
