"""
Test Cast with local HTTP streaming server.
This simulates what Sonorium does - serving an MP3 stream via HTTP.
"""
import time
import uuid
import threading
import http.server
import socketserver
import pychromecast
from pychromecast import Chromecast
from pychromecast.models import CastInfo, HostServiceInfo

DEVICE_IP = "192.168.100.202"
DEVICE_PORT = 8009
LOCAL_IP = "192.168.1.198"
STREAM_PORT = 8888

# Simple MP3 stream generator (silence with MP3 frames)
def generate_mp3_silence():
    """Generate MP3 silence frames."""
    # MP3 frame header for 128kbps, 44.1kHz, stereo
    # This is a valid MP3 frame of silence
    mp3_frame = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MPEG Audio Layer 3, 128kbps, 44.1kHz
    ] + [0x00] * 413)  # Padding to make ~418 bytes per frame
    return mp3_frame


class StreamHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[SERVER] GET request from {self.client_address}")
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

        print("[SERVER] Streaming MP3 silence...")
        try:
            frame_count = 0
            while True:
                frame = generate_mp3_silence()
                self.wfile.write(frame)
                self.wfile.flush()
                frame_count += 1
                if frame_count % 100 == 0:
                    print(f"[SERVER] Sent {frame_count} frames")
                time.sleep(0.026)  # ~38 frames/sec for 128kbps
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"[SERVER] Client disconnected: {e}")
        except Exception as e:
            print(f"[SERVER] Error: {e}")

    def do_HEAD(self):
        print(f"[SERVER] HEAD request from {self.client_address}")
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_server():
    with socketserver.TCPServer(("0.0.0.0", STREAM_PORT), StreamHandler) as httpd:
        print(f"[SERVER] Listening on port {STREAM_PORT}")
        httpd.serve_forever()


def test_local_stream():
    # Start local HTTP server in background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    print(f"Connecting to Cast device at {DEVICE_IP}...")

    cast_info = CastInfo(
        services={HostServiceInfo(DEVICE_IP, DEVICE_PORT)},
        uuid=uuid.uuid4(),
        model_name="Google Nest Hub",
        friendly_name="Office display",
        host=DEVICE_IP,
        port=DEVICE_PORT,
        cast_type="cast",
        manufacturer="Google Inc.",
    )

    cast = Chromecast(cast_info=cast_info)
    cast.wait()
    print(f"Connected!")

    mc = cast.media_controller

    # Play from local server
    stream_url = f"http://{LOCAL_IP}:{STREAM_PORT}/stream.mp3"
    print(f"\nPlaying local stream: {stream_url}")
    mc.play_media(stream_url, "audio/mpeg")

    time.sleep(2)
    try:
        mc.block_until_active(timeout=10)
    except Exception as e:
        print(f"block_until_active failed: {e}")

    print(f"Player state: {mc.status.player_state}")
    print(f"Idle reason: {mc.status.idle_reason}")

    print("Waiting 15 seconds...")
    for i in range(15):
        time.sleep(1)
        print(f"  {i+1}s - state: {mc.status.player_state}")

    print("Stopping...")
    mc.stop()
    print("Done!")


if __name__ == "__main__":
    test_local_stream()
