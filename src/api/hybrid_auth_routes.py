from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.auth.hybrid_service import HybridAuthService
from src.auth.models import (
    HybridTokenResponse,
    HybridVerifyRequest,
    HybridVerifyResponse,
    LoginRequest,
)
from src.config import settings
from src.crypto.classical.rsa import RSASignature
from src.crypto.kem.kyber import KyberKEM
from src.crypto.signatures.dilithium import DilithiumSignature
from src.db.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth-hybrid"])

# Module-level lazy singleton — both keypairs (RSA + ML-DSA-44) are generated
# once on the first request, not at import time.
_hybrid_service: HybridAuthService | None = None


def _get_service() -> HybridAuthService:
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridAuthService(
            classical_signature=RSASignature(settings.rsa_key_size),
            pqc_signature=DilithiumSignature(settings.sig_algorithm),
            kem=KyberKEM(settings.pqc_algorithm),
            user_repo=UserRepository(),
        )
    return _hybrid_service


@router.post("/login-hybrid", response_model=HybridTokenResponse)
def login_hybrid(body: LoginRequest) -> HybridTokenResponse:
    """Authenticate and return both RS256 JWT and ML-DSA-44 PQC tokens.

    The response includes separate timing metrics for each signing operation,
    enabling direct performance comparison between classical and PQC.
    """
    try:
        return _get_service().login(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/verify-hybrid", response_model=HybridVerifyResponse)
def verify_hybrid(body: HybridVerifyRequest) -> HybridVerifyResponse:
    """Verify both RS256 and ML-DSA-44 tokens, returning comparative timings.

    Always returns HTTP 200. Check `classical_valid` and `pqc_valid` fields.
    """
    return _get_service().verify_tokens(body.classical_token, body.pqc_token)
