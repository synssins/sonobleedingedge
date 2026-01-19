#!/usr/bin/env python3
"""
Manual RAOP Streaming Test

Implements direct RAOP/AirPlay audio streaming without relying on pyatv's /info parsing.
Tests basic RAOP handshake and audio transmission to Arylic/Linkplay speakers.

Protocol sequence:
1. ANNOUNCE - Describe the audio stream (SDP)
2. SETUP - Establish RTP transport
3. RECORD - Start streaming
4. [Send audio via RTP]
5. TEARDOWN - End session
"""

import asyncio
import socket
import struct
import time
import io
import logging
import argparse
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
DEFAULT_TARGET_IP = "192.168.1.74"
DEFAULT_TARGET_PORT = 4515
TEST_DURATION = 5  # seconds
TONE_FREQUENCY = 440  # Hz (A4 note)
SAMPLE_RATE = 44100
VOLUME = 0.3


class RAOPClient:
    """Simple RAOP client for testing audio streaming."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.cseq = 0
        self.session_id = None
        self.server_port = None
        self.timing_port = None
        self.control_port = None
        self.client_port = None

    async def connect(self):
        """Connect to the RAOP server."""
        logger.info(f"Connecting to {self.host}:{self.port}...")
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        logger.info("Connected!")

    async def send_request(self, method: str, uri: str, headers: dict = None, body: str = None) -> tuple[dict, str]:
        """Send RTSP request and return response headers and body."""
        self.cseq += 1

        # Build request
        lines = [f"{method} {uri} RTSP/1.0"]
        lines.append(f"CSeq: {self.cseq}")
        lines.append("User-Agent: Sonorium/1.0")

        if headers:
            for key, value in headers.items():
                lines.append(f"{key}: {value}")

        if body:
            lines.append(f"Content-Length: {len(body)}")
            lines.append(f"Content-Type: application/sdp")

        lines.append("")  # Empty line before body

        if body:
            lines.append(body)

        request = "\r\n".join(lines)
        if not request.endswith("\r\n"):
            request += "\r\n"

        logger.debug(f"Sending:\n{request}")
        self.writer.write(request.encode('utf-8'))
        await self.writer.drain()

        # Read response
        response_data = await asyncio.wait_for(self.reader.read(8192), timeout=10)
        response_text = response_data.decode('utf-8', errors='replace')
        logger.debug(f"Received:\n{response_text}")

        # Parse response
        lines = response_text.split('\r\n')
        status_line = lines[0]

        # Parse headers
        resp_headers = {}
        body_start = 0
        for i, line in enumerate(lines[1:], 1):
            if line == '':
                body_start = i + 1
                break
            if ':' in line:
                key, value = line.split(':', 1)
                resp_headers[key.strip()] = value.strip()

        resp_body = '\r\n'.join(lines[body_start:]) if body_start < len(lines) else ''

        return status_line, resp_headers, resp_body

    async def announce(self) -> bool:
        """Send ANNOUNCE with SDP describing the audio stream."""
        logger.info("Sending ANNOUNCE...")

        # Generate session ID and random port
        self.session_id = str(random.randint(1000000000, 9999999999))
        self.client_port = random.randint(49152, 65535)

        # SDP describing ALAC audio stream (what AirPlay/RAOP expects)
        # Using PCM for simplicity (cn=1 from mDNS means PCM is supported)
        sdp = (
            "v=0\r\n"
            f"o=iTunes {self.session_id} 0 IN IP4 {self._get_local_ip()}\r\n"
            "s=Sonorium\r\n"
            f"c=IN IP4 {self._get_local_ip()}\r\n"
            "t=0 0\r\n"
            "m=audio 0 RTP/AVP 96\r\n"
            "a=rtpmap:96 L16/44100/2\r\n"  # 16-bit PCM, 44.1kHz, stereo
            "a=fmtp:96 4096 0 16 40 10 14 2 255 0 0 44100\r\n"
        )

        status, headers, body = await self.send_request(
            "ANNOUNCE",
            f"rtsp://{self.host}/{self.session_id}",
            {},
            sdp
        )

        if "200 OK" in status:
            logger.info("ANNOUNCE accepted!")
            return True
        else:
            logger.error(f"ANNOUNCE failed: {status}")
            return False

    async def setup(self) -> bool:
        """Send SETUP to establish transport."""
        logger.info("Sending SETUP...")

        # Request RTP transport
        transport = f"RTP/AVP/UDP;unicast;interleaved=0-1;mode=record;control_port={self.client_port};timing_port={self.client_port + 1}"

        status, headers, body = await self.send_request(
            "SETUP",
            f"rtsp://{self.host}/{self.session_id}",
            {"Transport": transport}
        )

        if "200 OK" in status:
            logger.info("SETUP accepted!")

            # Parse Transport header for server ports
            if "Transport" in headers:
                transport_resp = headers["Transport"]
                logger.info(f"Transport: {transport_resp}")

                # Extract server_port
                for part in transport_resp.split(';'):
                    if part.startswith('server_port='):
                        self.server_port = int(part.split('=')[1])
                    elif part.startswith('control_port='):
                        self.control_port = int(part.split('=')[1])
                    elif part.startswith('timing_port='):
                        self.timing_port = int(part.split('=')[1])

            # Get Session header
            if "Session" in headers:
                self.session_id = headers["Session"]

            logger.info(f"Server ports: audio={self.server_port}, control={self.control_port}, timing={self.timing_port}")
            return True
        else:
            logger.error(f"SETUP failed: {status}")
            return False

    async def record(self) -> bool:
        """Send RECORD to start streaming."""
        logger.info("Sending RECORD...")

        headers = {
            "Range": "npt=0-",
            "RTP-Info": f"seq=0;rtptime=0"
        }

        if self.session_id:
            headers["Session"] = self.session_id

        status, resp_headers, body = await self.send_request(
            "RECORD",
            f"rtsp://{self.host}/{self.session_id}",
            headers
        )

        if "200 OK" in status:
            logger.info("RECORD accepted - streaming started!")
            return True
        else:
            logger.error(f"RECORD failed: {status}")
            return False

    async def set_volume(self, volume: float = -30.0) -> bool:
        """Set volume via SET_PARAMETER."""
        logger.info(f"Setting volume to {volume}dB...")

        body = f"volume: {volume}\r\n"
        headers = {
            "Content-Type": "text/parameters"
        }
        if self.session_id:
            headers["Session"] = self.session_id

        status, resp_headers, resp_body = await self.send_request(
            "SET_PARAMETER",
            f"rtsp://{self.host}/{self.session_id}",
            headers,
            body
        )

        return "200 OK" in status

    async def teardown(self):
        """Send TEARDOWN to end session."""
        logger.info("Sending TEARDOWN...")
        try:
            headers = {}
            if self.session_id:
                headers["Session"] = self.session_id

            await self.send_request(
                "TEARDOWN",
                f"rtsp://{self.host}/{self.session_id}",
                headers
            )
        except Exception as e:
            logger.warning(f"TEARDOWN error: {e}")

    async def close(self):
        """Close connection."""
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except:
                pass
        logger.info("Connection closed")

    def _get_local_ip(self) -> str:
        """Get local IP address."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((self.host, 80))
            return s.getsockname()[0]
        finally:
            s.close()


async def send_rtp_audio(host: str, port: int, duration: float, frequency: float):
    """Send RTP audio packets."""
    import numpy as np

    logger.info(f"Sending RTP audio to {host}:{port}...")

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # RTP header values
    sequence = 0
    timestamp = 0
    ssrc = random.randint(0, 0xFFFFFFFF)

    # Generate audio samples
    samples_per_packet = 352  # Standard for ALAC/RAOP
    bytes_per_sample = 4  # 16-bit stereo = 4 bytes

    # Calculate how many packets to send
    packets_to_send = int((duration * SAMPLE_RATE) / samples_per_packet)

    logger.info(f"Sending {packets_to_send} RTP packets ({duration}s of audio)...")

    start_time = time.time()

    for packet_num in range(packets_to_send):
        # Generate sine wave samples for this packet
        t_start = packet_num * samples_per_packet / SAMPLE_RATE
        t = np.linspace(t_start, t_start + samples_per_packet / SAMPLE_RATE, samples_per_packet)
        samples = (VOLUME * 32767 * np.sin(2 * np.pi * frequency * t)).astype(np.int16)

        # Interleave for stereo (L, R, L, R, ...)
        stereo = np.zeros(samples_per_packet * 2, dtype='>i2')  # Big-endian
        stereo[0::2] = samples  # Left
        stereo[1::2] = samples  # Right

        # Build RTP header (12 bytes)
        # Byte 0: V=2, P=0, X=0, CC=0 => 0x80
        # Byte 1: M=1 (first packet marker), PT=96 => 0xE0 or 0x60
        rtp_header = struct.pack(
            '>BBHII',
            0x80,  # V=2
            96,    # PT=96 (dynamic)
            sequence & 0xFFFF,
            timestamp & 0xFFFFFFFF,
            ssrc
        )

        # Build packet
        packet = rtp_header + stereo.tobytes()

        # Send
        sock.sendto(packet, (host, port))

        sequence += 1
        timestamp += samples_per_packet

        # Maintain timing
        elapsed = time.time() - start_time
        expected = (packet_num + 1) * samples_per_packet / SAMPLE_RATE
        if expected > elapsed:
            await asyncio.sleep(expected - elapsed)

        if packet_num % 100 == 0:
            logger.info(f"Sent {packet_num}/{packets_to_send} packets...")

    logger.info(f"Finished sending {packets_to_send} RTP packets")
    sock.close()


async def test_streaming(host: str, port: int, duration: float):
    """Test RAOP streaming to device."""
    client = RAOPClient(host, port)

    try:
        await client.connect()

        # Run RAOP handshake
        if not await client.announce():
            return False

        if not await client.setup():
            return False

        # Set volume
        await client.set_volume(-20.0)

        if not await client.record():
            return False

        # Send audio
        if client.server_port:
            await send_rtp_audio(host, client.server_port, duration, TONE_FREQUENCY)
        else:
            logger.error("No server port - cannot send audio")
            return False

        await asyncio.sleep(1)  # Let audio finish
        await client.teardown()
        return True

    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.close()


async def main(host: str, port: int):
    """Main test function."""
    print("\n" + "#" * 60)
    print("# Manual RAOP Streaming Test")
    print("#" * 60)
    print(f"\nTarget: {host}:{port}")
    print(f"Duration: {TEST_DURATION}s")
    print(f"Frequency: {TONE_FREQUENCY}Hz")

    success = await test_streaming(host, port, TEST_DURATION)

    print("\n" + "=" * 60)
    print(f"Result: {'SUCCESS' if success else 'FAILED'}")
    print("=" * 60)

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual RAOP streaming test")
    parser.add_argument('--ip', type=str, default=DEFAULT_TARGET_IP,
                       help=f'Target IP (default: {DEFAULT_TARGET_IP})')
    parser.add_argument('--port', type=int, default=DEFAULT_TARGET_PORT,
                       help=f'Target port (default: {DEFAULT_TARGET_PORT})')
    args = parser.parse_args()

    try:
        success = asyncio.run(main(args.ip, args.port))
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
        exit(130)
