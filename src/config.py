from __future__ import annotations

from typing import Literal

from pydantic import Field # pyright: ignore[reportMissingImports]
from pydantic_settings import BaseSettings, SettingsConfigDict # pyright: ignore[reportMissingImports]


class Settings(BaseSettings):
    """Application settings loaded from .env. Single source of truth for all config."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Runtime environment.",
    )
    pqc_algorithm: str = Field(
        default="Kyber512",
        description="KEM algorithm name as accepted by liboqs (e.g. 'Kyber512', 'Kyber768').",
    )
    sig_algorithm: str = Field(
        default="ML-DSA-44",
        description="Digital signature algorithm name as accepted by liboqs (FIPS 204).",
    )
    classical_algorithm: str = Field(
        default="RS256",
        description="Classical JWT algorithm identifier used in Phase 2 baseline.",
    )
    benchmark_iterations: int = Field(
        default=100,
        gt=0,
        description="Number of iterations for each benchmark run (Phase 5).",
    )
    benchmark_warmup: int = Field(
        default=10,
        gt=0,
        description="Warmup iterations before measurement (discarded).",
    )
    jwt_expiration_minutes: int = Field(
        default=30,
        gt=0,
        description="JWT token expiration time in minutes.",
    )
    rsa_key_size: int = Field(
        default=2048,
        description="RSA key size in bits for the classical authentication baseline.",
    )
    database_path: str = Field(
        default="data/pqc_auth.db",
        description="Path to the SQLite database file.",
    )


settings = Settings()
