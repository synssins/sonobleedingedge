#!/usr/bin/env python3
"""
Patched pyatv Test

Applies a monkey-patch to pyatv to handle empty /info responses from
Arylic/Linkplay speakers, then tests streaming.

The patch makes pyatv's RTSP info() method return empty dict for empty responses,
just like it does for non-200 responses.
"""

import asyncio
import io
import logging
import argparse
import tempfile
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable pyatv debug logging
logging.getLogger('pyatv').setLevel(logging.DEBUG)


def apply_pyatv_patch():
    """Monkey-patch pyatv to handle empty /info responses."""
    import pyatv.support.rtsp as rtsp_module
    import pyatv.support.http as http_module
    import plistlib

    # Store original function
    original_decode = http_module.decode_bplist_from_body

    def patched_decode_bplist_from_body(response):
        """Patched version that handles empty bodies."""
        if not isinstance(response.body, (bytes, str)):
            raise Exception(f"expected bytes or str but got {type(response.body).__name__}")

        body = response.body
        if isinstance(body, str):
            body = body.encode("utf-8")

        # Handle empty body - return empty dict instead of failing
        if not body or len(body) == 0:
            logger.warning("Empty plist body received, returning empty dict")
            return {}

        try:
            return plistlib.loads(body)
        except plistlib.InvalidFileException as e:
            # If it's not a valid plist, log and return empty dict
            logger.warning(f"Invalid plist data ({len(body)} bytes), returning empty dict: {e}")
            return {}

    # Apply patch
    http_module.decode_bplist_from_body = patched_decode_bplist_from_body
    logger.info("Applied pyatv patch for empty /info responses")


# Apply patch before importing pyatv
apply_pyatv_patch()

import pyatv
from pyatv.const import Protocol
import numpy as np
import av


# Test configuration
DEFAULT_TARGET_IP = "192.168.1.74"
TEST_DURATION = 5  # seconds
TONE_FREQUENCY = 440  # Hz
SAMPLE_RATE = 44100
VOLUME = 0.3


def generate_stereo_mp3(duration: float, frequency: float) -> bytes:
    """Generate a stereo MP3 test tone using PyAV."""
    logger.info(f"Generating {duration}s stereo MP3 at {frequency}Hz...")

    num_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, num_samples, dtype=np.float32)
    mono = (VOLUME * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

    stereo_planar = np.vstack([mono, mono])

    buffer = io.BytesIO()
    container = av.open(buffer, mode='w', format='mp3')
    stream = container.add_stream('mp3', rate=SAMPLE_RATE)
    stream.bit_rate = 128000

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


async def discover_device(target_ip: str, timeout: int = 10):
    """Discover device at target IP."""
    logger.info(f"Scanning for devices (looking for {target_ip})...")

    # Get event loop for older pyatv versions
    loop = asyncio.get_event_loop()

    # Use broadcast scan - more reliable than host-specific
    all_devices = await pyatv.scan(loop, timeout=timeout)

    # Filter to target IP
    devices = [d for d in all_devices if str(d.address) == target_ip]

    if not devices:
        logger.error(f"No device found at {target_ip}")
        logger.info(f"Found {len(all_devices)} other devices:")
        for d in all_devices:
            logger.info(f"  - {d.name} ({d.address})")
        return None

    device = devices[0]
    logger.info(f"Found: {device.name} ({device.address})")

    # Log services
    for service in device.services:
        logger.info(f"  Service: {service.protocol.name} on port {service.port}")

    return device


async def test_streaming(config, mp3_data: bytes):
    """Test streaming to device."""
    logger.info(f"Connecting to {config.name}...")

    loop = asyncio.get_event_loop()

    try:
        atv = await pyatv.connect(config, loop)
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    if not atv.stream:
        logger.error("No stream interface available")
        await atv.close()
        return False

    logger.info("Connected! Stream interface available.")

    # Try file-based streaming
    logger.info("Testing file-based streaming...")
    temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    temp_file.write(mp3_data)
    temp_file.close()

    try:
        await asyncio.wait_for(
            atv.stream.stream_file(temp_file.name),
            timeout=TEST_DURATION + 30
        )
        logger.info("SUCCESS: File streaming completed!")
        result = True
    except asyncio.TimeoutError:
        logger.warning("File streaming timed out")
        result = False
    except Exception as e:
        logger.error(f"File streaming failed: {e}")
        import traceback
        traceback.print_exc()
        result = False
    finally:
        os.unlink(temp_file.name)

    # Close connection - handle both sync and async versions
    try:
        close_result = atv.close()
        if asyncio.iscoroutine(close_result):
            await close_result
    except Exception as e:
        logger.warning(f"Close error (ignored): {e}")

    return result


async def main(target_ip: str):
    """Main test function."""
    print("\n" + "#" * 60)
    print("# Patched pyatv AirPlay Streaming Test")
    print("#" * 60)

    # Generate test audio
    mp3_data = generate_stereo_mp3(TEST_DURATION, TONE_FREQUENCY)

    # Discover device
    config = await discover_device(target_ip)
    if not config:
        return False

    # Test streaming
    success = await test_streaming(config, mp3_data)

    print("\n" + "=" * 60)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
    print("=" * 60)

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patched pyatv streaming test")
    parser.add_argument('--ip', type=str, default=DEFAULT_TARGET_IP,
                       help=f'Target IP (default: {DEFAULT_TARGET_IP})')
    args = parser.parse_args()

    try:
        success = asyncio.run(main(args.ip))
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        exit(130)
