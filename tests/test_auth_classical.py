from __future__ import annotations

import pytest

from src.auth.classical_service import ClassicalAuthService
from src.crypto.classical.rsa import RSASignature
from src.db.repository import UserRepository


@pytest.fixture
def auth(memory_db) -> tuple[ClassicalAuthService, UserRepository]:
    """Function-scoped: fresh DB per test, but RSA keygen happens each time.
    Acceptable for correctness tests; Phase 5 benchmarks use a different setup.
    """
    repo = UserRepository()
    svc = ClassicalAuthService(signature=RSASignature(key_size=2048), user_repo=repo)
    return svc, repo


def test_login_success(auth):
    svc, repo = auth
    repo.create_user("alice", "pass")
    result = svc.login("alice", "pass")
    assert result.access_token != ""
    assert result.algorithm == "RS256"


def test_login_timing_is_positive(auth):
    svc, repo = auth
    repo.create_user("timed_user", "pass")
    result = svc.login("timed_user", "pass")
    assert result.timing.duration_ms > 0
    assert result.timing.operation == "jwt_sign"


def test_login_wrong_password_raises(auth):
    svc, repo = auth
    repo.create_user("frank", "correct")
    with pytest.raises(ValueError):
        svc.login("frank", "wrong")


def test_login_unknown_user_raises(auth):
    svc, repo = auth
    with pytest.raises(ValueError):
        svc.login("nobody", "pass")


def test_verify_token_valid(auth):
    svc, repo = auth
    repo.create_user("grace", "pass")
    token_resp = svc.login("grace", "pass")
    verify_resp = svc.verify_token(token_resp.access_token)
    assert verify_resp.valid is True
    assert verify_resp.claims is not None
    assert verify_resp.claims["sub"] == "grace"


def test_verify_token_invalid(auth):
    svc, _ = auth
    result = svc.verify_token("this.is.garbage")
    assert result.valid is False
    assert result.claims is None


def test_verify_timing_is_positive(auth):
    svc, repo = auth
    repo.create_user("henry", "pass")
    token_resp = svc.login("henry", "pass")
    verify_resp = svc.verify_token(token_resp.access_token)
    assert verify_resp.timing.duration_ms > 0
    assert verify_resp.timing.operation == "jwt_verify"
