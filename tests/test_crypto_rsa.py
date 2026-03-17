from __future__ import annotations

import pytest

from src.crypto.classical.rsa import RSASignature


@pytest.fixture(scope="module")
def rsa() -> RSASignature:
    return RSASignature(key_size=2048)


@pytest.fixture(scope="module")
def keypair(rsa: RSASignature):
    return rsa.generate_keypair()


def test_keygen_returns_nonempty_bytes(keypair):
    assert len(keypair.public_key) > 0
    assert len(keypair.private_key) > 0


def test_keygen_public_private_differ(keypair):
    assert keypair.public_key != keypair.private_key


def test_sign_returns_bytes(rsa, keypair):
    sig = rsa.sign(b"hello", keypair.private_key)
    assert isinstance(sig, bytes)
    assert len(sig) > 0


def test_verify_valid_signature(rsa, keypair):
    message = b"test message for RSA"
    sig = rsa.sign(message, keypair.private_key)
    assert rsa.verify(message, sig, keypair.public_key) is True


def test_verify_wrong_signature_returns_false(rsa, keypair):
    message = b"original message"
    other_message = b"different message"
    sig = rsa.sign(other_message, keypair.private_key)
    assert rsa.verify(message, sig, keypair.public_key) is False


def test_verify_corrupted_bytes_returns_false(rsa, keypair):
    message = b"test"
    sig = rsa.sign(message, keypair.private_key)
    corrupted = sig[:-4] + b"\x00\x00\x00\x00"
    assert rsa.verify(message, corrupted, keypair.public_key) is False


def test_validate_passes(rsa):
    assert rsa.validate() is True
