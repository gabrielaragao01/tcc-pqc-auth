"""Statistical analysis of benchmark results — reads raw_samples.csv, outputs summary CSVs.

Usage:
    python -m benchmark.analysis
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def load_samples(filepath: Path | None = None) -> pd.DataFrame:
    """Load raw_samples.csv into a DataFrame."""
    path = filepath or (RESULTS_DIR / "raw_samples.csv")
    df = pd.read_csv(path)
    log.info("Loaded %d samples from %s", len(df), path)
    return df


def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute summary statistics grouped by (operation, algorithm, environment)."""
    grouped = df.groupby(["operation", "algorithm", "environment"])

    summary = grouped["duration_ms"].agg(
        count="count",
        mean_ms="mean",
        median_ms="median",
        stdev_ms="std",
        min_ms="min",
        max_ms="max",
    ).reset_index()

    # Add percentiles
    p95 = grouped["duration_ms"].quantile(0.95).reset_index().rename(columns={"duration_ms": "p95_ms"})
    p99 = grouped["duration_ms"].quantile(0.99).reset_index().rename(columns={"duration_ms": "p99_ms"})

    summary = summary.merge(p95, on=["operation", "algorithm", "environment"])
    summary = summary.merge(p99, on=["operation", "algorithm", "environment"])

    # Memory stats (tracemalloc)
    mem_stats = grouped["tracemalloc_peak_bytes"].agg(
        mean_tracemalloc_peak_bytes="mean",
        median_tracemalloc_peak_bytes="median",
    ).reset_index()
    summary = summary.merge(mem_stats, on=["operation", "algorithm", "environment"])

    # Payload size stats
    payload_stats = grouped["payload_size_bytes"].agg(
        mean_payload_size_bytes="mean",
    ).reset_index()
    summary = summary.merge(payload_stats, on=["operation", "algorithm", "environment"])

    # Round numeric columns
    numeric_cols = summary.select_dtypes(include=[np.number]).columns
    summary[numeric_cols] = summary[numeric_cols].round(4)

    return summary


def compute_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    """Build a side-by-side comparison table: classical vs PQC for matching operations."""
    # Map service-layer operations to pairs
    pairs = [
        ("jwt_sign", "pqc_sign", "Token Signing"),
        ("jwt_verify", "pqc_verify", "Token Verification"),
        ("raw_rsa_keygen", "raw_mldsa_keygen", "Key Generation (raw)"),
        ("raw_rsa_sign", "raw_mldsa_sign", "Signature (raw)"),
        ("raw_rsa_verify", "raw_mldsa_verify", "Verification (raw)"),
    ]

    rows = []
    for classical_op, pqc_op, label in pairs:
        classical = summary[summary["operation"] == classical_op]
        pqc = summary[summary["operation"] == pqc_op]

        if classical.empty or pqc.empty:
            continue

        c = classical.iloc[0]
        p = pqc.iloc[0]

        speedup = c["mean_ms"] / p["mean_ms"] if p["mean_ms"] > 0 else float("inf")

        rows.append({
            "comparison": label,
            "classical_op": classical_op,
            "classical_algorithm": c["algorithm"],
            "classical_mean_ms": c["mean_ms"],
            "classical_median_ms": c["median_ms"],
            "classical_p95_ms": c["p95_ms"],
            "pqc_op": pqc_op,
            "pqc_algorithm": p["algorithm"],
            "pqc_mean_ms": p["mean_ms"],
            "pqc_median_ms": p["median_ms"],
            "pqc_p95_ms": p["p95_ms"],
            "speedup_factor": round(speedup, 2),
        })

    return pd.DataFrame(rows)


def main() -> None:
    df = load_samples()

    summary = compute_summary(df)
    summary_path = RESULTS_DIR / "summary_stats.csv"
    summary.to_csv(summary_path, index=False)
    log.info("Summary stats (%d rows) → %s", len(summary), summary_path)

    # Print summary table
    print("\n=== SUMMARY STATISTICS ===\n")
    print(summary[["operation", "algorithm", "mean_ms", "median_ms", "stdev_ms", "p95_ms", "p99_ms"]].to_string(index=False))

    comparison = compute_comparison(summary)
    if not comparison.empty:
        comparison_path = RESULTS_DIR / "comparison.csv"
        comparison.to_csv(comparison_path, index=False)
        log.info("Comparison table (%d rows) → %s", len(comparison), comparison_path)

        print("\n=== CLASSICAL vs PQC COMPARISON ===\n")
        print(comparison[["comparison", "classical_mean_ms", "pqc_mean_ms", "speedup_factor"]].to_string(index=False))


if __name__ == "__main__":
    main()
