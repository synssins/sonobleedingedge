# Arylic/Linkplay HTTP API Reference

> **Source:** https://developer.arylic.com/httpapi
> **Note:** This file is for reference only - NOT committed to git.

---

## Overview

Arylic speakers use the Linkplay platform and expose an HTTP API for control and status.

**Base URL Format:**
```
GET http://{device_ip}/httpapi.asp?command={command}
```

**Response Format:** JSON (unless otherwise specified)

---

## Test Devices

| Device | IP Address | Notes |
|--------|------------|-------|
| Office_C97a | 192.168.1.74 | Primary test device |
| Arylic-livingroom | 192.168.1.254 | Secondary |

---

## Device Information

### Get Device Status (Comprehensive)
```
GET /httpapi.asp?command=getStatusEx
```

Returns: Device metadata, firmware version, hardware type, network status, capabilities

### Get Playback Status
```
GET /httpapi.asp?command=getPlayerStatus
```

Returns:
```json
{
  "type": "0",           // 0=master, 1=guest
  "ch": "0",             // 0=stereo, 1=left, 2=right
  "mode": "10",          // Input source (see modes below)
  "status": "play",      // stop, play, pause, load
  "curpos": "12345",     // Position in milliseconds
  "totlen": "180000",    // Track length in milliseconds
  "Title": "48656C6C6F", // Hex-encoded metadata
  "Artist": "...",
  "Album": "...",
  "vol": "50",           // Volume 0-100
  "mute": "0"            // 0=unmuted, 1=muted
}
```

**Mode Values:**
| Mode | Source |
|------|--------|
| 0 | Idle |
| 1 | AirPlay |
| 2 | DLNA |
| 10 | Network stream |
| 11 | USB storage |
| 31 | Spotify Connect |
| 40 | Line-in |
| 41 | Bluetooth |

---

## Playback Control

### Play URL
```
GET /httpapi.asp?command=setPlayerCmd:play:{url}
```

### Play M3U Stream
```
GET /httpapi.asp?command=setPlayerCmd:m3u:play:{url}
```

### Pause/Resume/Stop
```
GET /httpapi.asp?command=setPlayerCmd:pause
GET /httpapi.asp?command=setPlayerCmd:resume
GET /httpapi.asp?command=setPlayerCmd:stop
```

### Seek
```
GET /httpapi.asp?command=setPlayerCmd:seek:{position_seconds}
```

### Next/Previous
```
GET /httpapi.asp?command=setPlayerCmd:next
GET /httpapi.asp?command=setPlayerCmd:prev
```

---

## Volume Control

### Set Volume (0-100)
```
GET /httpapi.asp?command=setPlayerCmd:vol:{level}
```

### Adjust Volume
```
GET /httpapi.asp?command=setPlayerCmd:vol--      # Decrease by 6
GET /httpapi.asp?command=setPlayerCmd:vol%2b%2b  # Increase by 6
```

### Mute/Unmute
```
GET /httpapi.asp?command=setPlayerCmd:mute:1     # Mute
GET /httpapi.asp?command=setPlayerCmd:mute:0     # Unmute
```

---

## Input Source Selection

```
GET /httpapi.asp?command=setPlayerCmd:switchmode:{mode}
```

**Modes:**
- `wifi` - Network streaming
- `line-in` - Analog input
- `bluetooth` - Bluetooth source
- `optical` - Optical digital
- `co-axial` - Coaxial digital
- `line-in2` - Secondary analog
- `udisk` - USB storage
- `PCUSB` - USB DAC mode

---

## Notification Playback

Play notification over current audio (with ducking):
```
GET /httpapi.asp?command=playPromptUrl:{url}
```

---

## Multiroom/Zone Commands

### Add Device to Group
```
GET /httpapi.asp?command=ConnectMasterAp:JoinGroupMaster:eth{ip}:wifi0.0.0.0
```

### List Guest Devices
```
GET /httpapi.asp?command=multiroom:getSlaveList
```

### Remove Device from Group
```
GET /httpapi.asp?command=multiroom:SlaveKickout:{ip}
```

### Dissolve Group
```
GET /httpapi.asp?command=multiroom:Ungroup
```

### Mute Guest Device
```
GET /httpapi.asp?command=multiroom:SlaveMute:{ip}:{0|1}
```

---

## Network Configuration

### List WiFi Networks
```
GET /httpapi.asp?command=wlanGetApListEx
```

### Connect to WiFi
```
GET /httpapi.asp?command=wlanConnectApEx
GET /httpapi.asp?command=wlanConnectHideApEx  # Hidden networks
```

### Get WiFi Status
```
GET /httpapi.asp?command=wlanGetConnectState
```

### Static IP Configuration
```
GET /httpapi.asp?command=getStaticIP
GET /httpapi.asp?command=setStaticIP:{json}
GET /httpapi.asp?command=setDhcp:{type}
```

---

## System Commands

### Reboot Device
```
GET /httpapi.asp?command=reboot
```

### Get System Log
```
GET /httpapi.asp?command=getsyslog
```

---

## Streaming Protocols Supported

Arylic/Linkplay devices support multiple streaming protocols:

| Protocol | Mode ID | Notes |
|----------|---------|-------|
| **AirPlay** | 1 | RAOP push streaming |
| **DLNA** | 2 | UPnP pull streaming |
| **Spotify Connect** | 31 | Native integration |
| **HTTP URL** | 10 | Direct URL playback |
| **Bluetooth** | 41 | A2DP sink |

---

## Data Encoding

String values (SSIDs, passwords, metadata) use **hexadecimal encoding**.

Example: "Hello" = "48656C6C6F"

---

## Response Codes

- `OK` - Success
- `PAIRFAIL` - Pairing failed
- `PROCESS` - Operation in progress
- `FAIL` - Operation failed

---

## Usage with Sonorium

### Check if AirPlay is Active
```python
import aiohttp

async def check_airplay_active(ip: str) -> bool:
    url = f"http://{ip}/httpapi.asp?command=getPlayerStatus"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return data.get("mode") == "1"  # Mode 1 = AirPlay
```

### Get Current Volume
```python
async def get_volume(ip: str) -> int:
    url = f"http://{ip}/httpapi.asp?command=getPlayerStatus"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            return int(data.get("vol", 50))
```

### Stop Any Current Playback
```python
async def stop_playback(ip: str):
    url = f"http://{ip}/httpapi.asp?command=setPlayerCmd:stop"
    async with aiohttp.ClientSession() as session:
        await session.get(url)
```
