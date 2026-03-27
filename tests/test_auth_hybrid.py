from __future__ import annotations

import pytest

from src.auth.hybrid_service import HybridAuthService
from src.crypto.classical.rsa import RSASignature
from src.crypto.kem.kyber import KyberKEM
from src.crypto.signatures.dilithium import DilithiumSignature
from src.db.repository import UserRepository


@pytest.fixture
def hybrid_auth(memory_db) -> tuple[HybridAuthService, UserRepository]:
    """Function-scoped: fresh DB per test. Both keypairs generated each time."""
    repo = UserRepository()
    svc = HybridAuthService(
        classical_signature=RSASignature(2048),
        pqc_signature=DilithiumSignature("ML-DSA-44"),
        kem=KyberKEM("Kyber512"),
        user_repo=repo,
    )
    return svc, repo


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_hybrid_returns_both_tokens(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("alice", "pass")
    result = svc.login("alice", "pass")
    assert result.classical_token != ""
    assert result.pqc_token != ""
    assert result.token_type == "bearer"


def test_login_hybrid_classical_is_rs256(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("bob", "pass")
    result = svc.login("bob", "pass")
    assert result.timing_classical.algorithm == "RS256"
    assert result.timing_classical.operation == "jwt_sign"


def test_login_hybrid_pqc_is_mldsa44(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("carol", "pass")
    result = svc.login("carol", "pass")
    assert result.timing_pqc.algorithm == "ML-DSA-44"
    assert result.timing_pqc.operation == "pqc_sign"


def test_login_hybrid_timings_are_positive(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("dave", "pass")
    result = svc.login("dave", "pass")
    assert result.timing_classical.duration_ms > 0
    assert result.timing_pqc.duration_ms > 0


def test_login_hybrid_wrong_password_raises(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("eve", "correct")
    with pytest.raises(ValueError):
        svc.login("eve", "wrong")


def test_login_hybrid_unknown_user_raises(hybrid_auth):
    svc, _ = hybrid_auth
    with pytest.raises(ValueError):
        svc.login("nobody", "pass")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def test_verify_hybrid_both_valid(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("frank", "pass")
    tokens = svc.login("frank", "pass")
    result = svc.verify_tokens(tokens.classical_token, tokens.pqc_token)
    assert result.classical_valid is True
    assert result.pqc_valid is True
    assert result.claims is not None
    assert result.claims["sub"] == "frank"


def test_verify_hybrid_classical_invalid(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("grace", "pass")
    tokens = svc.login("grace", "pass")
    result = svc.verify_tokens("garbage.token.here", tokens.pqc_token)
    assert result.classical_valid is False
    assert result.pqc_valid is True
    assert result.claims is not None
    assert result.claims["sub"] == "grace"


def test_verify_hybrid_pqc_invalid(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("henry", "pass")
    tokens = svc.login("henry", "pass")
    result = svc.verify_tokens(tokens.classical_token, "bad.pqc.token")
    assert result.classical_valid is True
    assert result.pqc_valid is False
    assert result.claims is not None
    assert result.claims["sub"] == "henry"


def test_verify_hybrid_both_invalid(hybrid_auth):
    svc, _ = hybrid_auth
    result = svc.verify_tokens("bad.jwt.token", "bad.pqc.token")
    assert result.classical_valid is False
    assert result.pqc_valid is False
    assert result.claims is None


def test_verify_hybrid_timings_are_positive(hybrid_auth):
    svc, repo = hybrid_auth
    repo.create_user("ivan", "pass")
    tokens = svc.login("ivan", "pass")
    result = svc.verify_tokens(tokens.classical_token, tokens.pqc_token)
    assert result.timing_classical.duration_ms > 0
    assert result.timing_classical.operation == "jwt_verify"
    assert result.timing_classical.algorithm == "RS256"
    assert result.timing_pqc.duration_ms > 0
    assert result.timing_pqc.operation == "pqc_verify"
    assert result.timing_pqc.algorithm == "ML-DSA-44"
