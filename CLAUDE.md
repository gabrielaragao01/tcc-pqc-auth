# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TCC (Trabalho de Conclusão de Curso) — Post-Quantum Cryptography (PQC) authentication system for web applications. The project benchmarks PQC algorithms (Kyber512 KEM, ML-DSA-44 signatures via liboqs) against classical cryptography (RSA-2048 + JWT RS256). Built in 5 phases; **all phases complete**.

> **Library versions in use:** liboqs 0.15.0 (C library, compiled from source) + liboqs-python 0.14.1 (Python wrapper). Version mismatch is cosmetic — the mathematical core of all algorithms is identical. See `docs/context.md` Semana 2 for full context.

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
- `SIG_ALGORITHM=ML-DSA-44` — PQC signature algorithm (FIPS 204, formerly Dilithium2)
- `CLASSICAL_ALGORITHM=RS256` — classical baseline JWT algorithm
- `BENCHMARK_ITERATIONS=100` — perf test iterations (Phase 5)
- `BENCHMARK_WARMUP=10` — warmup iterations before measurement (discarded)
- `JWT_EXPIRATION_MINUTES=30` — token lifetime
- `RSA_KEY_SIZE=2048` — RSA key size for classical baseline
- `DATABASE_PATH=data/pqc_auth.db` — SQLite file path

Smoke test endpoints: `GET /pqc/health`, `GET /docs`

## Architecture

Clean architecture with interface-based dependency injection, designed to grow across 5 phases without breaking existing layers.

### Full Directory Structure (Phase 5)

```
benchmark/
  __init__.py                     ← package init
  __main__.py                     ← allows `python -m benchmark.runner`
  runner.py                       ← benchmark runner: warmup, N=100, timing + tracemalloc
  metrics.py                      ← BenchmarkSample dataclass, detect_environment()
  analysis.py                     ← statistics: mean, median, stdev, P95, P99 + CSV export
  charts.py                       ← bar charts, box plots, violin plots (matplotlib/seaborn)
  throughput.py                   ← HTTP throughput test via httpx
results/                          ← benchmark output (CSVs, PNGs) — gitignored except .gitkeep
scripts/
  run_benchmarks.sh               ← full benchmark pipeline: runner → analysis → charts
src/
  config.py                       ← pydantic-settings singleton, reads .env
  crypto/
    __init__.py
    interfaces.py                 ← IKeyEncapsulation, IDigitalSignature (ABCs)
    models.py                     ← KEMKeyPair, KEMResult, SignatureKeyPair, SmokeTestResult, PQCSmokeTestReport
    kem/
      __init__.py
      kyber.py                    ← KyberKEM(IKeyEncapsulation) via liboqs
    signatures/
      __init__.py
      dilithium.py                ← DilithiumSignature(IDigitalSignature) via liboqs
    classical/
      __init__.py
      rsa.py                      ← RSASignature(IDigitalSignature) via cryptography lib
  db/
    __init__.py
    database.py                   ← init_db(), get_connection() context manager
    models.py                     ← User Pydantic model
    repository.py                 ← UserRepository (create_user, get_by_username, verify_password)
  auth/
    __init__.py
    models.py                     ← AuthBenchmarkResult, LoginRequest, TokenResponse, VerifyResponse, HybridTokenResponse, ...
    service.py                    ← PQCAuthService (smoke tests, Phase 1)
    classical_service.py          ← ClassicalAuthService (login + verify with timing, Phase 2)
    pqc_service.py                ← PQCLoginService (login + verify + kem_exchange with timing, Phase 3)
    hybrid_service.py             ← HybridAuthService (composes Classical + PQC, Phase 4)
  api/
    __init__.py
    routes.py                     ← GET /pqc/health (Phase 1)
    auth_routes.py                ← POST /auth/register, /login-classical, /verify-classical (Phase 2)
    pqc_auth_routes.py            ← POST /auth/login-pqc, /verify-pqc, /kem-exchange (Phase 3)
    hybrid_auth_routes.py         ← POST /auth/login-hybrid, /auth/verify-hybrid (Phase 4)
main.py                           ← FastAPI app, lifespan (init_db), includes all routers
```

### Layer Hierarchy

```
API Layer (src/api/routes.py, auth_routes.py, pqc_auth_routes.py, hybrid_auth_routes.py)
  └── Service Layer (src/auth/service.py, classical_service.py, pqc_service.py, hybrid_service.py)
        └── Crypto Interfaces (src/crypto/interfaces.py)
              ├── KEM — PQC (src/crypto/kem/kyber.py)          ← liboqs only
              ├── Signature — PQC (src/crypto/signatures/dilithium.py)  ← liboqs only
              └── Signature — Classical (src/crypto/classical/rsa.py)   ← cryptography only
        └── Database Layer (src/db/)
              └── UserRepository (src/db/repository.py)        ← bcrypt + sqlite3
```

**Key design rules:**
- `oqs` (liboqs) is imported **only** in `kyber.py` and `dilithium.py`
- `cryptography` lib is imported **only** in `rsa.py`
- Service and API layers depend solely on abstract interfaces (`IKeyEncapsulation`, `IDigitalSignature`)
- `perf_counter()` timing wraps **only** the crypto operation inside the service — never HTTP/DB overhead

### Crypto Abstractions (`src/crypto/interfaces.py`)

- `IKeyEncapsulation` — KEM interface: `generate_keypair()`, `encapsulate()`, `decapsulate()`, `validate()`
- `IDigitalSignature` — signature interface: `generate_keypair()`, `sign()`, `verify()`, `validate()`

Both PQC implementations use liboqs context managers (`with oqs.KeyEncapsulation(...) as kem:`).
`RSASignature` implements the same `IDigitalSignature` interface using RSA-PSS + SHA-256.

### Domain Models

**Crypto models** (`src/crypto/models.py`) — frozen Pydantic value objects:
`KEMKeyPair`, `KEMResult`, `SignatureKeyPair`, `SmokeTestResult`, `PQCSmokeTestReport`

**Auth models** (`src/auth/models.py`) — frozen Pydantic value objects:
`AuthBenchmarkResult`, `LoginRequest`, `RegisterRequest`, `RegisterResponse`, `TokenResponse`, `VerifyRequest`, `VerifyResponse`, `KEMExchangeResponse`, `HybridTokenResponse`, `HybridVerifyRequest`, `HybridVerifyResponse`

### Service Layer

- `PQCAuthService` (`src/auth/service.py`) — injected with KEM + signature impls; runs smoke tests; Phase 1
- `ClassicalAuthService` (`src/auth/classical_service.py`) — injected with `RSASignature` + `UserRepository`; generates RSA keypair once at init; `login()` and `verify_token()` each return their result plus an `AuthBenchmarkResult` with `duration_ms`
- `PQCLoginService` (`src/auth/pqc_service.py`) — injected with `DilithiumSignature` + `KyberKEM` + `UserRepository`; generates ML-DSA-44 keypair once at init; `login()` and `verify_token()` use custom base64url token format; `kem_exchange()` runs full Kyber512 round-trip with per-operation timing
- `HybridAuthService` (`src/auth/hybrid_service.py`) — composes `ClassicalAuthService` + `PQCLoginService` via constructor injection; `login()` returns dual tokens (RS256 + ML-DSA-44) with separate timings; `verify_tokens()` verifies both independently with comparative timings

### Database Layer (`src/db/`)

SQLite via built-in `sqlite3`. No ORM. Schema: single `users` table (`id`, `username`, `password_hash`, `created_at`). Created at startup via `init_db()` called in the FastAPI lifespan event. Thread-safe: new connection per call in `get_connection()`.

### Configuration (`src/config.py`)

Single `settings` singleton via `pydantic-settings`, loaded from `.env`.

## Development Rules (from `.cursorrules`)

- **Never implement crypto from scratch** — always use liboqs for PQC, `cryptography` lib for classical
- **Benchmark with `time.perf_counter()`** — wrap only the crypto operation; exclude I/O, DB, network
- **`psutil`** for memory measurement in Phase 5
- **Type hints required** on all functions; use Pydantic models for all API schemas
- **SQLite** for persistence (not the focus — crypto benchmarking is)
- **Docker Compose mandatory** for multi-container setups in later phases

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 1 | Setup: liboqs, KEM, signatures, clean arch | ✅ Complete |
| 2 | Classical baseline: RSA-2048, JWT RS256, SQLite, `/auth/*` endpoints | ✅ Complete |
| 3 | Pure PQC authentication: ML-DSA-44 tokens, Kyber512 KEM handshake | ✅ Complete |
| 4 | Hybrid mode: classical + PQC side by side, dual-token strategy | ✅ Complete |
| 5 | Benchmarking & performance analysis: N=100 iterations, CSV export, charts | ✅ Complete |

Development diary with architecture decisions: `docs/context.md` (Portuguese).
Formal benchmark data (N=100): `docs/benchmarks.md`.
Raw data + charts: `results/` directory.

## Running Benchmarks (Phase 5)

```bash
# Full benchmark pipeline (local, ~2 min)
./scripts/run_benchmarks.sh

# Multi-run benchmark (3 runs for reproducibility, ~8 min)
./scripts/run_benchmarks.sh --multi-run

# Or step by step (multi-run):
python -m benchmark.runner --run-id 1
python -m benchmark.runner --run-id 2
python -m benchmark.runner --run-id 3
python -m benchmark.analysis --multi-run
python -m benchmark.charts --multi-run

# Or step by step (single run):
python -m benchmark.runner --environment arm64-macos
python -m benchmark.analysis
python -m benchmark.charts

# HTTP throughput test (requires running server)
uvicorn main:app &
python -m benchmark.throughput

# Via Docker
docker compose --profile benchmark run benchmark
```
