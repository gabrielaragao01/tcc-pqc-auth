from __future__ import annotations

import pytest

from src.auth.pqc_service import PQCLoginService
from src.crypto.kem.kyber import KyberKEM
from src.crypto.signatures.dilithium import DilithiumSignature
from src.db.repository import UserRepository


@pytest.fixture
def pqc_auth(memory_db) -> tuple[PQCLoginService, UserRepository]:
    """Function-scoped: fresh DB per test. ML-DSA-44 keygen happens each time.
    Acceptable for correctness tests; Phase 5 benchmarks use a separate setup.
    """
    repo = UserRepository()
    svc = PQCLoginService(
        signature=DilithiumSignature("ML-DSA-44"),
        kem=KyberKEM("Kyber512"),
        user_repo=repo,
    )
    return svc, repo


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_pqc_success(pqc_auth):
    svc, repo = pqc_auth
    repo.create_user("alice", "pass")
    result = svc.login("alice", "pass")
    assert result.access_token != ""
    assert result.algorithm == "ML-DSA-44"
    assert len(result.access_token.split(".")) == 3


def test_login_pqc_timing_is_positive(pqc_auth):
    svc, repo = pqc_auth
    repo.create_user("timed_user", "pass")
    result = svc.login("timed_user", "pass")
    assert result.timing.duration_ms > 0
    assert result.timing.operation == "pqc_sign"


def test_login_pqc_wrong_password_raises(pqc_auth):
    svc, repo = pqc_auth
    repo.create_user("frank", "correct")
    with pytest.raises(ValueError):
        svc.login("frank", "wrong")


def test_login_pqc_unknown_user_raises(pqc_auth):
    svc, _ = pqc_auth
    with pytest.raises(ValueError):
        svc.login("nobody", "pass")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def test_verify_pqc_token_valid(pqc_auth):
    svc, repo = pqc_auth
    repo.create_user("grace", "pass")
    token_resp = svc.login("grace", "pass")
    verify_resp = svc.verify_token(token_resp.access_token)
    assert verify_resp.valid is True
    assert verify_resp.claims is not None
    assert verify_resp.claims["sub"] == "grace"


def test_verify_pqc_token_invalid(pqc_auth):
    svc, _ = pqc_auth
    result = svc.verify_token("this.is.garbage")
    assert result.valid is False
    assert result.claims is None


def test_verify_pqc_timing_is_positive(pqc_auth):
    svc, repo = pqc_auth
    repo.create_user("henry", "pass")
    token_resp = svc.login("henry", "pass")
    verify_resp = svc.verify_token(token_resp.access_token)
    assert verify_resp.timing.duration_ms > 0
    assert verify_resp.timing.operation == "pqc_verify"


def test_verify_pqc_token_tampered(pqc_auth):
    """Payload adulterado após assinatura deve falhar na verificação."""
    svc, repo = pqc_auth
    repo.create_user("ivan", "pass")
    token_resp = svc.login("ivan", "pass")
    parts = token_resp.access_token.split(".")
    # Substitui o payload por outro (mesmo que válido em base64)
    import base64, json
    fake_payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "hacker", "iat": 0, "exp": 9999999999}, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    tampered = parts[0] + "." + fake_payload + "." + parts[2]
    result = svc.verify_token(tampered)
    assert result.valid is False


def test_verify_pqc_malformed_token(pqc_auth):
    """Token com número errado de partes deve retornar valid=False."""
    svc, _ = pqc_auth
    result = svc.verify_token("onlytwoparts.here")
    assert result.valid is False


# ---------------------------------------------------------------------------
# KEM Exchange
# ---------------------------------------------------------------------------

def test_kem_exchange_secrets_match(pqc_auth):
    svc, _ = pqc_auth
    result = svc.kem_exchange()
    assert result.secrets_match is True


def test_kem_exchange_timing_positive(pqc_auth):
    svc, _ = pqc_auth
    result = svc.kem_exchange()
    assert result.timing_keygen.duration_ms > 0
    assert result.timing_encapsulate.duration_ms > 0
    assert result.timing_decapsulate.duration_ms > 0
    assert result.timing_keygen.algorithm == "Kyber512"
    assert result.timing_encapsulate.algorithm == "Kyber512"
    assert result.timing_decapsulate.algorithm == "Kyber512"
