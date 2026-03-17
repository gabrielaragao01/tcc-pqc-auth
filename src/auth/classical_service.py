from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt  # PyJWT

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_der_private_key,
)

from src.auth.models import AuthBenchmarkResult, TokenResponse, VerifyResponse
from src.config import settings
from src.crypto.interfaces import IDigitalSignature
from src.db.repository import UserRepository


class ClassicalAuthService:
    """Orchestrates classical RSA + JWT authentication with built-in timing.

    RSA keys are generated once at construction and held in memory for the
    lifetime of the service. This mirrors the PQC approach in Phase 3, ensuring
    an apples-to-apples benchmark comparison.
    """

    def __init__(
        self,
        signature: IDigitalSignature,
        user_repo: UserRepository,
    ) -> None:
        self._signature = signature
        self._user_repo = user_repo

        # Generate RSA keypair once. Store DER bytes for IDigitalSignature use
        # and PEM bytes for PyJWT (RS256 requires PEM-encoded keys).
        keypair = self._signature.generate_keypair()

        private_key_obj = load_der_private_key(keypair.private_key, password=None)
        self._private_key_pem = private_key_obj.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
        self._public_key_pem = private_key_obj.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )

    def login(self, username: str, password: str) -> TokenResponse:
        """Authenticate user and return a signed RS256 JWT with timing metrics.

        Raises ValueError if credentials are invalid.
        """
        user = self._user_repo.get_by_username(username)
        if user is None or not self._user_repo.verify_password(password, user.password_hash):
            raise ValueError("Invalid username or password.")

        payload = {
            "sub": user.username,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes),
        }

        t0 = time.perf_counter()
        token = jwt.encode(payload, self._private_key_pem, algorithm="RS256")
        t1 = time.perf_counter()

        timing = AuthBenchmarkResult(
            operation="jwt_sign",
            duration_ms=(t1 - t0) * 1000,
            algorithm="RS256",
        )
        return TokenResponse(access_token=token, algorithm="RS256", timing=timing)

    def verify_token(self, token: str) -> VerifyResponse:
        """Decode and verify a JWT, returning claims and timing metrics."""
        t0 = time.perf_counter()
        try:
            claims = jwt.decode(token, self._public_key_pem, algorithms=["RS256"])
            valid = True
        except jwt.PyJWTError:
            claims = None
            valid = False
        t1 = time.perf_counter()

        timing = AuthBenchmarkResult(
            operation="jwt_verify",
            duration_ms=(t1 - t0) * 1000,
            algorithm="RS256",
        )
        return VerifyResponse(valid=valid, claims=claims, timing=timing)
