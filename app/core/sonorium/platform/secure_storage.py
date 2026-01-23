"""
Secure Storage for Sensitive Settings

Provides encrypted storage for tokens, passwords, and other sensitive values.
Uses platform-appropriate encryption methods.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from sonorium.obs import logger


class SecureStorage:
    """
    Encrypted storage for sensitive configuration values.

    Uses Fernet symmetric encryption with a machine-derived key.
    Falls back to base64 obfuscation if cryptography is not available.
    """

    def __init__(self, storage_path: Path):
        """
        Initialize secure storage.

        Args:
            storage_path: Path to the encrypted storage file
        """
        self.storage_path = storage_path
        self._key: bytes | None = None
        self._fernet: Any = None
        self._data: dict[str, str] = {}

        self._initialize_encryption()
        self._load()

    def _get_machine_id(self) -> str:
        """
        Get a machine-specific identifier for key derivation.

        Uses various system identifiers to create a stable machine ID.
        """
        identifiers = []

        # Try various machine identifiers
        try:
            # Windows
            import subprocess
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'UUID'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    identifiers.append(lines[1].strip())
        except Exception:
            pass

        try:
            # Linux - machine-id
            machine_id_path = Path('/etc/machine-id')
            if machine_id_path.exists():
                identifiers.append(machine_id_path.read_text().strip())
        except Exception:
            pass

        try:
            # Docker/HA - use hostname as identifier
            identifiers.append(os.environ.get('HOSTNAME', ''))
        except Exception:
            pass

        # Fallback to username + home directory
        identifiers.append(os.environ.get('USERNAME', os.environ.get('USER', '')))
        identifiers.append(str(Path.home()))

        # Combine all identifiers
        combined = '|'.join(filter(None, identifiers))
        return combined or 'sonorium-default-key'

    def _derive_key(self) -> bytes:
        """Derive encryption key from machine ID."""
        machine_id = self._get_machine_id()

        # Use PBKDF2 to derive a key
        salt = b'sonorium-secure-storage-v1'
        key = hashlib.pbkdf2_hmac(
            'sha256',
            machine_id.encode(),
            salt,
            100000,  # iterations
            dklen=32
        )
        return base64.urlsafe_b64encode(key)

    def _initialize_encryption(self) -> None:
        """Initialize encryption using Fernet if available."""
        self._key = self._derive_key()

        try:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(self._key)
            logger.debug("Secure storage using Fernet encryption")
        except ImportError:
            self._fernet = None
            logger.warning(
                "cryptography library not available - "
                "using base64 obfuscation (less secure)"
            )

    def _encrypt(self, value: str) -> str:
        """Encrypt a string value."""
        if self._fernet:
            encrypted = self._fernet.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        else:
            # Fallback: XOR with key + base64 (obfuscation, not true encryption)
            key_bytes = self._key[:len(value.encode())]
            value_bytes = value.encode()
            xored = bytes(v ^ key_bytes[i % len(key_bytes)]
                         for i, v in enumerate(value_bytes))
            return base64.urlsafe_b64encode(xored).decode()

    def _decrypt(self, encrypted: str) -> str | None:
        """Decrypt a string value."""
        try:
            if self._fernet:
                decoded = base64.urlsafe_b64decode(encrypted.encode())
                return self._fernet.decrypt(decoded).decode()
            else:
                # Fallback: reverse XOR
                decoded = base64.urlsafe_b64decode(encrypted.encode())
                key_bytes = self._key[:len(decoded)]
                xored = bytes(v ^ key_bytes[i % len(key_bytes)]
                             for i, v in enumerate(decoded))
                return xored.decode()
        except Exception as e:
            logger.warning(f"Failed to decrypt value: {e}")
            return None

    def _load(self) -> None:
        """Load encrypted data from file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load secure storage: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save encrypted data to file."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save secure storage: {e}")

    def set(self, key: str, value: str) -> None:
        """
        Store an encrypted value.

        Args:
            key: Setting key (e.g., 'ha_token', 'mqtt_password')
            value: Plain text value to encrypt and store
        """
        if value:
            self._data[key] = self._encrypt(value)
        elif key in self._data:
            del self._data[key]
        self._save()

    def get(self, key: str) -> str | None:
        """
        Retrieve and decrypt a value.

        Args:
            key: Setting key

        Returns:
            Decrypted value or None if not found
        """
        encrypted = self._data.get(key)
        if encrypted:
            return self._decrypt(encrypted)
        return None

    def delete(self, key: str) -> None:
        """Remove a stored value."""
        if key in self._data:
            del self._data[key]
            self._save()

    def clear(self) -> None:
        """Remove all stored values."""
        self._data = {}
        self._save()

    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._data

    def keys(self) -> list[str]:
        """Get all stored keys."""
        return list(self._data.keys())


# Global instance
_secure_storage: SecureStorage | None = None


def get_secure_storage(data_dir: Path | None = None) -> SecureStorage:
    """
    Get the global secure storage instance.

    Args:
        data_dir: Data directory (only needed on first call)

    Returns:
        SecureStorage instance
    """
    global _secure_storage

    if _secure_storage is None:
        if data_dir is None:
            # Try to get from runtime context
            try:
                from sonorium.platform import runtime
                data_dir = runtime.paths.data
            except Exception:
                # Fallback
                data_dir = Path.home() / '.sonorium'

        storage_path = data_dir / 'settings.secure.json'
        _secure_storage = SecureStorage(storage_path)

    return _secure_storage


def initialize_secure_storage(data_dir: Path) -> SecureStorage:
    """
    Initialize secure storage with a specific data directory.

    Call this during app startup.
    """
    global _secure_storage
    storage_path = data_dir / 'settings.secure.json'
    _secure_storage = SecureStorage(storage_path)
    return _secure_storage


__all__ = [
    'SecureStorage',
    'get_secure_storage',
    'initialize_secure_storage',
]
