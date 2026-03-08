"""
Preflight Cryptography Layer — Ed25519 asymmetric signatures.

Production-grade cryptographic primitives for the execution firewall:
- Ed25519 asymmetric signing with non-repudiation
- SHA-256 state hashing with canonical JSON
- HMAC-SHA256 envelope integrity
- Key pair generation, rotation, and export
- Execution receipt creation and verification
- Public key distribution for independent verification

Ed25519 provides 128-bit security, deterministic signatures (no nonce
required), and ~60,000 sign/verify operations per second on commodity
hardware.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import base64
from datetime import datetime, timezone
from typing import Any, Optional

# Ed25519 via the `cryptography` library when available.
# Falls back to HMAC-SHA256 deterministic signatures with the same
# interface for zero-dependency operation.

_USE_CRYPTOGRAPHY = False
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    _USE_CRYPTOGRAPHY = True
except BaseException:
    pass


class KeyPair:
    """Ed25519 key pair for signing and verification.

    When the `cryptography` library is installed, uses real Ed25519.
    Falls back to HMAC-based deterministic signatures with the same
    interface for zero-dependency mode.
    """

    def __init__(
        self,
        private_key_bytes: Optional[bytes] = None,
        key_id: str = "",
    ):
        self.key_id = key_id or secrets.token_hex(8)
        self.created_at = datetime.now(timezone.utc)
        self._revoked = False

        if _USE_CRYPTOGRAPHY:
            if private_key_bytes:
                self._private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            else:
                self._private_key = Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            self._private_bytes = self._private_key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            self._public_bytes = self._public_key.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        else:
            # Fallback: HMAC-based deterministic signatures
            self._private_bytes = private_key_bytes or secrets.token_bytes(32)
            self._public_bytes = hashlib.sha256(self._private_bytes).digest()
            self._private_key = None
            self._public_key = None

    def sign(self, data: bytes) -> bytes:
        """Sign data and return the signature bytes."""
        if self._revoked:
            raise RuntimeError(f"Key {self.key_id} has been revoked")

        if _USE_CRYPTOGRAPHY and self._private_key:
            return self._private_key.sign(data)
        else:
            return hmac_mod.new(
                self._private_bytes, data, hashlib.sha256
            ).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify a signature against the original data."""
        if _USE_CRYPTOGRAPHY and self._public_key:
            try:
                self._public_key.verify(signature, data)
                return True
            except InvalidSignature:
                return False
        else:
            expected = hmac_mod.new(
                self._private_bytes, data, hashlib.sha256
            ).digest()
            return hmac_mod.compare_digest(expected, signature)

    def public_key_hex(self) -> str:
        return self._public_bytes.hex()

    def private_key_hex(self) -> str:
        return self._private_bytes.hex()

    def public_key_b64(self) -> str:
        return base64.b64encode(self._public_bytes).decode()

    def revoke(self) -> None:
        self._revoked = True

    @property
    def is_revoked(self) -> bool:
        return self._revoked

    def export_public(self) -> dict[str, Any]:
        """Export public key material for distribution."""
        return {
            "key_id": self.key_id,
            "algorithm": "Ed25519" if _USE_CRYPTOGRAPHY else "HMAC-SHA256",
            "public_key": self.public_key_hex(),
            "public_key_b64": self.public_key_b64(),
            "created_at": self.created_at.isoformat(),
            "revoked": self._revoked,
        }


class KeyRegistry:
    """Manages key pairs with rotation and revocation support."""

    def __init__(self):
        self._keys: dict[str, KeyPair] = {}
        self._active_key_id: Optional[str] = None

    def generate(self, key_id: str = "") -> KeyPair:
        kp = KeyPair(key_id=key_id)
        self._keys[kp.key_id] = kp
        if self._active_key_id is None:
            self._active_key_id = kp.key_id
        return kp

    def set_active(self, key_id: str) -> None:
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id} not found")
        if self._keys[key_id].is_revoked:
            raise ValueError(f"Key {key_id} is revoked")
        self._active_key_id = key_id

    @property
    def active_key(self) -> Optional[KeyPair]:
        if self._active_key_id and self._active_key_id in self._keys:
            return self._keys[self._active_key_id]
        return None

    def get_key(self, key_id: str) -> Optional[KeyPair]:
        return self._keys.get(key_id)

    def revoke(self, key_id: str) -> None:
        if key_id in self._keys:
            self._keys[key_id].revoke()
            if self._active_key_id == key_id:
                self._active_key_id = None

    def rotate(self) -> KeyPair:
        new_key = self.generate()
        self._active_key_id = new_key.key_id
        return new_key

    def export_public_keys(self) -> list[dict[str, Any]]:
        return [kp.export_public() for kp in self._keys.values()]

    def __len__(self) -> int:
        return len(self._keys)


class CryptoProvider:
    """Unified cryptographic operations for the Preflight execution firewall.

    Supports:
    - Ed25519 asymmetric signing (with `cryptography` package)
    - HMAC-SHA256 fallback signing (zero-dependency mode)
    - SHA-256 state hashing with canonical JSON
    - HMAC-SHA256 envelope integrity
    - Key pair management, rotation, and revocation
    - Execution receipt creation and verification
    """

    def __init__(
        self,
        signing_key: Optional[str] = None,
        hmac_key: Optional[str] = None,
    ):
        self._hmac_key = hmac_key or os.environ.get(
            "PREFLIGHT_HMAC_KEY", secrets.token_hex(32)
        )
        self._registry = KeyRegistry()
        self._signing_key = signing_key or secrets.token_hex(32)

        # Generate key pairs for agent, policy, and operator roles
        for role in ("agent", "policy", "operator"):
            if signing_key:
                derived = hashlib.sha256(
                    f"{signing_key}:{role}".encode()
                ).digest()
                kp = KeyPair(private_key_bytes=derived, key_id=role)
            else:
                kp = KeyPair(key_id=role)
            self._registry._keys[role] = kp
        self._registry._active_key_id = "agent"

    @property
    def registry(self) -> KeyRegistry:
        return self._registry

    @property
    def algorithm(self) -> str:
        return "Ed25519" if _USE_CRYPTOGRAPHY else "HMAC-SHA256"

    # -- Hashing -----------------------------------------------------------

    @staticmethod
    def hash_state(data: dict[str, Any]) -> str:
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # -- HMAC Integrity ----------------------------------------------------

    def compute_hmac(self, data: bytes) -> str:
        return hmac_mod.new(
            self._hmac_key.encode(), data, hashlib.sha256
        ).hexdigest()

    def verify_hmac(self, data: bytes, expected: str) -> bool:
        actual = self.compute_hmac(data)
        return hmac_mod.compare_digest(actual, expected)

    # -- Asymmetric Signing ------------------------------------------------

    def sign(self, data: bytes, key_id: str = "agent") -> str:
        """Sign data using Ed25519 (or HMAC fallback). Returns hex string."""
        kp = self._registry.get_key(key_id)
        if kp:
            return kp.sign(data).hex()

        derived_key = hashlib.sha256(
            f"{self._signing_key}:{key_id}".encode()
        ).digest()
        return hmac_mod.new(derived_key, data, hashlib.sha256).hexdigest()

    def verify_signature(
        self, data: bytes, signature: str, key_id: str = "agent"
    ) -> bool:
        kp = self._registry.get_key(key_id)
        if kp:
            try:
                sig_bytes = bytes.fromhex(signature)
                return kp.verify(data, sig_bytes)
            except (ValueError, Exception):
                return False

        expected = self.sign(data, key_id)
        return hmac_mod.compare_digest(expected, signature)

    def sign_dict(self, data: dict[str, Any], key_id: str = "agent") -> str:
        canonical = json.dumps(data, sort_keys=True, default=str).encode()
        return self.sign(canonical, key_id)

    def verify_dict_signature(
        self, data: dict[str, Any], signature: str, key_id: str = "agent"
    ) -> bool:
        canonical = json.dumps(data, sort_keys=True, default=str).encode()
        return self.verify_signature(canonical, signature, key_id)

    # -- Execution Receipt -------------------------------------------------

    def create_receipt(
        self,
        action_id: str,
        agent_id: str,
        pre_state_hash: str,
        post_state_hash: str,
        verdict: str,
        risk_score: float,
    ) -> dict[str, Any]:
        receipt_data = {
            "action_id": action_id,
            "agent_id": agent_id,
            "pre_state_hash": pre_state_hash,
            "post_state_hash": post_state_hash,
            "verdict": verdict,
            "risk_score": risk_score,
        }
        receipt_data["signatures"] = {
            "agent": self.sign_dict(receipt_data, "agent"),
            "policy": self.sign_dict(receipt_data, "policy"),
        }
        receipt_data["key_references"] = {}
        for role in ("agent", "policy"):
            kp = self._registry.get_key(role)
            if kp:
                receipt_data["key_references"][role] = {
                    "key_id": kp.key_id,
                    "algorithm": self.algorithm,
                    "public_key": kp.public_key_hex(),
                }
        receipt_data["integrity"] = self.compute_hmac(
            json.dumps(receipt_data, sort_keys=True, default=str).encode()
        )
        return receipt_data

    def verify_receipt(self, receipt: dict[str, Any]) -> bool:
        integrity = receipt.get("integrity", "")
        signatures = receipt.get("signatures", {})

        check_data = {k: v for k, v in receipt.items() if k != "integrity"}
        if not self.verify_hmac(
            json.dumps(check_data, sort_keys=True, default=str).encode(),
            integrity,
        ):
            return False

        core_data = {
            k: v for k, v in receipt.items()
            if k not in ("integrity", "signatures", "key_references")
        }
        for key_id, sig in signatures.items():
            if not self.verify_dict_signature(core_data, sig, key_id):
                return False

        return True

    def export_public_keys(self) -> list[dict[str, Any]]:
        return self._registry.export_public_keys()

    def rotate_key(self, role: str) -> dict[str, Any]:
        old_key = self._registry.get_key(role)
        if old_key:
            old_key.revoke()
        new_key = KeyPair(key_id=role)
        self._registry._keys[role] = new_key
        return new_key.export_public()
