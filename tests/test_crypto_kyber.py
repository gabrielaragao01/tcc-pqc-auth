from __future__ import annotations

import pytest

from src.crypto.kem.kyber import KyberKEM


@pytest.fixture(scope="module")
def kem() -> KyberKEM:
    return KyberKEM()


@pytest.fixture(scope="module")
def keypair(kem: KyberKEM):
    return kem.generate_keypair()


def test_keygen_returns_nonempty_bytes(keypair):
    assert len(keypair.public_key) > 0
    assert len(keypair.private_key) > 0


def test_encapsulate_returns_ciphertext_and_secret(kem, keypair):
    result = kem.encapsulate(keypair.public_key)
    assert len(result.ciphertext) > 0
    assert len(result.shared_secret) > 0


def test_decapsulate_recovers_shared_secret(kem, keypair):
    result = kem.encapsulate(keypair.public_key)
    recovered = kem.decapsulate(result.ciphertext, keypair.private_key)
    assert recovered == result.shared_secret


def test_decapsulate_wrong_ciphertext_gives_different_secret(kem, keypair):
    result = kem.encapsulate(keypair.public_key)
    tampered = bytes(b ^ 0xFF for b in result.ciphertext[:10]) + result.ciphertext[10:]
    recovered = kem.decapsulate(tampered, keypair.private_key)
    assert recovered != result.shared_secret


def test_validate_passes(kem):
    assert kem.validate() is True
