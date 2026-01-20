#!/usr/bin/env python3
import time
import sys
import socket
from datetime import datetime

NEST_HUB_IP = '192.168.100.202'
TEST_STREAM_URL = 'http://ice1.somafm.com/groovesalad-128-mp3'
STREAM_CONTENT_TYPE = 'audio/mpeg'
PLAYBACK_DURATION = 10
CONNECTION_TIMEOUT = 30
PLAYBACK_TIMEOUT = 15

def log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f'[{timestamp}] {msg}')

def main():
    log('=' * 60)
    log('Chromecast/Nest Hub Audio Test')
    log('=' * 60)
    log(f'Target device: {NEST_HUB_IP}')
    log(f'Test stream: {TEST_STREAM_URL}')
    log(f'Playback duration: {PLAYBACK_DURATION} seconds')
    log('')
    
    try:
        import pychromecast
        try:
            from importlib.metadata import version as get_version
            version = get_version('pychromecast')
        except:
            version = 'unknown'
        log(f'pychromecast version: {version}')
    except ImportError as e:
        log(f'FAILED: Cannot import pychromecast: {e}')
        return 1
    
    cast = None
    browser = None
    test_passed = False
    
    try:
        log('')
        log('Step 1: Connecting to Nest Hub...')
        log(f'  Attempting connection to {NEST_HUB_IP}')
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((NEST_HUB_IP, 8009))
            sock.close()
            if result == 0:
                log(f'  Port 8009 is open on {NEST_HUB_IP}')
            else:
                log(f'  WARNING: Port 8009 appears closed (code: {result})')
        except Exception as e:
            log(f'  WARNING: Could not check port: {e}')
        
        start_time = time.time()
        log(f'  Scanning network (timeout: {CONNECTION_TIMEOUT}s)...')
        chromecasts, browser = pychromecast.get_chromecasts(timeout=CONNECTION_TIMEOUT)
        log(f'  Found {len(chromecasts)} device(s)')
        
        for cc in chromecasts:
            device_host = cc.cast_info.host if cc.cast_info else 'unknown'
            log(f'    - {cc.name} at {device_host}')
            if device_host == NEST_HUB_IP:
                cast = cc
                log('  => Matched target IP!')
        
        connection_time = time.time() - start_time
        
        if not cast:
            log(f'FAILED: No Chromecast found at {NEST_HUB_IP}')
            return 1
        
        log(f'  Device: {cast.name} ({cast.model_name})')
        log(f'  UUID: {cast.uuid}')
        log(f'  Connection time: {connection_time:.2f}s')
        
        log('  Waiting for device...')
        cast.wait(timeout=10)
        log(f'  Status: {cast.status}')
        log('  CONNECTION SUCCESS')
        
        log('')
        log('Step 2: Starting playback...')
        mc = cast.media_controller
        log(f'  Playing: {TEST_STREAM_URL}')
        mc.play_media(TEST_STREAM_URL, STREAM_CONTENT_TYPE, title='Sonorium Test')
        mc.block_until_active(timeout=10)
        
        log('')
        log('Step 3: Waiting for playback state...')
        playback_started = False
        start_wait = time.time()
        
        while time.time() - start_wait < PLAYBACK_TIMEOUT:
            mc.update_status()
            status = mc.status
            if status:
                state = status.player_state
                log(f'  State: {state}')
                if state in ['PLAYING', 'BUFFERING']:
                    playback_started = True
                    log(f'  PLAYBACK STARTED!')
                    break
                elif state == 'IDLE' and status.idle_reason:
                    log(f'  Idle: {status.idle_reason}')
                    if status.idle_reason == 'ERROR':
                        return 1
            time.sleep(1)
        
        if not playback_started:
            log(f'FAILED: No playback in {PLAYBACK_TIMEOUT}s')
            return 1
        
        log('')
        log(f'Step 4: Playing for {PLAYBACK_DURATION}s...')
        for i in range(PLAYBACK_DURATION):
            time.sleep(1)
            mc.update_status()
            if mc.status:
                pos = mc.status.current_time or 0
                log(f'  [{i+1}/{PLAYBACK_DURATION}s] {mc.status.player_state}, pos={pos:.1f}s')
        
        log('')
        log('Step 5: Stopping...')
        mc.stop()
        time.sleep(2)
        mc.update_status()
        final = mc.status.player_state if mc.status else 'UNKNOWN'
        log(f'  Final state: {final}')
        test_passed = final in ['IDLE', 'UNKNOWN']
        
    except Exception as e:
        log(f'FAILED: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if cast:
            try:
                cast.disconnect()
                log('  Disconnected')
            except:
                pass
        if browser:
            try:
                browser.stop_discovery()
            except:
                pass
    
    log('')
    log('=' * 60)
    if test_passed:
        log('TEST PASSED')
    else:
        log('TEST FAILED')
    log('=' * 60)
    return 0 if test_passed else 1

if __name__ == '__main__':
    sys.exit(main())
