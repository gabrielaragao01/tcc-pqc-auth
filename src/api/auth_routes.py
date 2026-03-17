from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException

from src.auth.classical_service import ClassicalAuthService
from src.auth.models import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    VerifyRequest,
    VerifyResponse,
)
from src.config import settings
from src.crypto.classical.rsa import RSASignature
from src.db.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])

# Module-level lazy singleton — RSA key generation happens once on the first
# request, not at import time. The keys persist for the process lifetime.
_classical_service: ClassicalAuthService | None = None


def _get_service() -> ClassicalAuthService:
    global _classical_service
    if _classical_service is None:
        _classical_service = ClassicalAuthService(
            signature=RSASignature(key_size=settings.rsa_key_size),
            user_repo=UserRepository(),
        )
    return _classical_service


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest) -> RegisterResponse:
    """Create a test user in the SQLite database."""
    try:
        user = UserRepository().create_user(body.username, body.password)
        return RegisterResponse(username=user.username)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists.")


@router.post("/login-classical", response_model=TokenResponse)
def login_classical(body: LoginRequest) -> TokenResponse:
    """Authenticate with username/password and return an RS256-signed JWT.

    The response includes `timing.duration_ms` — the wall-clock time for the
    JWT signing operation, used for Phase 5 benchmarking.
    """
    try:
        return _get_service().login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/verify-classical", response_model=VerifyResponse)
def verify_classical(body: VerifyRequest) -> VerifyResponse:
    """Verify an RS256 JWT and return decoded claims.

    Always returns HTTP 200. Check the `valid` field in the response body.
    The response includes `timing.duration_ms` for the verify operation.
    """
    return _get_service().verify_token(body.token)
