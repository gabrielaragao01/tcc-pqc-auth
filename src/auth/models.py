from __future__ import annotations

from pydantic import BaseModel, Field


class AuthBenchmarkResult(BaseModel):
    """Single timing measurement captured during an auth operation."""

    model_config = {"frozen": True}

    operation: str = Field(description="Operation name (e.g. 'jwt_sign', 'jwt_verify').")
    duration_ms: float = Field(description="Wall-clock time in milliseconds (perf_counter).")
    algorithm: str = Field(description="Algorithm used (e.g. 'RS256', 'ML-DSA-44').")


class LoginRequest(BaseModel):
    """Credentials submitted for login."""

    username: str = Field(description="Username.")
    password: str = Field(description="Plaintext password.")


class RegisterRequest(BaseModel):
    """Credentials submitted for user registration."""

    username: str = Field(description="Desired username.")
    password: str = Field(description="Plaintext password (stored as bcrypt hash).")


class RegisterResponse(BaseModel):
    """Confirmation returned after successful registration."""

    username: str
    message: str = Field(default="User created successfully.")


class TokenResponse(BaseModel):
    """JWT token returned after a successful login."""

    access_token: str = Field(description="Signed JWT.")
    token_type: str = Field(default="bearer")
    algorithm: str = Field(description="Signing algorithm used (e.g. 'RS256').")
    timing: AuthBenchmarkResult = Field(description="Benchmark timing for the signing operation.")


class VerifyRequest(BaseModel):
    """Token submitted for verification."""

    token: str = Field(description="JWT to verify.")


class VerifyResponse(BaseModel):
    """Result of token verification."""

    valid: bool = Field(description="Whether the token signature and expiry are valid.")
    claims: dict | None = Field(default=None, description="Decoded JWT claims if valid.")
    timing: AuthBenchmarkResult = Field(description="Benchmark timing for the verify operation.")


class KEMExchangeResponse(BaseModel):
    """Result of a full KEM round-trip (keygen → encapsulate → decapsulate)."""

    model_config = {"frozen": True}

    secrets_match: bool = Field(description="Whether shared secrets from encapsulate and decapsulate are identical.")
    timing_keygen: AuthBenchmarkResult = Field(description="Benchmark timing for keypair generation.")
    timing_encapsulate: AuthBenchmarkResult = Field(description="Benchmark timing for encapsulation.")
    timing_decapsulate: AuthBenchmarkResult = Field(description="Benchmark timing for decapsulation.")


class HybridTokenResponse(BaseModel):
    """Dual-token response: classical RS256 + PQC ML-DSA-44."""

    model_config = {"frozen": True}

    classical_token: str = Field(description="RS256 JWT token.")
    pqc_token: str = Field(description="ML-DSA-44 signed PQC token.")
    token_type: str = Field(default="bearer")
    timing_classical: AuthBenchmarkResult = Field(description="RS256 signing timing.")
    timing_pqc: AuthBenchmarkResult = Field(description="ML-DSA-44 signing timing.")


class HybridVerifyRequest(BaseModel):
    """Both tokens submitted for hybrid verification."""

    classical_token: str = Field(description="RS256 JWT to verify.")
    pqc_token: str = Field(description="ML-DSA-44 PQC token to verify.")


class HybridVerifyResponse(BaseModel):
    """Dual verification result with comparative timings."""

    model_config = {"frozen": True}

    classical_valid: bool = Field(description="Whether the RS256 JWT is valid.")
    pqc_valid: bool = Field(description="Whether the ML-DSA-44 PQC token is valid.")
    claims: dict | None = Field(default=None, description="Decoded claims (from classical token if valid, else PQC).")
    timing_classical: AuthBenchmarkResult = Field(description="RS256 verify timing.")
    timing_pqc: AuthBenchmarkResult = Field(description="ML-DSA-44 verify timing.")
