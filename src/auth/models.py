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
