"""
Test RAOP streamer with Arylic speaker at 192.168.1.74.

This test uses the raop_play binary to stream audio to an AirPlay 1 speaker.
Requires the binary to be built first.
"""

import asyncio
import sys
import os
import struct
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.sonorium.raop_streamer import RaopStreamer, RaopState


def generate_sine_wave(frequency: float, duration: float, sample_rate: int = 44100) -> bytes:
    """Generate a sine wave as PCM data (16-bit, stereo)."""
    num_samples = int(sample_rate * duration)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate
        # Generate sine wave at specified frequency
        value = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))
        # Stereo (same value for left and right)
        samples.append(struct.pack('<hh', value, value))

    return b''.join(samples)


async def test_streamer():
    """Test the RAOP streamer with generated audio."""
    # Target: Arylic speaker at 192.168.1.74
    host = "192.168.1.74"

    print(f"Testing RAOP streamer with {host}")
    print("=" * 50)

    # Find binary
    streamer = RaopStreamer()
    print(f"Binary path: {streamer.binary_path}")

    # Check if binary exists
    if not os.path.exists(streamer.binary_path):
        print(f"ERROR: Binary not found at {streamer.binary_path}")
        print("\nTo build the binary:")
        print("  1. SSH to Docker host: ssh root@192.168.1.150")
        print("  2. cd /tmp/libraop-builder")
        print("  3. docker-compose build --no-cache")
        print("  4. docker-compose up")
        print("  5. Copy output binaries")
        return

    # Set up callbacks
    def on_error(error):
        print(f"ERROR: {error}")

    def on_state_change(state):
        print(f"State: {state.value}")

    streamer.set_on_error(on_error)
    streamer.set_on_state_change(on_state_change)

    print(f"\nConnecting to {host}...")

    # Start streaming
    success = await streamer.start(host, volume=30)  # Low volume for testing

    if not success:
        print("Failed to connect!")
        return

    print("Connected! Generating test tone...")

    # Generate a pleasant A4 (440Hz) tone for 3 seconds
    print("Playing 440Hz sine wave for 3 seconds...")
    pcm_data = generate_sine_wave(440, 3.0)

    # Send in chunks
    chunk_size = 8192
    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i:i + chunk_size]
        if not await streamer.write(chunk):
            print("Failed to write audio data!")
            break
        # Small delay to prevent buffer overflow
        await asyncio.sleep(0.01)

    print("Audio sent, waiting for playback...")
    await asyncio.sleep(3)

    # Test pause/resume
    print("\nTesting pause...")
    await streamer.pause()
    await asyncio.sleep(1)

    print("Testing resume...")
    await streamer.resume()

    # Play another tone
    print("Playing 523Hz sine wave (C5) for 2 seconds...")
    pcm_data = generate_sine_wave(523.25, 2.0)

    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i:i + chunk_size]
        await streamer.write(chunk)
        await asyncio.sleep(0.01)

    await asyncio.sleep(2)

    # Stop
    print("\nStopping...")
    await streamer.stop()

    print("Test complete!")


async def test_with_http_stream():
    """Test streaming from an HTTP source."""
    # This would require a running audio server
    # For now, just demonstrate the pattern

    print("\nHTTP streaming example (not running without server):")
    print("""
    async with RaopStreamWriter("192.168.1.74", volume=50) as writer:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://server/stream.pcm") as response:
                async for chunk in response.content.iter_chunked(8192):
                    await writer.write(chunk)
    """)


if __name__ == "__main__":
    print("RAOP Streamer Test")
    print("=" * 50)
    asyncio.run(test_streamer())
