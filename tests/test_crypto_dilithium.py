from __future__ import annotations

import pytest

from src.crypto.signatures.dilithium import DilithiumSignature


@pytest.fixture(scope="module")
def dilithium() -> DilithiumSignature:
    return DilithiumSignature()


@pytest.fixture(scope="module")
def keypair(dilithium: DilithiumSignature):
    return dilithium.generate_keypair()


def test_keygen_returns_nonempty_bytes(keypair):
    assert len(keypair.public_key) > 0
    assert len(keypair.private_key) > 0


def test_sign_returns_bytes(dilithium, keypair):
    sig = dilithium.sign(b"hello", keypair.private_key)
    assert isinstance(sig, bytes)
    assert len(sig) > 0


def test_verify_valid_signature(dilithium, keypair):
    message = b"test message for ML-DSA-44"
    sig = dilithium.sign(message, keypair.private_key)
    assert dilithium.verify(message, sig, keypair.public_key) is True


def test_verify_tampered_message_returns_false(dilithium, keypair):
    message = b"original"
    sig = dilithium.sign(message, keypair.private_key)
    assert dilithium.verify(b"tampered", sig, keypair.public_key) is False


def test_verify_wrong_key_returns_false(dilithium):
    kp1 = dilithium.generate_keypair()
    kp2 = dilithium.generate_keypair()
    sig = dilithium.sign(b"message", kp1.private_key)
    assert dilithium.verify(b"message", sig, kp2.public_key) is False


def test_validate_passes(dilithium):
    assert dilithium.validate() is True
