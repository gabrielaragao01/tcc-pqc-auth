"""Benchmark runner — executes N iterations of each crypto operation and exports CSV.

Usage:
    python -m benchmark.runner [--environment arm64-macos]

Operates in two layers:
  Layer 1 (RAW): Direct crypto interface calls (no bcrypt, no JWT, no base64url)
  Layer 2 (SERVICE): Full service-layer calls (with bcrypt, token encoding, etc.)
"""

from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from benchmark.metrics import BenchmarkSample, detect_environment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


# ---------------------------------------------------------------------------
# In-memory database setup (same pattern as tests/conftest.py)
# ---------------------------------------------------------------------------

def _setup_memory_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database and patch modules to use it."""
    from src.db import database, repository
    from src.db.database import _CREATE_USERS_TABLE

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def _shared_conn() -> Generator[sqlite3.Connection, None, None]:
        yield conn

    database.get_connection = _shared_conn  # type: ignore[assignment]
    repository.get_connection = _shared_conn  # type: ignore[assignment]

    conn.execute(_CREATE_USERS_TABLE)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------

def _create_test_user(username: str = "benchuser", password: str = "benchpass") -> None:
    from src.db.repository import UserRepository
    repo = UserRepository()
    try:
        repo.create_user(username, password)
    except sqlite3.IntegrityError:
        pass  # already exists


def _build_classical_service():
    from src.auth.classical_service import ClassicalAuthService
    from src.crypto.classical.rsa import RSASignature
    from src.db.repository import UserRepository
    return ClassicalAuthService(signature=RSASignature(2048), user_repo=UserRepository())


def _build_pqc_service():
    from src.auth.pqc_service import PQCLoginService
    from src.crypto.kem.kyber import KyberKEM
    from src.crypto.signatures.dilithium import DilithiumSignature
    from src.db.repository import UserRepository
    return PQCLoginService(
        signature=DilithiumSignature("ML-DSA-44"),
        kem=KyberKEM("Kyber512"),
        user_repo=UserRepository(),
    )


def _build_hybrid_service():
    from src.auth.hybrid_service import HybridAuthService
    from src.crypto.classical.rsa import RSASignature
    from src.crypto.kem.kyber import KyberKEM
    from src.crypto.signatures.dilithium import DilithiumSignature
    from src.db.repository import UserRepository
    return HybridAuthService(
        classical_signature=RSASignature(2048),
        pqc_signature=DilithiumSignature("ML-DSA-44"),
        kem=KyberKEM("Kyber512"),
        user_repo=UserRepository(),
    )


# ---------------------------------------------------------------------------
# Benchmark helpers
# ---------------------------------------------------------------------------

def _measure_memory(fn, n_samples: int = 10) -> tuple[float, float]:
    """Run fn with tracemalloc in a separate pass to get average peak/current bytes.

    Separated from timing to avoid tracemalloc overhead contaminating perf_counter
    measurements (tracemalloc start/stop cycles can invalidate internal caches in
    the `cryptography` library, inflating RSA operations from ~1-2ms to ~44ms).
    """
    peaks, currents = [], []
    for _ in range(n_samples):
        tracemalloc.start()
        tracemalloc.reset_peak()
        fn()
        cur, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
        currents.append(cur)
    return sum(peaks) / len(peaks), sum(currents) / len(currents)


# ---------------------------------------------------------------------------
# Layer 1: RAW crypto benchmarks
# ---------------------------------------------------------------------------

def _run_raw_benchmarks(n_warmup: int, n_measure: int, env: str) -> list[BenchmarkSample]:
    """Benchmark raw crypto operations (no service layer, no bcrypt)."""
    from src.crypto.classical.rsa import RSASignature
    from src.crypto.kem.kyber import KyberKEM
    from src.crypto.signatures.dilithium import DilithiumSignature

    log.info("=== RAW CRYPTO BENCHMARKS ===")
    all_samples: list[BenchmarkSample] = []
    message = b"benchmark test message for signing operations"

    # --- RSA-2048 ---
    rsa = RSASignature(2048)
    rsa_kp = rsa.generate_keypair()

    all_samples.extend(_run_raw_timed(
        "raw_rsa_keygen", "RSA-2048", n_warmup, n_measure,
        fn=lambda: rsa.generate_keypair(),
        payload_fn=lambda r: len(r.public_key),
        env=env,
    ))

    rsa_sig = rsa.sign(message, rsa_kp.private_key)
    all_samples.extend(_run_raw_timed(
        "raw_rsa_sign", "RSA-2048", n_warmup, n_measure,
        fn=lambda: rsa.sign(message, rsa_kp.private_key),
        payload_fn=lambda r: len(r),
        env=env,
    ))
    all_samples.extend(_run_raw_timed(
        "raw_rsa_verify", "RSA-2048", n_warmup, n_measure,
        fn=lambda: rsa.verify(message, rsa_sig, rsa_kp.public_key),
        payload_fn=lambda _: len(rsa_sig),
        env=env,
    ))

    # --- ML-DSA-44 ---
    mldsa = DilithiumSignature("ML-DSA-44")
    mldsa_kp = mldsa.generate_keypair()

    all_samples.extend(_run_raw_timed(
        "raw_mldsa_keygen", "ML-DSA-44", n_warmup, n_measure,
        fn=lambda: mldsa.generate_keypair(),
        payload_fn=lambda r: len(r.public_key),
        env=env,
    ))
    mldsa_sig = mldsa.sign(message, mldsa_kp.private_key)
    all_samples.extend(_run_raw_timed(
        "raw_mldsa_sign", "ML-DSA-44", n_warmup, n_measure,
        fn=lambda: mldsa.sign(message, mldsa_kp.private_key),
        payload_fn=lambda r: len(r),
        env=env,
    ))
    all_samples.extend(_run_raw_timed(
        "raw_mldsa_verify", "ML-DSA-44", n_warmup, n_measure,
        fn=lambda: mldsa.verify(message, mldsa_sig, mldsa_kp.public_key),
        payload_fn=lambda _: len(mldsa_sig),
        env=env,
    ))

    # --- Kyber512 ---
    kem = KyberKEM("Kyber512")
    kem_kp = kem.generate_keypair()

    all_samples.extend(_run_raw_timed(
        "raw_kyber_keygen", "Kyber512", n_warmup, n_measure,
        fn=lambda: kem.generate_keypair(),
        payload_fn=lambda r: len(r.public_key),
        env=env,
    ))
    kem_result = kem.encapsulate(kem_kp.public_key)
    all_samples.extend(_run_raw_timed(
        "raw_kyber_encapsulate", "Kyber512", n_warmup, n_measure,
        fn=lambda: kem.encapsulate(kem_kp.public_key),
        payload_fn=lambda r: len(r.ciphertext),
        env=env,
    ))
    all_samples.extend(_run_raw_timed(
        "raw_kyber_decapsulate", "Kyber512", n_warmup, n_measure,
        fn=lambda: kem.decapsulate(kem_result.ciphertext, kem_kp.private_key),
        payload_fn=lambda r: len(r),
        env=env,
    ))

    return all_samples


def _run_raw_timed(
    operation: str, algorithm: str,
    n_warmup: int, n_measure: int,
    fn, payload_fn, env: str,
) -> list[BenchmarkSample]:
    """Run raw crypto operation: timing via perf_counter, memory via separate tracemalloc pass."""
    log.info("  [warmup] %s: %d iterations...", operation, n_warmup)
    for _ in range(n_warmup):
        fn()

    # Phase A: timing-only (no tracemalloc to avoid cache invalidation)
    timing_data: list[tuple[int, float, object]] = []
    log.info("  [measure] %s: %d iterations (timing)...", operation, n_measure)
    for i in range(n_measure):
        t0 = time.perf_counter()
        result = fn()
        t1 = time.perf_counter()
        timing_data.append((i, (t1 - t0) * 1000, result))

    # Phase B: memory-only (separate small sample)
    n_mem = min(10, n_measure)
    log.info("  [memory] %s: %d iterations (tracemalloc)...", operation, n_mem)
    avg_peak, avg_current = _measure_memory(fn, n_mem)

    # Combine timing + averaged memory
    samples: list[BenchmarkSample] = []
    for i, dur_ms, result in timing_data:
        samples.append(BenchmarkSample(
            iteration=i,
            operation=operation,
            algorithm=algorithm,
            duration_ms=dur_ms,
            tracemalloc_peak_bytes=avg_peak,
            tracemalloc_current_bytes=avg_current,
            payload_size_bytes=payload_fn(result),
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=env,
        ))

    return samples


# ---------------------------------------------------------------------------
# Layer 2: SERVICE benchmarks
# ---------------------------------------------------------------------------

def _run_service_benchmarks(n_warmup: int, n_measure: int, env: str) -> list[BenchmarkSample]:
    """Benchmark service-layer operations (includes bcrypt, token encoding)."""
    log.info("=== SERVICE LAYER BENCHMARKS ===")
    all_samples: list[BenchmarkSample] = []
    username, password = "benchuser", "benchpass"

    # --- Classical ---
    log.info("Building ClassicalAuthService (RSA keygen)...")
    classical = _build_classical_service()

    # jwt_sign (login)
    all_samples.extend(_run_service_op(
        "jwt_sign", n_warmup, n_measure, env,
        fn=lambda: classical.login(username, password),
        timing_attr="timing",
        payload_fn=lambda r: len(r.access_token.encode()),
    ))

    # jwt_verify
    token_resp = classical.login(username, password)
    classical_token = token_resp.access_token
    all_samples.extend(_run_service_op(
        "jwt_verify", n_warmup, n_measure, env,
        fn=lambda: classical.verify_token(classical_token),
        timing_attr="timing",
        payload_fn=lambda r: len(classical_token.encode()),
    ))

    # --- PQC ---
    log.info("Building PQCLoginService (ML-DSA-44 keygen)...")
    pqc = _build_pqc_service()

    # pqc_sign (login)
    all_samples.extend(_run_service_op(
        "pqc_sign", n_warmup, n_measure, env,
        fn=lambda: pqc.login(username, password),
        timing_attr="timing",
        payload_fn=lambda r: len(r.access_token.encode()),
    ))

    # pqc_verify
    pqc_token_resp = pqc.login(username, password)
    pqc_token = pqc_token_resp.access_token
    all_samples.extend(_run_service_op(
        "pqc_verify", n_warmup, n_measure, env,
        fn=lambda: pqc.verify_token(pqc_token),
        timing_attr="timing",
        payload_fn=lambda r: len(pqc_token.encode()),
    ))

    # KEM exchange (3 timings)
    all_samples.extend(_run_kem_benchmark(pqc, n_warmup, n_measure, env))

    # --- Hybrid ---
    log.info("Building HybridAuthService (RSA + ML-DSA-44 keygen)...")
    log.info("  Note: Hybrid login calls bcrypt 2x per iteration (~20s extra for N=100)")
    hybrid = _build_hybrid_service()

    # hybrid login (dual timings)
    all_samples.extend(_run_hybrid_login_benchmark(hybrid, username, password, n_warmup, n_measure, env))

    # hybrid verify (dual timings)
    hybrid_resp = hybrid.login(username, password)
    all_samples.extend(_run_hybrid_verify_benchmark(
        hybrid, hybrid_resp.classical_token, hybrid_resp.pqc_token, n_warmup, n_measure, env
    ))

    return all_samples


def _run_service_op(
    label: str, n_warmup: int, n_measure: int, env: str,
    fn, timing_attr: str, payload_fn,
) -> list[BenchmarkSample]:
    """Run a service operation: timing from service response, memory via separate pass."""
    log.info("  [warmup] %s: %d iterations...", label, n_warmup)
    for _ in range(n_warmup):
        fn()

    # Phase A: timing-only (service already measures via perf_counter internally)
    results: list[tuple[int, object]] = []
    log.info("  [measure] %s: %d iterations (timing)...", label, n_measure)
    for i in range(n_measure):
        result = fn()
        results.append((i, result))

    # Phase B: memory-only (separate small sample)
    n_mem = min(10, n_measure)
    log.info("  [memory] %s: %d iterations (tracemalloc)...", label, n_mem)
    avg_peak, avg_current = _measure_memory(fn, n_mem)

    # Combine
    samples: list[BenchmarkSample] = []
    for i, result in results:
        timing = getattr(result, timing_attr)
        samples.append(BenchmarkSample(
            iteration=i,
            operation=timing.operation,
            algorithm=timing.algorithm,
            duration_ms=timing.duration_ms,
            tracemalloc_peak_bytes=avg_peak,
            tracemalloc_current_bytes=avg_current,
            payload_size_bytes=payload_fn(result),
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=env,
        ))

    return samples


def _run_kem_benchmark(pqc_service, n_warmup: int, n_measure: int, env: str) -> list[BenchmarkSample]:
    """Benchmark KEM exchange (3 separate timings per iteration).

    Note: tracemalloc measures the aggregate KEM exchange (keygen+encapsulate+decapsulate),
    so all 3 sub-operations share the same average memory value.
    """
    log.info("  [warmup] kem_exchange: %d iterations...", n_warmup)
    for _ in range(n_warmup):
        pqc_service.kem_exchange()

    # Phase A: timing-only
    results: list[tuple[int, object]] = []
    log.info("  [measure] kem_exchange: %d iterations (timing)...", n_measure)
    for i in range(n_measure):
        result = pqc_service.kem_exchange()
        results.append((i, result))

    # Phase B: memory-only (aggregate for the entire kem_exchange call)
    n_mem = min(10, n_measure)
    log.info("  [memory] kem_exchange: %d iterations (tracemalloc)...", n_mem)
    avg_peak, avg_current = _measure_memory(pqc_service.kem_exchange, n_mem)

    # Combine
    samples: list[BenchmarkSample] = []
    for i, result in results:
        ts = datetime.now(timezone.utc).isoformat()
        for timing_attr in ("timing_keygen", "timing_encapsulate", "timing_decapsulate"):
            timing = getattr(result, timing_attr)
            samples.append(BenchmarkSample(
                iteration=i,
                operation=timing.operation,
                algorithm=timing.algorithm,
                duration_ms=timing.duration_ms,
                tracemalloc_peak_bytes=avg_peak,
                tracemalloc_current_bytes=avg_current,
                payload_size_bytes=None,
                timestamp=ts,
                environment=env,
            ))

    return samples


def _run_hybrid_login_benchmark(hybrid, username, password, n_warmup, n_measure, env):
    """Benchmark hybrid login (2 timings per iteration).

    Note: tracemalloc measures the aggregate hybrid login (classical+PQC signing),
    so both sub-operations share the same average memory value.
    """
    log.info("  [warmup] hybrid_login: %d iterations...", n_warmup)
    for _ in range(n_warmup):
        hybrid.login(username, password)

    # Phase A: timing-only
    results: list[tuple[int, object]] = []
    log.info("  [measure] hybrid_login: %d iterations (timing)...", n_measure)
    for i in range(n_measure):
        result = hybrid.login(username, password)
        results.append((i, result))

    # Phase B: memory-only (aggregate for the entire hybrid login)
    n_mem = min(10, n_measure)
    log.info("  [memory] hybrid_login: %d iterations (tracemalloc)...", n_mem)
    avg_peak, avg_current = _measure_memory(lambda: hybrid.login(username, password), n_mem)

    # Combine
    samples: list[BenchmarkSample] = []
    for i, result in results:
        ts = datetime.now(timezone.utc).isoformat()
        samples.append(BenchmarkSample(
            iteration=i, operation="hybrid_sign_classical",
            algorithm=result.timing_classical.algorithm,
            duration_ms=result.timing_classical.duration_ms,
            tracemalloc_peak_bytes=avg_peak, tracemalloc_current_bytes=avg_current,
            payload_size_bytes=len(result.classical_token.encode()),
            timestamp=ts, environment=env,
        ))
        samples.append(BenchmarkSample(
            iteration=i, operation="hybrid_sign_pqc",
            algorithm=result.timing_pqc.algorithm,
            duration_ms=result.timing_pqc.duration_ms,
            tracemalloc_peak_bytes=avg_peak, tracemalloc_current_bytes=avg_current,
            payload_size_bytes=len(result.pqc_token.encode()),
            timestamp=ts, environment=env,
        ))

    return samples


def _run_hybrid_verify_benchmark(hybrid, classical_token, pqc_token, n_warmup, n_measure, env):
    """Benchmark hybrid verify (2 timings per iteration).

    Note: tracemalloc measures the aggregate hybrid verify (classical+PQC verification),
    so both sub-operations share the same average memory value.
    """
    log.info("  [warmup] hybrid_verify: %d iterations...", n_warmup)
    for _ in range(n_warmup):
        hybrid.verify_tokens(classical_token, pqc_token)

    # Phase A: timing-only
    results: list[tuple[int, object]] = []
    log.info("  [measure] hybrid_verify: %d iterations (timing)...", n_measure)
    for i in range(n_measure):
        result = hybrid.verify_tokens(classical_token, pqc_token)
        results.append((i, result))

    # Phase B: memory-only (aggregate for the entire hybrid verify)
    n_mem = min(10, n_measure)
    log.info("  [memory] hybrid_verify: %d iterations (tracemalloc)...", n_mem)
    avg_peak, avg_current = _measure_memory(
        lambda: hybrid.verify_tokens(classical_token, pqc_token), n_mem
    )

    # Combine
    samples: list[BenchmarkSample] = []
    for i, result in results:
        ts = datetime.now(timezone.utc).isoformat()
        samples.append(BenchmarkSample(
            iteration=i, operation="hybrid_verify_classical",
            algorithm=result.timing_classical.algorithm,
            duration_ms=result.timing_classical.duration_ms,
            tracemalloc_peak_bytes=avg_peak, tracemalloc_current_bytes=avg_current,
            payload_size_bytes=len(classical_token.encode()),
            timestamp=ts, environment=env,
        ))
        samples.append(BenchmarkSample(
            iteration=i, operation="hybrid_verify_pqc",
            algorithm=result.timing_pqc.algorithm,
            duration_ms=result.timing_pqc.duration_ms,
            tracemalloc_peak_bytes=avg_peak, tracemalloc_current_bytes=avg_current,
            payload_size_bytes=len(pqc_token.encode()),
            timestamp=ts, environment=env,
        ))

    return samples


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _export_csv(samples: list[BenchmarkSample], filepath: Path) -> None:
    """Write all samples to CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(samples[0]).keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in samples:
            writer.writerow(asdict(s))
    log.info("Exported %d samples to %s", len(samples), filepath)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="PQC Benchmark Runner")
    parser.add_argument("--environment", default=None, help="Override environment label")
    args = parser.parse_args()

    from src.config import settings
    n_warmup = settings.benchmark_warmup
    n_measure = settings.benchmark_iterations
    env = args.environment or detect_environment()

    log.info("Benchmark config: N=%d, warmup=%d, environment=%s", n_measure, n_warmup, env)

    # Setup in-memory DB and test user
    conn = _setup_memory_db()
    _create_test_user()

    t_start = time.perf_counter()

    # Layer 1: Raw crypto
    raw_samples = _run_raw_benchmarks(n_warmup, n_measure, env)

    # Layer 2: Service layer
    service_samples = _run_service_benchmarks(n_warmup, n_measure, env)

    all_samples = raw_samples + service_samples
    t_end = time.perf_counter()

    log.info("Total benchmark time: %.1f seconds", t_end - t_start)
    log.info("Total samples collected: %d", len(all_samples))

    # Export
    _export_csv(all_samples, RESULTS_DIR / "raw_samples.csv")

    # Unique operations summary
    ops = sorted(set(s.operation for s in all_samples))
    log.info("Operations benchmarked (%d): %s", len(ops), ", ".join(ops))

    conn.close()


if __name__ == "__main__":
    main()
