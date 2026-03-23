from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timedelta, timezone

from src.auth.models import AuthBenchmarkResult, KEMExchangeResponse, TokenResponse, VerifyResponse
from src.config import settings
from src.crypto.interfaces import IDigitalSignature, IKeyEncapsulation
from src.db.repository import UserRepository


# ---------------------------------------------------------------------------
# Token helpers (module-level, pure functions)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class PQCLoginService:
    """Orchestrates pure PQC authentication using ML-DSA-44 signatures with built-in timing.

    A single ML-DSA-44 keypair is generated at construction and reused for the
    lifetime of the service — identical lifecycle to ClassicalAuthService (RSA).

    Token format (JWT-like, custom):
        base64url(header) . base64url(payload) . base64url(signature)

    Standard JWT is not used because no JOSE library natively supports ML-DSA-44.
    The signed message is ``header_b64 + "." + payload_b64`` encoded as UTF-8 bytes.
    """

    def __init__(
        self,
        signature: IDigitalSignature,
        kem: IKeyEncapsulation,
        user_repo: UserRepository,
    ) -> None:
        self._signature = signature
        self._kem = kem
        self._user_repo = user_repo

        # Generate ML-DSA-44 keypair once.
        keypair = self._signature.generate_keypair()
        self._public_key: bytes = keypair.public_key
        self._private_key: bytes = keypair.private_key

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> TokenResponse:
        """Authenticate user and return a signed PQC token with timing metrics.

        Raises ValueError if credentials are invalid.
        """
        user = self._user_repo.get_by_username(username)
        if user is None or not self._user_repo.verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password.")

        now = datetime.now(timezone.utc)
        header = {"alg": "ML-DSA-44", "typ": "PQC"}
        payload = {
            "sub": user.username,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.jwt_expiration_minutes)).timestamp()),
        }

        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        message = (header_b64 + "." + payload_b64).encode()

        t0 = time.perf_counter()
        signature_bytes = self._signature.sign(message, self._private_key)
        t1 = time.perf_counter()

        token = header_b64 + "." + payload_b64 + "." + _b64url_encode(signature_bytes)
        timing = AuthBenchmarkResult(
            operation="pqc_sign",
            duration_ms=(t1 - t0) * 1000,
            algorithm="ML-DSA-44",
        )
        return TokenResponse(access_token=token, algorithm="ML-DSA-44", timing=timing)

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    def verify_token(self, token: str) -> VerifyResponse:
        """Verify a PQC token signature and expiry, returning claims and timing metrics."""
        parts = token.split(".")
        if len(parts) != 3:
            timing = AuthBenchmarkResult(
                operation="pqc_verify",
                duration_ms=0.0,
                algorithm="ML-DSA-44",
            )
            return VerifyResponse(valid=False, claims=None, timing=timing)

        header_b64, payload_b64, sig_b64 = parts
        message = (header_b64 + "." + payload_b64).encode()

        try:
            sig_bytes = _b64url_decode(sig_b64)
        except Exception:
            timing = AuthBenchmarkResult(
                operation="pqc_verify",
                duration_ms=0.0,
                algorithm="ML-DSA-44",
            )
            return VerifyResponse(valid=False, claims=None, timing=timing)

        t0 = time.perf_counter()
        valid = self._signature.verify(message, sig_bytes, self._public_key)
        t1 = time.perf_counter()

        timing = AuthBenchmarkResult(
            operation="pqc_verify",
            duration_ms=(t1 - t0) * 1000,
            algorithm="ML-DSA-44",
        )

        if not valid:
            return VerifyResponse(valid=False, claims=None, timing=timing)

        # Signature valid — check expiry (outside perf_counter, not a crypto op)
        try:
            payload_bytes = _b64url_decode(payload_b64)
            claims: dict = json.loads(payload_bytes)
            exp = claims.get("exp")
            if exp is not None and datetime.now(timezone.utc).timestamp() > exp:
                return VerifyResponse(valid=False, claims=None, timing=timing)
        except Exception:
            return VerifyResponse(valid=False, claims=None, timing=timing)

        return VerifyResponse(valid=True, claims=claims, timing=timing)

    # ------------------------------------------------------------------
    # KEM Exchange
    # ------------------------------------------------------------------

    def kem_exchange(self) -> KEMExchangeResponse:
        """Execute a full Kyber512 KEM round-trip (keygen → encapsulate → decapsulate).

        Each operation is timed independently. Intended for benchmarking only —
        in a real deployment keygen and encapsulation would happen on separate hosts.
        """
        t0 = time.perf_counter()
        kem_keypair = self._kem.generate_keypair()
        t1 = time.perf_counter()
        timing_keygen = AuthBenchmarkResult(
            operation="kem_keygen",
            duration_ms=(t1 - t0) * 1000,
            algorithm="Kyber512",
        )

        t0 = time.perf_counter()
        kem_result = self._kem.encapsulate(kem_keypair.public_key)
        t1 = time.perf_counter()
        timing_encapsulate = AuthBenchmarkResult(
            operation="kem_encapsulate",
            duration_ms=(t1 - t0) * 1000,
            algorithm="Kyber512",
        )

        t0 = time.perf_counter()
        decapsulated_secret = self._kem.decapsulate(kem_result.ciphertext, kem_keypair.private_key)
        t1 = time.perf_counter()
        timing_decapsulate = AuthBenchmarkResult(
            operation="kem_decapsulate",
            duration_ms=(t1 - t0) * 1000,
            algorithm="Kyber512",
        )

        return KEMExchangeResponse(
            secrets_match=(kem_result.shared_secret == decapsulated_secret),
            timing_keygen=timing_keygen,
            timing_encapsulate=timing_encapsulate,
            timing_decapsulate=timing_decapsulate,
        )
