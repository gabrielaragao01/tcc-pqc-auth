"""Generate benchmark visualization charts from raw_samples.csv.

Usage:
    python -m benchmark.charts
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
DPI = 300
FIGSIZE = (12, 6)

# Consistent color palette for algorithms
PALETTE = {"RS256": "#2196F3", "RSA-2048": "#2196F3", "ML-DSA-44": "#4CAF50", "Kyber512": "#FF9800"}


def _load_data() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_DIR / "raw_samples.csv")
    return df


def _save(fig: plt.Figure, name: str) -> None:
    path = RESULTS_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved %s", path)


def chart_latency_comparison(df: pd.DataFrame) -> None:
    """Bar chart: mean latency per operation (classical vs PQC), log scale."""
    # Filter to service-layer sign/verify (most relevant for TCC)
    ops = ["jwt_sign", "pqc_sign", "jwt_verify", "pqc_verify"]
    subset = df[df["operation"].isin(ops)].copy()
    if subset.empty:
        return

    fig, ax = plt.subplots(figsize=FIGSIZE)
    sns.barplot(data=subset, x="operation", y="duration_ms", hue="algorithm",
                palette=PALETTE, errorbar="sd", ax=ax)
    ax.set_yscale("log")
    ax.set_xlabel("Operation")
    ax.set_ylabel("Latency (ms, log scale)")
    ax.set_title("Service-Layer Latency: Classical (RS256) vs PQC (ML-DSA-44)")
    ax.legend(title="Algorithm")
    _save(fig, "latency_comparison.png")


def chart_latency_boxplot(df: pd.DataFrame) -> None:
    """Box plot: latency distribution for all service-layer operations, log scale."""
    service_ops = ["jwt_sign", "jwt_verify", "pqc_sign", "pqc_verify",
                   "kem_keygen", "kem_encapsulate", "kem_decapsulate"]
    subset = df[df["operation"].isin(service_ops)].copy()
    if subset.empty:
        return

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.boxplot(data=subset, x="operation", y="duration_ms", hue="algorithm",
                palette=PALETTE, ax=ax)
    ax.set_yscale("log")
    ax.set_xlabel("Operation")
    ax.set_ylabel("Latency (ms, log scale)")
    ax.set_title("Latency Distribution (N=100, Service Layer)")
    ax.legend(title="Algorithm")
    plt.xticks(rotation=30, ha="right")
    _save(fig, "latency_boxplot.png")


def chart_latency_violin(df: pd.DataFrame) -> None:
    """Violin plot: raw crypto latency split into RSA (top) and PQC/KEM (bottom)."""
    raw_ops = [op for op in df["operation"].unique() if op.startswith("raw_")]
    subset = df[df["operation"].isin(raw_ops)].copy()
    if subset.empty:
        return

    rsa_ops = [op for op in raw_ops if "rsa" in op]
    pqc_ops = [op for op in raw_ops if "rsa" not in op]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Top: RSA operations (high latency range)
    rsa_data = subset[subset["operation"].isin(rsa_ops)]
    if not rsa_data.empty:
        sns.violinplot(data=rsa_data, x="operation", y="duration_ms", hue="algorithm",
                       palette=PALETTE, inner="box", ax=ax1)
        ax1.set_xlabel("")
        ax1.set_ylabel("Latency (ms)")
        ax1.set_title("Raw Crypto Latency — RSA-2048 (N=100)")
        ax1.legend(title="Algorithm")
        ax1.tick_params(axis="x", rotation=20)

    # Bottom: PQC + KEM operations (sub-millisecond range)
    pqc_data = subset[subset["operation"].isin(pqc_ops)]
    if not pqc_data.empty:
        sns.violinplot(data=pqc_data, x="operation", y="duration_ms", hue="algorithm",
                       palette=PALETTE, inner="box", ax=ax2)
        ax2.set_xlabel("Operation")
        ax2.set_ylabel("Latency (ms)")
        ax2.set_title("Raw Crypto Latency — ML-DSA-44 & Kyber512 (N=100)")
        ax2.legend(title="Algorithm")
        ax2.tick_params(axis="x", rotation=20)

    fig.tight_layout()
    _save(fig, "latency_violin.png")


def chart_memory_comparison(df: pd.DataFrame) -> None:
    """Bar chart: tracemalloc peak bytes per operation."""
    summary = df.groupby(["operation", "algorithm"])["tracemalloc_peak_bytes"].mean().reset_index()

    fig, ax = plt.subplots(figsize=FIGSIZE)
    sns.barplot(data=summary, x="operation", y="tracemalloc_peak_bytes", hue="algorithm",
                palette=PALETTE, ax=ax)
    ax.set_xlabel("Operation")
    ax.set_ylabel("Peak Memory Allocation (bytes)")
    ax.set_title("Python Heap Allocation per Operation (tracemalloc)")
    ax.legend(title="Algorithm")
    plt.xticks(rotation=40, ha="right")
    _save(fig, "memory_comparison.png")


def chart_payload_sizes(df: pd.DataFrame) -> None:
    """Horizontal bar chart: payload/artifact sizes."""
    # Get unique payload sizes per operation
    payload_df = df.dropna(subset=["payload_size_bytes"])
    if payload_df.empty:
        return
    sizes = payload_df.groupby(["operation", "algorithm"])["payload_size_bytes"].first().reset_index()
    sizes = sizes.sort_values("payload_size_bytes", ascending=True)

    fig, ax = plt.subplots(figsize=(10, max(6, len(sizes) * 0.4)))
    colors = [PALETTE.get(alg, "#999") for alg in sizes["algorithm"]]
    ax.barh(sizes["operation"], sizes["payload_size_bytes"], color=colors)
    ax.set_xlabel("Size (bytes)")
    ax.set_title("Payload / Artifact Sizes")

    # Add value labels
    for i, (_, row) in enumerate(sizes.iterrows()):
        ax.text(row["payload_size_bytes"] + 10, i, f'{int(row["payload_size_bytes"])}',
                va="center", fontsize=9)

    _save(fig, "payload_sizes.png")


def main() -> None:
    df = _load_data()
    log.info("Loaded %d samples for chart generation", len(df))

    chart_latency_comparison(df)
    chart_latency_boxplot(df)
    chart_latency_violin(df)
    chart_memory_comparison(df)
    chart_payload_sizes(df)

    log.info("All charts generated in %s", RESULTS_DIR)


if __name__ == "__main__":
    main()
