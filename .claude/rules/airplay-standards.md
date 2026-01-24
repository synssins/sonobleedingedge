# AirPlay Implementation Standards - MANDATORY

These rules are NON-NEGOTIABLE and apply to ALL Sonorium development.

## Protocol Compliance

1. **AirPlay Standards Only** - Implement AirPlay 1 (RAOP) and AirPlay 2 protocols according to published specifications. Do not invent proprietary extensions or shortcuts.

2. **No Protocol Fallbacks** - When diagnosing or implementing AirPlay functionality:
   - Do NOT fall back to DLNA, Chromecast, or other protocols as "alternatives"
   - Do NOT suggest switching protocols when AirPlay has issues
   - STAY on AirPlay and solve the actual problem

3. **No Device-Specific Hacks** - Do not write code that:
   - Targets specific device brands (Arylic, Sonos, etc.) with special cases
   - Uses undocumented device quirks as solutions
   - Breaks when used with other AirPlay-compatible devices

## Platform Agnostic Core

4. **100% Portable Code** - The core Sonorium codebase MUST:
   - Run identically on Windows, Linux, macOS, and in containers
   - Use only cross-platform Python libraries
   - Never use OS-specific APIs in core modules
   - Never assume file paths, line endings, or shell availability

5. **Dependency Rules**:
   - All dependencies must be pip-installable
   - No compiled extensions that aren't available cross-platform
   - No subprocess calls to OS-specific tools in core code

6. **Path Handling**:
   - Use `pathlib.Path` exclusively, never string concatenation
   - Never hardcode path separators
   - Never assume case sensitivity or insensitivity

## Diagnostic Approach

7. **When AirPlay Issues Occur**:
   - First: Verify mDNS/Bonjour discovery is working
   - Second: Check RAOP handshake sequence
   - Third: Validate audio codec/format compatibility
   - Fourth: Inspect timing/sync packets
   - NEVER: "Just use DLNA instead"

8. **Device Testing**:
   - Test against multiple AirPlay receivers
   - Verify behavior matches Apple's implementation
   - Document any device-specific observations WITHOUT coding around them

## Code Review Checklist

Before any AirPlay-related code is committed:
- [ ] Works with generic AirPlay receiver (not just test devices)
- [ ] No platform-specific imports in core modules
- [ ] No hardcoded paths or OS assumptions
- [ ] No protocol fallback logic
- [ ] No device brand checks or special cases
