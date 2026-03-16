from __future__ import annotations

from pydantic import BaseModel, Field # pyright: ignore[reportMissingImports]


class KEMKeyPair(BaseModel):
    """Immutable value object holding a KEM public/private key pair."""

    model_config = {"frozen": True}

    public_key: bytes = Field(description="Public key bytes used for encapsulation.")
    private_key: bytes = Field(description="Private key bytes used for decapsulation.")


class KEMResult(BaseModel):
    """Immutable value object holding the output of a KEM encapsulation."""

    model_config = {"frozen": True}

    ciphertext: bytes = Field(description="Encapsulated ciphertext to send to the recipient.")
    shared_secret: bytes = Field(description="Shared secret established on the sender side.")


class SignatureKeyPair(BaseModel):
    """Immutable value object holding a digital signature public/private key pair."""

    model_config = {"frozen": True}

    public_key: bytes = Field(description="Verification (public) key bytes.")
    private_key: bytes = Field(description="Signing (private) key bytes.")


class SmokeTestResult(BaseModel):
    """Structured result for a single algorithm smoke test."""

    model_config = {"frozen": True}

    algorithm: str = Field(description="Canonical algorithm name (e.g. 'Kyber512', 'Dilithium2').")
    passed: bool = Field(description="True if the round-trip completed without error.")
    error: str | None = Field(
        default=None,
        description="Human-readable error message when passed=False, else None.",
    )


class PQCSmokeTestReport(BaseModel):
    """Aggregated report of all PQC smoke tests."""

    model_config = {"frozen": True}

    all_passed: bool = Field(description="True only when every individual smoke test passed.")
    results: list[SmokeTestResult] = Field(
        description="Ordered list of individual smoke test results."
    )
