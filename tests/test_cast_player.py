"""
Test Cast streaming functionality directly using pychromecast.
This simulates what CastPlayer does without requiring the full sonorium dependencies.
"""
import asyncio
import time
import uuid
import threading
import http.server
import socketserver
from concurrent.futures import ThreadPoolExecutor

import pychromecast
from pychromecast import Chromecast
from pychromecast.models import CastInfo, HostServiceInfo

# Test config
DEVICE_IP = "192.168.100.202"
LOCAL_IP = "192.168.1.198"
STREAM_PORT = 8889

_executor = ThreadPoolExecutor(max_workers=2)

# Entity ID patterns that indicate Cast devices (from cast_player.py)
CAST_ENTITY_PATTERNS = [
    '_display', '_hub', 'nest_', 'chromecast_', 'google_home_',
    'google_mini', 'google_max', '_speaker', 'cast_',
]

def is_cast_by_entity_pattern(entity_id: str) -> bool:
    """Check if entity ID matches Cast device patterns."""
    entity_lower = entity_id.lower()
    return any(pattern in entity_lower for pattern in CAST_ENTITY_PATTERNS)

# Simple MP3 stream server
def generate_mp3_silence():
    mp3_frame = bytes([0xFF, 0xFB, 0x90, 0x00] + [0x00] * 413)
    return mp3_frame

class StreamHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[SERVER] GET from {self.client_address}")
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        try:
            for i in range(500):  # Stream for ~13 seconds
                self.wfile.write(generate_mp3_silence())
                self.wfile.flush()
                time.sleep(0.026)
        except Exception as e:
            print(f"[SERVER] {e}")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.end_headers()

    def log_message(self, *args):
        pass

def start_server():
    with socketserver.TCPServer(("0.0.0.0", STREAM_PORT), StreamHandler) as httpd:
        print(f"[SERVER] Listening on {STREAM_PORT}")
        httpd.serve_forever()

def play_media_sync(ip: str, url: str) -> bool:
    """Play media on Cast device (sync, runs in thread)."""
    try:
        cast_info = CastInfo(
            services={HostServiceInfo(ip, 8009)},
            uuid=uuid.uuid4(),
            model_name=None,
            friendly_name=None,
            host=ip,
            port=8009,
            cast_type="cast",
            manufacturer="Google Inc.",
        )

        cast = Chromecast(cast_info=cast_info)
        cast.wait(timeout=10)
        print(f"[CAST] Connected to {ip}")

        mc = cast.media_controller
        mc.play_media(url, "audio/mpeg")

        # Wait for playback to start
        for _ in range(10):
            time.sleep(0.5)
            state = mc.status.player_state
            print(f"[CAST] State: {state}")
            if state in ('PLAYING', 'BUFFERING'):
                return True
            if mc.status.idle_reason:
                print(f"[CAST] Idle reason: {mc.status.idle_reason}")
                return False

        return False

    except Exception as e:
        print(f"[CAST] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_cast():
    # Start local stream server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    # Test entity pattern detection
    print("\n--- Testing Cast Detection by Entity Pattern ---")
    test_entities = [
        "media_player.office_display",
        "media_player.nest_hub",
        "media_player.living_room_speaker",
        "media_player.morning_room_display",  # The user's device!
        "media_player.sonos_office",
        "media_player.regular_player",
        "media_player.chromecast_living_room",
        "media_player.google_home_kitchen",
    ]
    for eid in test_entities:
        is_cast = is_cast_by_entity_pattern(eid)
        print(f"  {eid}: {'CAST' if is_cast else 'not cast'}")

    # Test playback
    print("\n--- Testing Playback to Nest Hub ---")
    stream_url = f"http://{LOCAL_IP}:{STREAM_PORT}/stream.mp3"
    print(f"Stream URL: {stream_url}")
    print(f"Device IP: {DEVICE_IP}")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, play_media_sync, DEVICE_IP, stream_url)
    print(f"Play result: {result}")

    if result:
        print("Waiting 10 seconds for playback...")
        await asyncio.sleep(10)

    print("\nTest complete!")

if __name__ == "__main__":
    asyncio.run(test_cast())
