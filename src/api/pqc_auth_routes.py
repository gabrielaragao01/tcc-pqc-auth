from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.auth.models import (
    KEMExchangeResponse,
    LoginRequest,
    TokenResponse,
    VerifyRequest,
    VerifyResponse,
)
from src.auth.pqc_service import PQCLoginService
from src.config import settings
from src.crypto.kem.kyber import KyberKEM
from src.crypto.signatures.dilithium import DilithiumSignature
from src.db.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth-pqc"])

# Module-level lazy singleton — ML-DSA-44 keypair is generated once on the
# first request, not at import time. The key persists for the process lifetime.
_pqc_service: PQCLoginService | None = None


def _get_service() -> PQCLoginService:
    global _pqc_service
    if _pqc_service is None:
        _pqc_service = PQCLoginService(
            signature=DilithiumSignature(settings.sig_algorithm),
            kem=KyberKEM(settings.pqc_algorithm),
            user_repo=UserRepository(),
        )
    return _pqc_service


@router.post("/login-pqc", response_model=TokenResponse)
def login_pqc(body: LoginRequest) -> TokenResponse:
    """Authenticate with username/password and return a ML-DSA-44-signed PQC token.

    The response includes `timing.duration_ms` — the wall-clock time for the
    signing operation, used for Phase 5 benchmarking comparison with RS256.
    """
    try:
        return _get_service().login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/verify-pqc", response_model=VerifyResponse)
def verify_pqc(body: VerifyRequest) -> VerifyResponse:
    """Verify a PQC token signature and expiry, returning claims and timing.

    Always returns HTTP 200. Check the `valid` field in the response body.
    The response includes `timing.duration_ms` for the verify operation.
    """
    return _get_service().verify_token(body.token)


@router.post("/kem-exchange", response_model=KEMExchangeResponse)
def kem_exchange() -> KEMExchangeResponse:
    """Execute a full Kyber512 KEM round-trip (keygen → encapsulate → decapsulate).

    Returns individual timings for each KEM operation and confirms that the
    shared secrets produced by encapsulate and decapsulate are identical.
    Intended for Phase 5 benchmarking — not part of the login flow.
    """
    return _get_service().kem_exchange()
