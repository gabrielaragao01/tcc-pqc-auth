from __future__ import annotations

from src.auth.classical_service import ClassicalAuthService
from src.auth.models import HybridTokenResponse, HybridVerifyResponse
from src.auth.pqc_service import PQCLoginService
from src.crypto.interfaces import IDigitalSignature, IKeyEncapsulation
from src.db.repository import UserRepository


class HybridAuthService:
    """Orchestrates hybrid authentication: classical RS256 + PQC ML-DSA-44.

    Composes the existing ClassicalAuthService and PQCLoginService, producing
    dual tokens from a single login request. Each token is signed independently
    with its own timing measurement, enabling direct performance comparison.
    """

    def __init__(
        self,
        classical_signature: IDigitalSignature,
        pqc_signature: IDigitalSignature,
        kem: IKeyEncapsulation,
        user_repo: UserRepository,
    ) -> None:
        self._classical = ClassicalAuthService(classical_signature, user_repo)
        self._pqc = PQCLoginService(pqc_signature, kem, user_repo)

    def login(self, username: str, password: str) -> HybridTokenResponse:
        """Authenticate user and return both RS256 and ML-DSA-44 tokens.

        Credentials are validated by the first service call; the second call
        re-validates (bcrypt ~1ms, excluded from crypto timing — acceptable).

        Raises ValueError if credentials are invalid.
        """
        classical_resp = self._classical.login(username, password)
        pqc_resp = self._pqc.login(username, password)

        return HybridTokenResponse(
            classical_token=classical_resp.access_token,
            pqc_token=pqc_resp.access_token,
            timing_classical=classical_resp.timing,
            timing_pqc=pqc_resp.timing,
        )

    def verify_tokens(
        self, classical_token: str, pqc_token: str
    ) -> HybridVerifyResponse:
        """Verify both tokens independently, returning comparative timings."""
        classical_resp = self._classical.verify_token(classical_token)
        pqc_resp = self._pqc.verify_token(pqc_token)

        # Prefer claims from classical token; fall back to PQC if classical invalid.
        claims = classical_resp.claims if classical_resp.valid else pqc_resp.claims

        return HybridVerifyResponse(
            classical_valid=classical_resp.valid,
            pqc_valid=pqc_resp.valid,
            claims=claims,
            timing_classical=classical_resp.timing,
            timing_pqc=pqc_resp.timing,
        )
