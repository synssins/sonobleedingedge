"""
Patches for pyatv to work with AirConnect and other AirPlay 1 devices.

AirConnect (airupnp/aircast) returns RTSP responses without CSeq headers,
which causes pyatv's request/response matching to fail. This module patches
the RtspSession class to handle such responses.

Usage:
    from sonorium.pyatv_patches import apply_patches
    apply_patches()  # Call once at startup before using pyatv
"""

import logging
import asyncio
from typing import Optional, Dict, Tuple, Any, Union, Mapping

_LOGGER = logging.getLogger(__name__)
_patches_applied = False


def patch_rtsp_session():
    """Patch RtspSession to handle responses without CSeq headers.

    AirConnect and some AirPlay 1 devices return responses like:
        RTSP/1.0 501 Not Implemented

    Without a CSeq header. pyatv expects CSeq for request/response matching.
    This patch handles such responses by matching them to the only pending request.
    """
    try:
        from pyatv.support import rtsp
        from pyatv.support.http import HttpResponse
        import plistlib
    except ImportError:
        _LOGGER.warning("Could not import pyatv.support.rtsp - patches not applied")
        return False

    # Constants from pyatv
    USER_AGENT = "AirPlay/550.10"
    BPLIST_CONTENT_TYPE = "application/x-apple-binary-plist"

    def get_digest_payload(method, uri, username, realm, nonce, password):
        """Generate digest authentication payload."""
        import hashlib
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        return f'Digest username="{username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}"'

    original_exchange = rtsp.RtspSession.exchange

    async def patched_exchange(
        self,
        method: str,
        uri: Optional[str] = None,
        content_type: Optional[str] = None,
        headers: Optional[Dict[str, object]] = None,
        body: Any = None,
        allow_error: bool = False,
        protocol: str = "RTSP/1.0",
    ) -> HttpResponse:
        """Patched exchange that handles responses without CSeq headers."""
        cseq = self.cseq
        self.cseq += 1

        hdrs = {
            "CSeq": cseq,
            "DACP-ID": self.dacp_id,
            "Active-Remote": self.active_remote,
            "Client-Instance": self.dacp_id,
        }

        # Add the password authentication if required
        if self.digest_info:
            hdrs["Authorization"] = get_digest_payload(
                method, uri or self.uri, *self.digest_info
            )

        if headers:
            hdrs.update(headers)

        # If body is a dict, assume that payload should be sent as a binary plist
        if isinstance(body, dict):
            hdrs["Content-Type"] = BPLIST_CONTENT_TYPE
            body = plistlib.dumps(body, fmt=plistlib.FMT_BINARY)

        # Map an asyncio Event to current CSeq and make the request
        self.requests[cseq] = (asyncio.Event(), None)

        try:
            resp = await self.connection.send_and_receive(
                method,
                uri or self.uri,
                protocol=protocol,
                user_agent=USER_AGENT,
                content_type=content_type,
                headers=hdrs,
                body=body,
                allow_error=allow_error,
            )
        except Exception as ex:
            del self.requests[cseq]
            raise

        # Handle response - check for CSeq header
        resp_cseq = int(resp.headers.get("CSeq", "-1"))

        if resp_cseq in self.requests:
            # Normal case: CSeq matches a pending request
            event, _ = self.requests[resp_cseq]
            self.requests[resp_cseq] = (event, resp)
            event.set()
        elif len(self.requests) == 1:
            # Fallback: No CSeq in response, but only one pending request
            # This handles AirConnect's CSeq-less 501 responses
            _LOGGER.debug(
                "Response without CSeq header, matching to only pending request (CSeq %d)",
                cseq
            )
            event, _ = self.requests[cseq]
            self.requests[cseq] = (event, resp)
            event.set()
        else:
            # Multiple pending requests and no CSeq - can't match reliably
            # This shouldn't happen in normal use
            _LOGGER.warning(
                "Response without CSeq header and multiple pending requests - ignoring"
            )

        # Wait for response to the CSeq we expect (with timeout)
        try:
            await asyncio.wait_for(self.requests[cseq][0].wait(), timeout=5.0)
        except asyncio.TimeoutError:
            del self.requests[cseq]
            if allow_error:
                # For allow_error requests (like /info), return an error response
                _LOGGER.debug("Request %s timed out, returning error response", uri or self.uri)
                return HttpResponse(
                    protocol="RTSP",
                    version="1.0",
                    code=408,
                    message="Request Timeout",
                    headers={},
                    body=""
                )
            raise asyncio.TimeoutError(f"no response to CSeq {cseq} ({uri or self.uri})")

        response = self.requests[cseq][1]
        del self.requests[cseq]

        if response is None:
            raise RuntimeError(f"no response was saved for {cseq}")

        return response

    # Apply the patch
    rtsp.RtspSession.exchange = patched_exchange
    _LOGGER.info("Patched RtspSession.exchange for AirConnect compatibility")
    return True


def patch_empty_bplist():
    """Patch decode_bplist_from_body to handle empty responses.

    Some devices return empty bodies or invalid plist data. This patch
    handles those cases gracefully by returning an empty dict.
    """
    try:
        from pyatv.support import http
        from pyatv.support import rtsp
        import plistlib
    except ImportError:
        _LOGGER.warning("Could not import pyatv.support.http - patches not applied")
        return False

    def patched_decode_bplist_from_body(response) -> Dict[str, Any]:
        """Decode binary plist, returning empty dict on failure."""
        try:
            body = response.body
            if not body:
                return {}

            if isinstance(body, str):
                body = body.encode("utf-8")

            if not isinstance(body, bytes) or len(body) == 0:
                return {}

            return plistlib.loads(body)
        except Exception as e:
            _LOGGER.debug("Failed to decode bplist: %s", e)
            return {}

    # Patch in both modules (rtsp imports it separately)
    http.decode_bplist_from_body = patched_decode_bplist_from_body
    rtsp.decode_bplist_from_body = patched_decode_bplist_from_body
    _LOGGER.info("Patched decode_bplist_from_body for empty response handling")
    return True


def patch_hex_session_id():
    """Patch AirPlayV1 to handle hex session IDs.

    AirConnect returns Session headers as hex strings (e.g., "DEADBEEF")
    while pyatv expects decimal integers. This patch handles both formats.
    """
    try:
        from pyatv.protocols.raop.protocols import airplayv1
        from pyatv.protocols.airplay.auth import pair_verify
    except ImportError as e:
        _LOGGER.warning("Could not import pyatv airplayv1: %s - patch not applied", e)
        return False

    # parse_transport is defined in airplayv1 module itself
    parse_transport = airplayv1.parse_transport
    original_setup = airplayv1.AirPlayV1.setup

    async def patched_setup(self, timing_server_port: int, control_client_port: int) -> None:
        """Patched setup that handles hex session IDs."""
        # Step 1: Verify credentials (same as original)
        verifier = pair_verify(self.context.credentials, self.rtsp.connection)
        await verifier.verify_credentials()

        # Step 2: Send ANNOUNCE (same as original)
        await self.rtsp.announce(
            self.context.bytes_per_channel,
            self.context.channels,
            self.context.sample_rate,
            self.context.password,
        )

        # Step 3: Send SETUP (same as original)
        resp = await self.rtsp.setup(
            headers={
                "Transport": (
                    "RTP/AVP/UDP;unicast;interleaved=0-1;mode=record;"
                    f"control_port={control_client_port};"
                    f"timing_port={timing_server_port}"
                )
            }
        )

        # Step 4: Parse Transport header (same as original)
        _, options = parse_transport(resp.headers["Transport"])
        self.context.timing_port = int(options.get("timing_port", 0))
        self.context.control_port = int(options["control_port"])
        self.context.server_port = int(options["server_port"])

        # Step 5: Parse Session header - PATCHED to handle hex
        session_str = resp.headers.get("Session", "0")
        try:
            # Try decimal first
            self.context.rtsp_session = int(session_str)
        except ValueError:
            try:
                # Try hex (AirConnect uses DEADBEEF, etc.)
                self.context.rtsp_session = int(session_str, 16)
                _LOGGER.debug("Parsed hex session ID: %s -> %d", session_str, self.context.rtsp_session)
            except ValueError:
                # Last resort - use a random session ID
                import random
                self.context.rtsp_session = random.randrange(2**32)
                _LOGGER.warning("Could not parse session ID '%s', using random: %d",
                              session_str, self.context.rtsp_session)

        _LOGGER.debug(
            "Remote ports: control=%d, timing=%d, server=%d",
            self.context.control_port,
            self.context.timing_port,
            self.context.server_port,
        )

    airplayv1.AirPlayV1.setup = patched_setup
    _LOGGER.info("Patched AirPlayV1.setup for hex session ID handling")
    return True


def apply_patches():
    """Apply all pyatv patches for AirConnect compatibility.

    This should be called once at application startup, before any pyatv
    operations are performed.

    Returns:
        bool: True if all patches were applied successfully
    """
    global _patches_applied

    if _patches_applied:
        _LOGGER.debug("pyatv patches already applied")
        return True

    success = True

    if not patch_rtsp_session():
        success = False

    if not patch_empty_bplist():
        success = False

    if not patch_hex_session_id():
        success = False

    _patches_applied = True
    _LOGGER.info("pyatv patches applied for AirConnect compatibility")

    return success


def is_airconnect_device(properties: dict) -> bool:
    """Check if a device is an AirConnect bridge.

    Args:
        properties: RAOP service properties from mDNS discovery

    Returns:
        True if this is an AirConnect device (airupnp or aircast)
    """
    model = properties.get('am', '').lower()
    return model in ('airupnp', 'aircast')
