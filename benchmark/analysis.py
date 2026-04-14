"""Statistical analysis of benchmark results — reads raw_samples.csv, outputs summary CSVs.

Usage:
    python -m benchmark.analysis              # single-run (existing behavior)
    python -m benchmark.analysis --multi-run  # analyze all runs in results/runs/
"""

from __future__ import annotations

import argparse
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


def load_multi_run_samples() -> pd.DataFrame:
    """Load and concatenate CSVs from all per-run directories."""
    run_csvs = sorted(RESULTS_DIR.glob("runs/run_*/raw_samples.csv"))
    if not run_csvs:
        raise FileNotFoundError("No run directories found in results/runs/")
    frames = []
    for csv_path in run_csvs:
        df = pd.read_csv(csv_path)
        if "run_id" not in df.columns:
            run_id = int(csv_path.parent.name.split("_")[1])
            df["run_id"] = run_id
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    log.info("Loaded %d total samples from %d runs", len(combined), len(run_csvs))
    return combined


def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute summary statistics grouped by (operation, algorithm, environment).

    If run_id column is present, also groups by run_id for per-run breakdown.
    """
    group_cols = ["operation", "algorithm", "environment"]
    if "run_id" in df.columns:
        group_cols = ["run_id"] + group_cols

    grouped = df.groupby(group_cols)

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

    summary = summary.merge(p95, on=group_cols)
    summary = summary.merge(p99, on=group_cols)

    # Memory stats (tracemalloc)
    mem_stats = grouped["tracemalloc_peak_bytes"].agg(
        mean_tracemalloc_peak_bytes="mean",
        median_tracemalloc_peak_bytes="median",
    ).reset_index()
    summary = summary.merge(mem_stats, on=group_cols)

    # Payload size stats
    payload_stats = grouped["payload_size_bytes"].agg(
        mean_payload_size_bytes="mean",
    ).reset_index()
    summary = summary.merge(payload_stats, on=group_cols)

    # Round numeric columns
    numeric_cols = summary.select_dtypes(include=[np.number]).columns
    summary[numeric_cols] = summary[numeric_cols].round(4)

    return summary


def compute_inter_run_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute inter-run variance: per-run means → stats across runs.

    Returns one row per (operation, algorithm, environment) with:
    - n_runs, grand_mean_ms, inter_run_stdev_ms, CV%
    """
    # Step 1: per-run means
    per_run = df.groupby(["run_id", "operation", "algorithm", "environment"])["duration_ms"].agg(
        run_mean_ms="mean",
        run_median_ms="median",
    ).reset_index()

    # Step 2: across-run stats of the per-run means
    group_cols = ["operation", "algorithm", "environment"]
    inter = per_run.groupby(group_cols).agg(
        n_runs=("run_mean_ms", "count"),
        grand_mean_ms=("run_mean_ms", "mean"),
        grand_median_ms=("run_median_ms", "mean"),
        inter_run_stdev_ms=("run_mean_ms", "std"),
        inter_run_min_ms=("run_mean_ms", "min"),
        inter_run_max_ms=("run_mean_ms", "max"),
    ).reset_index()

    # CV% = stdev / mean * 100
    inter["inter_run_cv_pct"] = np.where(
        inter["grand_mean_ms"] > 0,
        inter["inter_run_stdev_ms"] / inter["grand_mean_ms"] * 100,
        0.0,
    )

    # Round
    numeric_cols = inter.select_dtypes(include=[np.number]).columns
    inter[numeric_cols] = inter[numeric_cols].round(4)

    return inter


def compute_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    """Build a side-by-side comparison table: classical vs PQC for matching operations.

    Works with both single-run summary (no run_id grouping) and inter-run stats
    (uses grand_mean_ms or mean_ms column).
    """
    # Determine which mean column to use
    mean_col = "grand_mean_ms" if "grand_mean_ms" in summary.columns else "mean_ms"
    median_col = "grand_median_ms" if "grand_median_ms" in summary.columns else "median_ms"

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

        speedup = c[mean_col] / p[mean_col] if p[mean_col] > 0 else float("inf")

        rows.append({
            "comparison": label,
            "classical_op": classical_op,
            "classical_algorithm": c["algorithm"],
            "classical_mean_ms": c[mean_col],
            "classical_median_ms": c[median_col],
            "pqc_op": pqc_op,
            "pqc_algorithm": p["algorithm"],
            "pqc_mean_ms": p[mean_col],
            "pqc_median_ms": p[median_col],
            "speedup_factor": round(speedup, 2),
        })

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="PQC Benchmark Analysis")
    parser.add_argument("--multi-run", action="store_true",
                        help="Analyze all runs in results/runs/ and compute inter-run stats")
    args = parser.parse_args()

    if args.multi_run:
        df = load_multi_run_samples()
        multi_dir = RESULTS_DIR / "multi_run"
        multi_dir.mkdir(parents=True, exist_ok=True)

        # Save combined CSV
        df.to_csv(multi_dir / "combined_samples.csv", index=False)
        log.info("Combined samples → %s", multi_dir / "combined_samples.csv")

        # Per-run summary (groups by run_id)
        summary = compute_summary(df)
        summary.to_csv(multi_dir / "summary_stats_all_runs.csv", index=False)
        log.info("Per-run summary → %s", multi_dir / "summary_stats_all_runs.csv")

        # Inter-run stats (the key deliverable)
        inter = compute_inter_run_stats(df)
        inter.to_csv(multi_dir / "inter_run_stats.csv", index=False)
        log.info("Inter-run stats → %s", multi_dir / "inter_run_stats.csv")

        print("\n=== INTER-RUN REPRODUCIBILITY (CV%) ===\n")
        print(inter[["operation", "algorithm", "n_runs", "grand_mean_ms",
                      "inter_run_stdev_ms", "inter_run_cv_pct"]].to_string(index=False))

        # Comparison using grand means
        comparison = compute_comparison(inter)
        if not comparison.empty:
            comparison.to_csv(multi_dir / "comparison.csv", index=False)
            print("\n=== CLASSICAL vs PQC COMPARISON (grand means) ===\n")
            print(comparison[["comparison", "classical_mean_ms", "pqc_mean_ms",
                              "speedup_factor"]].to_string(index=False))
    else:
        # Original single-run behavior (unchanged)
        df = load_samples()

        summary = compute_summary(df)
        summary_path = RESULTS_DIR / "summary_stats.csv"
        summary.to_csv(summary_path, index=False)
        log.info("Summary stats (%d rows) → %s", len(summary), summary_path)

        print("\n=== SUMMARY STATISTICS ===\n")
        print(summary[["operation", "algorithm", "mean_ms", "median_ms", "stdev_ms",
                        "p95_ms", "p99_ms"]].to_string(index=False))

        comparison = compute_comparison(summary)
        if not comparison.empty:
            comparison_path = RESULTS_DIR / "comparison.csv"
            comparison.to_csv(comparison_path, index=False)
            log.info("Comparison table (%d rows) → %s", len(comparison), comparison_path)

            print("\n=== CLASSICAL vs PQC COMPARISON ===\n")
            print(comparison[["comparison", "classical_mean_ms", "pqc_mean_ms",
                              "speedup_factor"]].to_string(index=False))


if __name__ == "__main__":
    main()
