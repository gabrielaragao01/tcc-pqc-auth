"""HTTP throughput benchmark — measures req/s for each auth endpoint.

Usage:
    python -m benchmark.throughput [--base-url http://localhost:8000] [--burst 50]

Prerequisites: server must be running (uvicorn main:app).
Uses only login/verify endpoints with a pre-registered user (no /auth/register in the loop).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

from benchmark.metrics import detect_environment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


@dataclass
class ThroughputResult:
    endpoint: str
    mode: str  # "sequential" or "concurrent"
    total_requests: int
    total_time_s: float
    requests_per_second: float
    mean_latency_ms: float
    success_count: int
    error_count: int
    environment: str
    timestamp: str


def _register_user(base_url: str, username: str, password: str) -> None:
    """Ensure test user exists."""
    try:
        r = httpx.post(f"{base_url}/auth/register", json={"username": username, "password": password}, timeout=10)
        if r.status_code in (200, 201, 409):
            log.info("Test user '%s' ready (status=%d)", username, r.status_code)
    except httpx.ConnectError:
        log.error("Cannot connect to %s — is the server running?", base_url)
        raise


def _run_sequential(
    base_url: str, endpoint: str, payload: dict,
    n_requests: int, env: str,
) -> ThroughputResult:
    """Run N sequential requests, measuring total time and per-request latency."""
    latencies: list[float] = []
    errors = 0

    t_start = time.perf_counter()
    with httpx.Client(base_url=base_url, timeout=30) as client:
        for _ in range(n_requests):
            t0 = time.perf_counter()
            try:
                r = client.post(endpoint, json=payload)
                if r.status_code >= 400:
                    errors += 1
            except httpx.HTTPError:
                errors += 1
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)
    t_end = time.perf_counter()

    total_time = t_end - t_start
    return ThroughputResult(
        endpoint=endpoint,
        mode="sequential",
        total_requests=n_requests,
        total_time_s=round(total_time, 3),
        requests_per_second=round(n_requests / total_time, 2) if total_time > 0 else 0,
        mean_latency_ms=round(sum(latencies) / len(latencies), 3) if latencies else 0,
        success_count=n_requests - errors,
        error_count=errors,
        environment=env,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def _run_concurrent(
    base_url: str, endpoint: str, payload: dict,
    burst_size: int, env: str,
) -> ThroughputResult:
    """Fire burst_size requests concurrently, measuring throughput."""
    errors = 0

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        t_start = time.perf_counter()
        tasks = [client.post(endpoint, json=payload) for _ in range(burst_size)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        t_end = time.perf_counter()

    for r in responses:
        if isinstance(r, Exception) or (hasattr(r, "status_code") and r.status_code >= 400):
            errors += 1

    total_time = t_end - t_start
    return ThroughputResult(
        endpoint=endpoint,
        mode="concurrent",
        total_requests=burst_size,
        total_time_s=round(total_time, 3),
        requests_per_second=round(burst_size / total_time, 2) if total_time > 0 else 0,
        mean_latency_ms=round(total_time / burst_size * 1000, 3) if burst_size > 0 else 0,
        success_count=burst_size - errors,
        error_count=errors,
        environment=env,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _export_results(results: list[ThroughputResult]) -> None:
    filepath = RESULTS_DIR / "throughput.csv"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(results[0]).keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
    log.info("Throughput results → %s", filepath)


def main() -> None:
    parser = argparse.ArgumentParser(description="HTTP Throughput Benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--sequential", type=int, default=100, help="Sequential requests per endpoint")
    parser.add_argument("--burst", type=int, default=50, help="Concurrent burst size per endpoint")
    parser.add_argument("--environment", default=None)
    args = parser.parse_args()

    env = args.environment or detect_environment()
    credentials = {"username": "throughput_user", "password": "throughput_pass"}

    log.info("Throughput benchmark: base=%s, seq=%d, burst=%d", args.base_url, args.sequential, args.burst)

    # Register test user
    _register_user(args.base_url, credentials["username"], credentials["password"])

    # Endpoints to test (only login and verify, no register)
    endpoints = [
        ("/auth/login-classical", credentials),
        ("/auth/login-pqc", credentials),
        ("/auth/login-hybrid", credentials),
    ]

    all_results: list[ThroughputResult] = []

    for endpoint, payload in endpoints:
        log.info("Testing %s ...", endpoint)

        # Sequential
        result_seq = _run_sequential(args.base_url, endpoint, payload, args.sequential, env)
        all_results.append(result_seq)
        log.info("  sequential: %.1f req/s, mean=%.1fms", result_seq.requests_per_second, result_seq.mean_latency_ms)

        # Concurrent
        result_con = asyncio.run(_run_concurrent(args.base_url, endpoint, payload, args.burst, env))
        all_results.append(result_con)
        log.info("  concurrent: %.1f req/s, mean=%.1fms", result_con.requests_per_second, result_con.mean_latency_ms)

    # Verify endpoints (need tokens first)
    log.info("Generating tokens for verify benchmarks...")
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        classical_token = client.post("/auth/login-classical", json=credentials).json()["access_token"]
        pqc_token = client.post("/auth/login-pqc", json=credentials).json()["access_token"]

    verify_endpoints = [
        ("/auth/verify-classical", {"token": classical_token}),
        ("/auth/verify-pqc", {"token": pqc_token}),
        ("/auth/verify-hybrid", {"classical_token": classical_token, "pqc_token": pqc_token}),
    ]

    for endpoint, payload in verify_endpoints:
        log.info("Testing %s ...", endpoint)
        result_seq = _run_sequential(args.base_url, endpoint, payload, args.sequential, env)
        all_results.append(result_seq)
        log.info("  sequential: %.1f req/s, mean=%.1fms", result_seq.requests_per_second, result_seq.mean_latency_ms)

        result_con = asyncio.run(_run_concurrent(args.base_url, endpoint, payload, args.burst, env))
        all_results.append(result_con)
        log.info("  concurrent: %.1f req/s, mean=%.1fms", result_con.requests_per_second, result_con.mean_latency_ms)

    _export_results(all_results)

    # Print summary
    print("\n=== THROUGHPUT SUMMARY ===\n")
    for r in all_results:
        print(f"{r.endpoint:30s} {r.mode:12s} {r.requests_per_second:8.1f} req/s  "
              f"mean={r.mean_latency_ms:7.1f}ms  errors={r.error_count}")


if __name__ == "__main__":
    main()
