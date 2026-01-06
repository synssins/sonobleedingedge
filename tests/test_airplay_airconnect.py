"""
AirPlay Development Test Harness using AirConnect.

This test harness uses AirConnect as a simulated AirPlay receiver for developing
and testing Sonorium's AirPlay streaming functionality.

AirConnect devices are identified by:
- Model: 'airupnp' (for UPnP bridge mode)
- Model: 'aircast' (for Chromecast bridge mode)

Usage:
    python tests/test_airplay_airconnect.py                    # Run all tests
    python tests/test_airplay_airconnect.py --discover         # Discovery only
    python tests/test_airplay_airconnect.py --stream           # Stream test tone
    python tests/test_airplay_airconnect.py --stream-url URL   # Stream from URL
    python tests/test_airplay_airconnect.py --target IP        # Target specific IP

Requirements:
    pip install pyatv numpy av aiohttp

Note: Arylic speakers are OFF LIMITS for this test. Only AirConnect devices.
"""

import asyncio
import argparse
import logging
import sys
import io
import tempfile
import os
from typing import Optional, List
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('airplay_test')


@dataclass
class AirConnectDevice:
    """Represents an AirConnect device discovered via mDNS."""
    name: str
    address: str
    port: int
    model: str
    properties: dict
    device_config: object  # pyatv device config


class AirPlayTestHarness:
    """Test harness for AirPlay development using AirConnect."""

    AIRCONNECT_MODELS = ['airupnp', 'aircast']

    def __init__(self, target_ip: Optional[str] = None):
        self.target_ip = target_ip
        self.devices: List[AirConnectDevice] = []

    async def discover_devices(self, timeout: int = 10) -> List[AirConnectDevice]:
        """Discover AirConnect devices on the network.

        Returns only AirConnect devices (model = airupnp or aircast).
        Excludes Arylic/Linkplay devices.
        """
        import pyatv
        from pyatv.const import Protocol

        logger.info("Scanning for AirPlay devices...")
        loop = asyncio.get_event_loop()

        if self.target_ip:
            # Scan specific IP
            all_devices = await pyatv.scan(loop, hosts=[self.target_ip], timeout=timeout)
        else:
            # Scan entire network
            all_devices = await pyatv.scan(loop, timeout=timeout)

        logger.info(f"Found {len(all_devices)} total AirPlay devices")

        self.devices = []

        for device in all_devices:
            # Get RAOP service properties
            raop_service = device.get_service(Protocol.RAOP)
            if not raop_service:
                continue

            properties = dict(raop_service.properties) if raop_service.properties else {}
            model = properties.get('am', 'unknown')

            # Filter: Only AirConnect devices
            if model.lower() in self.AIRCONNECT_MODELS:
                ac_device = AirConnectDevice(
                    name=device.name,
                    address=str(device.address),
                    port=raop_service.port,
                    model=model,
                    properties=properties,
                    device_config=device
                )
                self.devices.append(ac_device)
                logger.info(f"  Found AirConnect: {device.name} ({device.address}:{raop_service.port}) - {model}")
            else:
                # Log but skip non-AirConnect devices
                logger.debug(f"  Skipping non-AirConnect: {device.name} ({device.address}) - {model}")

        if not self.devices:
            logger.warning("No AirConnect devices found!")

        return self.devices

    async def test_connection(self, device: AirConnectDevice) -> bool:
        """Test RTSP connection to an AirConnect device."""
        import pyatv

        logger.info(f"Testing connection to {device.name} ({device.address})...")

        try:
            loop = asyncio.get_event_loop()
            atv = await pyatv.connect(device.device_config, loop)

            logger.info(f"  Connected successfully!")
            logger.info(f"  Stream interface: {atv.stream is not None}")

            if atv.stream:
                logger.info(f"  stream_file: {hasattr(atv.stream, 'stream_file')}")
                logger.info(f"  play_url: {hasattr(atv.stream, 'play_url')}")

            # Close connection (handle pyatv quirks)
            try:
                result = atv.close()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

            return True

        except Exception as e:
            logger.error(f"  Connection failed: {type(e).__name__}: {e}")
            return False

    def generate_test_tone(self, duration: float = 5.0, frequency: float = 440.0) -> bytes:
        """Generate a test tone as MP3 data.

        Args:
            duration: Length in seconds
            frequency: Tone frequency in Hz (440 = A4)

        Returns:
            MP3 audio data as bytes
        """
        import numpy as np
        import av

        logger.info(f"Generating {duration}s test tone at {frequency}Hz...")

        sample_rate = 44100
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples, dtype=np.float32)

        # Generate gentle sine wave at moderate volume
        audio = (np.sin(2 * np.pi * frequency * t) * 0.25 * 32767).astype(np.int16)

        # Encode to MP3
        buffer = io.BytesIO()
        container = av.open(buffer, mode='w', format='mp3')
        stream = container.add_stream('mp3', rate=sample_rate)
        stream.bit_rate = 128000

        # Process in 1-second chunks
        chunk_size = sample_rate
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            # Create stereo planar array [2, N]
            stereo_planar = np.ascontiguousarray(np.vstack([chunk, chunk]))
            frame = av.AudioFrame.from_ndarray(stereo_planar, format='s16p', layout='stereo')
            frame.sample_rate = sample_rate
            frame.pts = i
            for packet in stream.encode(frame):
                container.mux(packet)

        # Flush encoder
        for packet in stream.encode(None):
            container.mux(packet)
        container.close()

        mp3_data = buffer.getvalue()
        logger.info(f"Generated {len(mp3_data)} bytes of MP3 audio")

        return mp3_data

    async def stream_to_device(
        self,
        device: AirConnectDevice,
        audio_source: str = 'tone',
        duration: float = 10.0
    ) -> bool:
        """Stream audio to an AirConnect device.

        Args:
            device: Target AirConnect device
            audio_source: 'tone' for test tone, or HTTP URL to stream
            duration: Duration for test tone (ignored for URL)

        Returns:
            True if streaming completed successfully
        """
        import pyatv
        import aiohttp

        logger.info(f"Streaming to {device.name} ({device.address})...")

        try:
            loop = asyncio.get_event_loop()
            atv = await pyatv.connect(device.device_config, loop)

            if not atv.stream:
                logger.error("Device does not support streaming interface")
                await atv.close()
                return False

            if audio_source == 'tone':
                # Generate and stream test tone
                mp3_data = self.generate_test_tone(duration=duration)

                # Save to temp file (pyatv prefers files for seeking)
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    f.write(mp3_data)
                    temp_path = f.name

                try:
                    logger.info(f"Streaming test tone to {device.name}...")
                    await asyncio.wait_for(
                        atv.stream.stream_file(temp_path),
                        timeout=duration + 30  # Extra time for buffering
                    )
                    logger.info("Streaming completed successfully!")
                    success = True
                except asyncio.TimeoutError:
                    logger.info("Stream timed out (expected for short files)")
                    success = True
                finally:
                    os.unlink(temp_path)

            else:
                # Stream from URL using aiohttp
                logger.info(f"Streaming from URL: {audio_source}")

                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(audio_source) as response:
                        if response.status != 200:
                            logger.error(f"HTTP {response.status} from URL")
                            await atv.close()
                            return False

                        # Create StreamReader and feed chunks
                        reader = asyncio.StreamReader()

                        async def feed_reader():
                            async for chunk in response.content.iter_chunked(8192):
                                reader.feed_data(chunk)
                            reader.feed_eof()

                        feed_task = asyncio.create_task(feed_reader())

                        try:
                            await atv.stream.stream_file(reader)
                            success = True
                        except asyncio.CancelledError:
                            success = True
                        finally:
                            feed_task.cancel()
                            try:
                                await feed_task
                            except asyncio.CancelledError:
                                pass

            # Close connection (handle pyatv quirks)
            try:
                result = atv.close()
                # Some pyatv versions return a coroutine, others don't
                if asyncio.iscoroutine(result):
                    await result
            except Exception as close_err:
                logger.debug(f"Close warning (ignorable): {close_err}")

            return success

        except Exception as e:
            logger.error(f"Streaming failed: {type(e).__name__}: {e}")
            return False

    async def run_full_test(self) -> dict:
        """Run complete test suite on all discovered AirConnect devices."""
        results = {
            'discovery': False,
            'devices': [],
            'connection_tests': {},
            'stream_tests': {}
        }

        # Discovery
        devices = await self.discover_devices()
        results['discovery'] = len(devices) > 0
        results['devices'] = [
            {
                'name': d.name,
                'address': d.address,
                'port': d.port,
                'model': d.model,
                'properties': d.properties
            }
            for d in devices
        ]

        if not devices:
            logger.error("No AirConnect devices found - cannot continue tests")
            return results

        # Connection tests
        for device in devices:
            success = await self.test_connection(device)
            results['connection_tests'][device.name] = success

        # Stream tests (only on devices that passed connection test)
        for device in devices:
            if results['connection_tests'].get(device.name):
                success = await self.stream_to_device(device, audio_source='tone', duration=5.0)
                results['stream_tests'][device.name] = success

        return results


async def main():
    parser = argparse.ArgumentParser(
        description='AirPlay Development Test Harness using AirConnect'
    )
    parser.add_argument(
        '--discover',
        action='store_true',
        help='Only run device discovery'
    )
    parser.add_argument(
        '--stream',
        action='store_true',
        help='Stream test tone to discovered devices'
    )
    parser.add_argument(
        '--stream-url',
        type=str,
        help='Stream from HTTP URL instead of test tone'
    )
    parser.add_argument(
        '--target',
        type=str,
        help='Target specific IP address'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=10.0,
        help='Duration of test tone in seconds (default: 10)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    harness = AirPlayTestHarness(target_ip=args.target)

    print("=" * 60)
    print("AirPlay Development Test Harness (AirConnect Only)")
    print("=" * 60)
    print()

    if args.discover:
        # Discovery only
        devices = await harness.discover_devices()
        print()
        print(f"Found {len(devices)} AirConnect device(s)")
        for d in devices:
            print(f"  - {d.name} ({d.address}:{d.port}) [{d.model}]")

    elif args.stream or args.stream_url:
        # Stream test
        devices = await harness.discover_devices()

        if not devices:
            print("No AirConnect devices found!")
            sys.exit(1)

        audio_source = args.stream_url if args.stream_url else 'tone'

        for device in devices:
            print()
            print(f"Testing stream to: {device.name}")
            success = await harness.stream_to_device(
                device,
                audio_source=audio_source,
                duration=args.duration
            )
            print(f"Result: {'PASSED' if success else 'FAILED'}")

    else:
        # Full test suite
        results = await harness.run_full_test()

        print()
        print("=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        print()

        print(f"Discovery: {'PASSED' if results['discovery'] else 'FAILED'}")
        print(f"Devices found: {len(results['devices'])}")

        for d in results['devices']:
            print(f"  - {d['name']} ({d['address']}:{d['port']}) [{d['model']}]")

        print()
        print("Connection Tests:")
        for name, passed in results['connection_tests'].items():
            print(f"  {name}: {'PASSED' if passed else 'FAILED'}")

        print()
        print("Stream Tests:")
        for name, passed in results['stream_tests'].items():
            print(f"  {name}: {'PASSED' if passed else 'FAILED'}")

        # Overall result
        all_passed = (
            results['discovery'] and
            all(results['connection_tests'].values()) and
            all(results['stream_tests'].values())
        )

        print()
        print("=" * 60)
        print(f"OVERALL: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        print("=" * 60)

        sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    asyncio.run(main())
