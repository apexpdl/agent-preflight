"""Tests for TrustKernel cryptography layer."""

import pytest
from trust_kernel.crypto import CryptoProvider


class TestCryptoProvider:
    def setup_method(self):
        self.crypto = CryptoProvider(
            signing_key="test-signing-key",
            hmac_key="test-hmac-key",
        )

    def test_hash_state_deterministic(self):
        data = {"key": "value", "num": 42}
        h1 = CryptoProvider.hash_state(data)
        h2 = CryptoProvider.hash_state(data)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_state_different_inputs(self):
        h1 = CryptoProvider.hash_state({"a": 1})
        h2 = CryptoProvider.hash_state({"a": 2})
        assert h1 != h2

    def test_hash_bytes(self):
        h = CryptoProvider.hash_bytes(b"hello world")
        assert len(h) == 64

    def test_hmac_compute_and_verify(self):
        data = b"test data"
        mac = self.crypto.compute_hmac(data)
        assert self.crypto.verify_hmac(data, mac)

    def test_hmac_tamper_detection(self):
        data = b"test data"
        mac = self.crypto.compute_hmac(data)
        assert not self.crypto.verify_hmac(b"tampered data", mac)

    def test_sign_and_verify(self):
        data = b"action payload"
        sig = self.crypto.sign(data, "agent")
        assert self.crypto.verify_signature(data, sig, "agent")

    def test_sign_different_keys(self):
        data = b"action payload"
        sig_agent = self.crypto.sign(data, "agent")
        sig_policy = self.crypto.sign(data, "policy")
        assert sig_agent != sig_policy

    def test_sign_dict(self):
        data = {"action": "delete", "target": "users"}
        sig = self.crypto.sign_dict(data, "agent")
        assert self.crypto.verify_dict_signature(data, sig, "agent")

    def test_sign_dict_order_independent(self):
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        sig1 = self.crypto.sign_dict(data1, "agent")
        sig2 = self.crypto.sign_dict(data2, "agent")
        assert sig1 == sig2

    def test_create_and_verify_receipt(self):
        receipt = self.crypto.create_receipt(
            action_id="act-1",
            agent_id="agent-1",
            pre_state_hash="abc123",
            post_state_hash="def456",
            verdict="allow",
            risk_score=0.15,
        )
        assert "signatures" in receipt
        assert "integrity" in receipt
        assert self.crypto.verify_receipt(receipt)

    def test_receipt_tamper_detection(self):
        receipt = self.crypto.create_receipt(
            action_id="act-1",
            agent_id="agent-1",
            pre_state_hash="abc123",
            post_state_hash="def456",
            verdict="allow",
            risk_score=0.15,
        )
        receipt["risk_score"] = 0.99  # Tamper
        assert not self.crypto.verify_receipt(receipt)
