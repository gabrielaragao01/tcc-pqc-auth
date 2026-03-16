from __future__ import annotations

from fastapi import APIRouter, HTTPException # pyright: ignore[reportMissingImports]

from src.auth.service import PQCAuthService
from src.config import settings
from src.crypto.kem.kyber import KyberKEM
from src.crypto.models import PQCSmokeTestReport
from src.crypto.signatures.dilithium import DilithiumSignature

router = APIRouter(prefix="/pqc", tags=["pqc"])


def _build_service() -> PQCAuthService:
    """Wire concrete implementations into PQCAuthService using algorithm names from settings."""
    return PQCAuthService(
        kem=KyberKEM(algorithm=settings.pqc_algorithm),
        signature=DilithiumSignature(algorithm=settings.sig_algorithm),
    )


@router.get(
    "/health",
    response_model=PQCSmokeTestReport,
    summary="Run PQC smoke tests",
    description=(
        "Executes a full KEM round-trip and a full signature round-trip using the "
        "algorithms configured in .env (PQC_ALGORITHM and SIG_ALGORITHM). "
        "Returns a structured report of results. "
        "Returns HTTP 200 when all tests pass, HTTP 503 when any test fails."
    ),
)
def pqc_health_check() -> PQCSmokeTestReport:
    """Returns 200 if all smoke tests pass, 503 with report body if any fail."""
    service = _build_service()
    report = service.run_smoke_tests()

    if not report.all_passed:
        raise HTTPException(status_code=503, detail=report.model_dump())

    return report
