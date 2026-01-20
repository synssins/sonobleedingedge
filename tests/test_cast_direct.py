"""
Direct Cast test - bypasses Home Assistant to test raw Cast functionality.
"""
import time
import uuid
import pychromecast
from pychromecast import Chromecast
from pychromecast.models import CastInfo, HostServiceInfo

DEVICE_IP = "192.168.100.202"
DEVICE_PORT = 8009
DEVICE_NAME = "Office display"

def test_cast():
    print(f"Connecting directly to Cast device at {DEVICE_IP}:{DEVICE_PORT}...")

    # Create CastInfo manually for direct IP connection
    cast_info = CastInfo(
        services={HostServiceInfo(DEVICE_IP, DEVICE_PORT)},
        uuid=uuid.uuid4(),  # Generate a UUID since we don't know the real one
        model_name="Google Nest Hub",
        friendly_name=DEVICE_NAME,
        host=DEVICE_IP,
        port=DEVICE_PORT,
        cast_type="cast",
        manufacturer="Google Inc.",
    )

    try:
        cast = Chromecast(cast_info=cast_info)
    except Exception as e:
        print(f"ERROR connecting: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"Cast object created, waiting for connection...")

    # Wait for connection
    cast.wait()
    print(f"Connected! Status: {cast.status}")

    # Get media controller
    mc = cast.media_controller

    # Test 1: Remote URL (already confirmed working)
    print("\n--- Test 1: Remote URL ---")
    test_url = "https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3"
    print(f"Playing: {test_url}")
    mc.play_media(test_url, "audio/mpeg")
    mc.block_until_active()
    print(f"Player state: {mc.status.player_state}")
    time.sleep(3)

    # Test 2: Try a longer streaming URL (internet radio)
    print("\n--- Test 2: Internet Radio Stream ---")
    # SomaFM Drone Zone - a known working stream
    stream_url = "https://ice2.somafm.com/dronezone-128-mp3"
    print(f"Playing: {stream_url}")
    mc.play_media(stream_url, "audio/mpeg")
    time.sleep(2)
    mc.block_until_active(timeout=5)
    print(f"Player state: {mc.status.player_state}")
    print("Waiting 10 seconds...")
    time.sleep(10)
    print(f"Player state after 10s: {mc.status.player_state}")

    print("Stopping playback...")
    mc.stop()
    print("Test complete!")

if __name__ == "__main__":
    test_cast()
