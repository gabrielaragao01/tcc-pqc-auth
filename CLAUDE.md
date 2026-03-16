# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TCC (Trabalho de Conclusão de Curso) — Post-Quantum Cryptography (PQC) authentication system for web applications. The project benchmarks PQC algorithms (Kyber512 KEM, ML-DSA-44 signatures via liboqs) against classical cryptography (RSA/ECDSA + JWT). Built in 5 phases; currently in Phase 1.

> **Library versions in use:** liboqs 0.15.0 (C library, installed via Homebrew) + liboqs-python 0.14.1 (Python wrapper). Version mismatch is cosmetic — the mathematical core of all algorithms is identical. See `docs/context.md` Semana 2 for full context.

## Running the Application

```bash
# Activate virtual environment first
source venv/bin/activate

# Run development server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Run via Docker
docker build -t pqc-auth .
docker run -p 8000:8000 pqc-auth
```

Configuration is in `.env` — key variables:
- `PQC_ALGORITHM=Kyber512` — KEM algorithm (FIPS 203 equivalent: ML-KEM-512)
- `SIG_ALGORITHM=ML-DSA-44` — signature algorithm (FIPS 204, formerly Dilithium2)
- `CLASSICAL_ALGORITHM=RS256` — classical baseline
- `BENCHMARK_ITERATIONS=100` — perf test iterations

Smoke test endpoint: `GET /pqc/health`

## Architecture

Clean architecture with interface-based dependency injection, designed to grow across 5 phases without breaking existing layers.

### Layer Hierarchy

```
API Layer (src/api/routes.py)
  └── Service Layer (src/auth/service.py)
        └── Crypto Interfaces (src/crypto/interfaces.py)
              ├── KEM Implementation (src/crypto/kem/kyber.py)
              └── Signature Implementation (src/crypto/signatures/dilithium.py)
```

**Key design rule**: `oqs` (liboqs) is imported **only** in the concrete crypto implementations (`kyber.py`, `dilithium.py`). Service and API layers depend solely on the abstract interfaces (`IKeyEncapsulation`, `IDigitalSignature`).

### Crypto Abstractions (`src/crypto/interfaces.py`)

- `IKeyEncapsulation` — KEM interface: `generate_keypair()`, `encapsulate()`, `decapsulate()`, `validate()`
- `IDigitalSignature` — signature interface: `generate_keypair()`, `sign()`, `verify()`, `validate()`

Both implementations use liboqs context managers (`with oqs.KeyEncapsulation(...) as kem:`) to manage C-level resources safely.

### Domain Models (`src/crypto/models.py`)

Frozen Pydantic models (value objects): `KEMKeyPair`, `KEMResult`, `SignatureKeyPair`, `SmokeTestResult`, `PQCSmokeTestReport`.

### Service Layer (`src/auth/service.py`)

`PQCAuthService` is injected with concrete implementations at construction time (in `routes.py::_build_service()`). It orchestrates round-trip validation for smoke tests and will orchestrate authentication flows in later phases.

### Configuration (`src/config.py`)

Single `settings` singleton via `pydantic-settings`, loaded from `.env`.

## Development Rules (from `.cursorrules`)

- **Never implement crypto from scratch** — always use liboqs for PQC algorithms
- **Benchmark with `time.perf_counter()` and `psutil`** for memory — this is core thesis output
- **Type hints required** on all functions; use Pydantic models for all API schemas
- **SQLite** for persistence (not the focus — crypto benchmarking is)
- **Docker Compose mandatory** for multi-container setups in later phases

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Setup: liboqs, KEM, signatures, clean arch | ✅ Complete |
| 2 | Classical baseline (RSA/ECDSA + JWT) | Planned |
| 3 | Pure PQC authentication | Planned |
| 4 | Hybrid mode (classical + PQC) | Planned |
| 5 | Benchmarking & performance analysis | Planned |

Development diary with architecture decisions: `docs/context.md` (Portuguese).
