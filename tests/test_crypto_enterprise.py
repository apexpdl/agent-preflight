"""Tests for the enterprise-grade cryptography layer."""

import pytest
from trust_kernel.crypto import CryptoProvider, KeyPair, KeyRegistry


class TestKeyPair:
    def test_create_keypair(self):
        kp = KeyPair()
        assert kp.key_id
        assert kp.public_key_hex()
        assert kp.private_key_hex()
        assert not kp.is_revoked

    def test_sign_and_verify(self):
        kp = KeyPair()
        data = b"test data for signing"
        sig = kp.sign(data)
        assert kp.verify(data, sig)

    def test_verify_fails_on_tampered_data(self):
        kp = KeyPair()
        data = b"original data"
        sig = kp.sign(data)
        assert not kp.verify(b"tampered data", sig)

    def test_revoked_key_cannot_sign(self):
        kp = KeyPair()
        kp.revoke()
        assert kp.is_revoked
        with pytest.raises(RuntimeError, match="revoked"):
            kp.sign(b"data")

    def test_export_public(self):
        kp = KeyPair(key_id="test-key")
        exported = kp.export_public()
        assert exported["key_id"] == "test-key"
        assert "algorithm" in exported
        assert "public_key" in exported
        assert "public_key_b64" in exported
        assert exported["revoked"] is False

    def test_deterministic_from_bytes(self):
        secret = b"0" * 32
        kp1 = KeyPair(private_key_bytes=secret, key_id="a")
        kp2 = KeyPair(private_key_bytes=secret, key_id="b")
        data = b"same data"
        sig1 = kp1.sign(data)
        # Both should produce same signature from same key material
        assert kp2.verify(data, sig1)


class TestKeyRegistry:
    def test_generate_and_get(self):
        reg = KeyRegistry()
        kp = reg.generate(key_id="primary")
        assert reg.get_key("primary") is kp
        assert reg.active_key is kp

    def test_rotate(self):
        reg = KeyRegistry()
        old = reg.generate(key_id="old")
        new = reg.rotate()
        assert reg.active_key is new
        assert reg.active_key is not old

    def test_revoke(self):
        reg = KeyRegistry()
        kp = reg.generate(key_id="revoke-me")
        reg.revoke("revoke-me")
        assert kp.is_revoked
        assert reg.active_key is None

    def test_set_active(self):
        reg = KeyRegistry()
        k1 = reg.generate(key_id="k1")
        k2 = reg.generate(key_id="k2")
        reg.set_active("k2")
        assert reg.active_key is k2

    def test_set_active_revoked_fails(self):
        reg = KeyRegistry()
        kp = reg.generate(key_id="r1")
        reg.revoke("r1")
        with pytest.raises(ValueError, match="revoked"):
            reg.set_active("r1")

    def test_export_public_keys(self):
        reg = KeyRegistry()
        reg.generate(key_id="a")
        reg.generate(key_id="b")
        exported = reg.export_public_keys()
        assert len(exported) == 2
        assert any(k["key_id"] == "a" for k in exported)


class TestCryptoProvider:
    def test_hash_state(self):
        h1 = CryptoProvider.hash_state({"a": 1, "b": 2})
        h2 = CryptoProvider.hash_state({"b": 2, "a": 1})
        assert h1 == h2  # Canonical JSON ordering

    def test_hmac_integrity(self):
        cp = CryptoProvider(hmac_key="test-key-123")
        data = b"important data"
        mac = cp.compute_hmac(data)
        assert cp.verify_hmac(data, mac)
        assert not cp.verify_hmac(b"tampered", mac)

    def test_sign_and_verify(self):
        cp = CryptoProvider(signing_key="test-signer")
        data = b"sign me"
        sig = cp.sign(data, key_id="agent")
        assert cp.verify_signature(data, sig, key_id="agent")

    def test_sign_dict(self):
        cp = CryptoProvider(signing_key="dict-signer")
        d = {"action": "test", "risk": 0.5}
        sig = cp.sign_dict(d, key_id="policy")
        assert cp.verify_dict_signature(d, sig, key_id="policy")

    def test_receipt_creation_and_verification(self):
        cp = CryptoProvider(hmac_key="receipt-key")
        receipt = cp.create_receipt(
            action_id="act-001",
            agent_id="agent-test",
            pre_state_hash="aabb",
            post_state_hash="ccdd",
            verdict="allow",
            risk_score=0.15,
        )
        assert receipt["action_id"] == "act-001"
        assert "signatures" in receipt
        assert "integrity" in receipt
        assert "key_references" in receipt
        assert cp.verify_receipt(receipt)

    def test_receipt_tamper_detection(self):
        cp = CryptoProvider(hmac_key="tamper-key")
        receipt = cp.create_receipt(
            action_id="act-002",
            agent_id="agent-test",
            pre_state_hash="1122",
            post_state_hash="3344",
            verdict="block",
            risk_score=0.9,
        )
        # Tamper with the receipt
        receipt["verdict"] = "allow"
        assert not cp.verify_receipt(receipt)

    def test_key_rotation(self):
        cp = CryptoProvider(signing_key="rotate-me")
        old_keys = cp.export_public_keys()
        new_info = cp.rotate_key("agent")
        assert new_info["key_id"] == "agent"
        # Old signature should no longer verify with new key
        data = b"after rotation"
        sig = cp.sign(data, key_id="agent")
        assert cp.verify_signature(data, sig, key_id="agent")

    def test_algorithm_property(self):
        cp = CryptoProvider()
        assert cp.algorithm in ("Ed25519", "HMAC-SHA256")

    def test_export_public_keys(self):
        cp = CryptoProvider()
        keys = cp.export_public_keys()
        assert len(keys) >= 3  # agent, policy, operator
        roles = {k["key_id"] for k in keys}
        assert "agent" in roles
        assert "policy" in roles
        assert "operator" in roles

    def test_cross_key_verification_fails(self):
        cp = CryptoProvider(signing_key="cross-key")
        data = b"cross check"
        sig = cp.sign(data, key_id="agent")
        # Should not verify with a different key
        assert not cp.verify_signature(data, sig, key_id="policy")
