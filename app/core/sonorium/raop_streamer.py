"""
RAOP Streamer - Python wrapper for libraop/raop_play binary.

This module provides AirPlay 1 (RAOP) streaming using the libraop binary.
It supports streaming PCM audio to AirPlay-compatible speakers.

Usage:
    streamer = RaopStreamer()
    await streamer.start("192.168.1.74", volume=50)
    # Feed PCM data
    await streamer.write(pcm_data)  # 16-bit, 44.1kHz, stereo
    await streamer.stop()
"""

import asyncio
import logging
import platform
import subprocess
import os
from pathlib import Path
from typing import Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class RaopState(Enum):
    """State of the RAOP streamer."""
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class RaopStreamer:
    """
    Python wrapper for libraop's raop_play binary.

    Provides async interface for streaming PCM audio to AirPlay 1 speakers.
    """

    def __init__(self, binary_path: Optional[str] = None):
        """
        Initialize the RAOP streamer.

        Args:
            binary_path: Path to raop_play binary. If None, auto-detects.
        """
        self.binary_path = binary_path or self._find_binary()
        self.process: Optional[asyncio.subprocess.Process] = None
        self.state = RaopState.IDLE
        self.host: Optional[str] = None
        self.volume: int = 50
        self._stderr_task: Optional[asyncio.Task] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_state_change: Optional[Callable[[RaopState], None]] = None

    def _find_binary(self) -> str:
        """Find the raop_play binary for the current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Determine binary name
        if system == "windows":
            binary_name = "raop_play-windows-x64.exe"
        elif system == "darwin":
            if "arm" in machine or "aarch64" in machine:
                binary_name = "raop_play-macos-arm64"
            else:
                binary_name = "raop_play-macos-x64"
        else:  # Linux
            if "aarch64" in machine or "arm64" in machine:
                binary_name = "raop_play-linux-aarch64"
            else:
                binary_name = "raop_play-linux-x86_64"

        # Look for binary in common locations
        search_paths = [
            # Same directory as this module
            Path(__file__).parent / "bin" / binary_name,
            # Build output directory
            Path(__file__).parent.parent.parent.parent / "build" / "docker" / "libraop-builder" / "output" / binary_name,
            # Current directory
            Path.cwd() / binary_name,
            # System PATH
            binary_name,
        ]

        for path in search_paths:
            if isinstance(path, Path):
                if path.exists():
                    logger.info(f"Found raop_play binary at: {path}")
                    return str(path)
            else:
                # Check if it's in PATH
                try:
                    result = subprocess.run(
                        ["which" if system != "windows" else "where", path],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        found_path = result.stdout.strip().split("\n")[0]
                        logger.info(f"Found raop_play binary in PATH: {found_path}")
                        return found_path
                except Exception:
                    pass

        logger.warning(f"raop_play binary not found. Expected: {binary_name}")
        return binary_name  # Return name anyway, will fail at runtime

    def set_on_error(self, callback: Callable[[str], None]):
        """Set callback for error events."""
        self._on_error = callback

    def set_on_state_change(self, callback: Callable[[RaopState], None]):
        """Set callback for state change events."""
        self._on_state_change = callback

    def _set_state(self, state: RaopState):
        """Set state and notify callback."""
        old_state = self.state
        self.state = state
        if self._on_state_change and old_state != state:
            try:
                self._on_state_change(state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    async def start(
        self,
        host: str,
        port: int = 7000,
        volume: int = 50,
        latency: int = 0,
        encryption: bool = False,
        interactive: bool = True
    ) -> bool:
        """
        Start streaming to an AirPlay device.

        Args:
            host: IP address of the AirPlay device
            port: RAOP port (default 5000)
            volume: Volume level 0-100
            latency: Audio latency in frames
            encryption: Whether to use encryption
            interactive: Enable interactive mode for commands

        Returns:
            True if started successfully
        """
        if self.process is not None:
            logger.warning("RAOP streamer already running, stopping first")
            await self.stop()

        self.host = host
        self.volume = volume
        self._set_state(RaopState.CONNECTING)

        # Build command
        cmd = [self.binary_path, host]
        cmd.extend(["-v", str(volume)])
        cmd.extend(["-p", str(port)])

        if latency > 0:
            cmd.extend(["-l", str(latency)])
        if encryption:
            cmd.append("-e")
        if interactive:
            cmd.append("-i")

        logger.info(f"Starting RAOP streamer: {' '.join(cmd)}")

        try:
            # Start the process with stdin for audio data
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Start stderr reader task
            self._stderr_task = asyncio.create_task(self._read_stderr())

            # Give it a moment to connect
            await asyncio.sleep(0.5)

            # Check if process is still running
            if self.process.returncode is not None:
                stderr = await self.process.stderr.read()
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                logger.error(f"RAOP process exited immediately: {error_msg}")
                self._set_state(RaopState.ERROR)
                if self._on_error:
                    self._on_error(error_msg)
                return False

            self._set_state(RaopState.STREAMING)
            logger.info(f"RAOP streamer connected to {host}")
            return True

        except FileNotFoundError:
            error_msg = f"raop_play binary not found: {self.binary_path}"
            logger.error(error_msg)
            self._set_state(RaopState.ERROR)
            if self._on_error:
                self._on_error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to start RAOP streamer: {e}"
            logger.error(error_msg)
            self._set_state(RaopState.ERROR)
            if self._on_error:
                self._on_error(error_msg)
            return False

    async def _read_stderr(self):
        """Read stderr from the process for status/errors."""
        try:
            while self.process and self.process.returncode is None:
                line = await self.process.stderr.readline()
                if not line:
                    break
                line_str = line.decode().strip()
                if line_str:
                    logger.debug(f"RAOP stderr: {line_str}")
                    # Check for error conditions
                    if "error" in line_str.lower() or "failed" in line_str.lower():
                        if self._on_error:
                            self._on_error(line_str)
        except Exception as e:
            logger.debug(f"RAOP stderr reader ended: {e}")

    async def write(self, pcm_data: bytes) -> bool:
        """
        Write PCM audio data to the stream.

        Args:
            pcm_data: Raw PCM data (16-bit, 44.1kHz, stereo, little-endian)

        Returns:
            True if data was written successfully
        """
        if not self.process or not self.process.stdin:
            logger.error("RAOP streamer not running")
            return False

        if self.state != RaopState.STREAMING:
            logger.warning(f"Cannot write data in state {self.state}")
            return False

        try:
            self.process.stdin.write(pcm_data)
            await self.process.stdin.drain()
            return True
        except Exception as e:
            logger.error(f"Failed to write audio data: {e}")
            self._set_state(RaopState.ERROR)
            return False

    async def send_command(self, command: str) -> bool:
        """
        Send an interactive command to raop_play.

        Commands:
            p - pause
            r - resume
            s - stop
            q - quit
            + - volume up
            - - volume down

        Args:
            command: Single character command

        Returns:
            True if command was sent
        """
        if not self.process or not self.process.stdin:
            logger.error("RAOP streamer not running")
            return False

        try:
            self.process.stdin.write(command.encode())
            await self.process.stdin.drain()
            logger.debug(f"Sent command: {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False

    async def pause(self) -> bool:
        """Pause playback."""
        if await self.send_command("p"):
            self._set_state(RaopState.PAUSED)
            return True
        return False

    async def resume(self) -> bool:
        """Resume playback."""
        if await self.send_command("r"):
            self._set_state(RaopState.STREAMING)
            return True
        return False

    async def set_volume(self, volume: int) -> bool:
        """
        Set volume level.

        Args:
            volume: Volume level 0-100
        """
        if not 0 <= volume <= 100:
            logger.error(f"Invalid volume: {volume}")
            return False

        # Adjust volume using + and - commands
        delta = volume - self.volume
        command = "+" if delta > 0 else "-"

        for _ in range(abs(delta) // 5):  # Each command changes by ~5%
            if not await self.send_command(command):
                return False
            await asyncio.sleep(0.05)

        self.volume = volume
        return True

    async def stop(self) -> bool:
        """Stop streaming and close the connection."""
        if not self.process:
            return True

        self._set_state(RaopState.STOPPED)

        try:
            # Send quit command first
            if self.process.stdin:
                try:
                    self.process.stdin.write(b"q")
                    await self.process.stdin.drain()
                    self.process.stdin.close()
                except Exception:
                    pass

            # Wait briefly for graceful shutdown
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Force kill if needed
                self.process.kill()
                await self.process.wait()

            logger.info("RAOP streamer stopped")

        except Exception as e:
            logger.error(f"Error stopping RAOP streamer: {e}")
        finally:
            self.process = None
            if self._stderr_task:
                self._stderr_task.cancel()
                self._stderr_task = None

        return True

    def is_running(self) -> bool:
        """Check if the streamer is running."""
        return (
            self.process is not None and
            self.process.returncode is None and
            self.state in (RaopState.STREAMING, RaopState.PAUSED)
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class RaopStreamWriter:
    """
    Async context manager for streaming audio to AirPlay devices.

    Usage:
        async with RaopStreamWriter("192.168.1.74", volume=50) as writer:
            # Stream from file
            with open("audio.pcm", "rb") as f:
                while chunk := f.read(8192):
                    await writer.write(chunk)

            # Or stream from HTTP
            async with aiohttp.ClientSession() as session:
                async with session.get(stream_url) as response:
                    async for chunk in response.content.iter_chunked(8192):
                        await writer.write(chunk)
    """

    def __init__(
        self,
        host: str,
        port: int = 5000,
        volume: int = 50,
        binary_path: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.volume = volume
        self.streamer = RaopStreamer(binary_path)

    async def __aenter__(self):
        success = await self.streamer.start(
            self.host,
            port=self.port,
            volume=self.volume
        )
        if not success:
            raise RuntimeError(f"Failed to connect to {self.host}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.streamer.stop()

    async def write(self, data: bytes) -> bool:
        """Write PCM audio data."""
        return await self.streamer.write(data)

    async def pause(self):
        """Pause playback."""
        await self.streamer.pause()

    async def resume(self):
        """Resume playback."""
        await self.streamer.resume()

    async def set_volume(self, volume: int):
        """Set volume level."""
        await self.streamer.set_volume(volume)
