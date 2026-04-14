"""Generate a PDF report with all benchmark charts and summary tables.

Usage:
    python scripts/generate_report_pdf.py
"""
from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
OUTPUT_PDF = RESULTS_DIR / "benchmark_report.pdf"


def _add_image_page(pdf: PdfPages, img_path: Path, title: str) -> None:
    """Add a full-page image with title."""
    img = mpimg.imread(str(img_path))
    h, w = img.shape[:2]
    aspect = w / h
    fig_w = 11
    fig_h = fig_w / aspect + 0.8  # extra for title

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.imshow(img)
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _add_table_page(pdf: PdfPages, df: pd.DataFrame, title: str, col_widths: list[float] | None = None) -> None:
    """Add a page with a formatted table."""
    n_rows = len(df)
    fig_h = max(4, 1.5 + n_rows * 0.35)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", y=0.98)

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)

    # Header styling
    for j in range(len(df.columns)):
        cell = table[0, j]
        cell.set_facecolor("#2196F3")
        cell.set_text_props(color="white", fontweight="bold")

    # Alternate row colors
    for i in range(1, n_rows + 1):
        for j in range(len(df.columns)):
            cell = table[i, j]
            if i % 2 == 0:
                cell.set_facecolor("#f5f5f5")

    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def main() -> None:
    multi_dir = RESULTS_DIR / "multi_run"

    # Load data
    inter_stats = pd.read_csv(multi_dir / "inter_run_stats.csv")
    comparison = pd.read_csv(multi_dir / "comparison.csv")

    with PdfPages(str(OUTPUT_PDF)) as pdf:
        # --- Cover page ---
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        ax.text(0.5, 0.65, "Benchmark Report", fontsize=28, fontweight="bold",
                ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.55, "Autenticacao Pos-Quantica em Aplicacoes Web", fontsize=16,
                ha="center", va="center", transform=ax.transAxes, color="#555")
        ax.text(0.5, 0.42, "ML-DSA-44 / Kyber512 vs RSA-2048 / RS256", fontsize=14,
                ha="center", va="center", transform=ax.transAxes, color="#777")
        ax.text(0.5, 0.30,
                "3 execucoes independentes  |  N=100 iteracoes/run  |  6000 amostras totais\n"
                "Ambiente: Apple Silicon (ARM64), macOS, Python 3.13\n"
                "liboqs 0.15.0 + liboqs-python 0.14.1",
                fontsize=11, ha="center", va="center", transform=ax.transAxes,
                color="#999", linespacing=1.6)
        ax.text(0.5, 0.12, "Gerado em: 2026-04-12", fontsize=10,
                ha="center", va="center", transform=ax.transAxes, color="#aaa")
        pdf.savefig(fig)
        plt.close(fig)

        # --- Table 1: Inter-run reproducibility ---
        table_df = inter_stats[["operation", "algorithm", "n_runs", "grand_mean_ms",
                                 "inter_run_stdev_ms", "inter_run_cv_pct"]].copy()
        table_df.columns = ["Operacao", "Algoritmo", "N Runs", "Grand Mean (ms)",
                            "Inter-Run StDev (ms)", "CV (%)"]
        table_df["Grand Mean (ms)"] = table_df["Grand Mean (ms)"].apply(lambda x: f"{x:.4f}")
        table_df["Inter-Run StDev (ms)"] = table_df["Inter-Run StDev (ms)"].apply(lambda x: f"{x:.4f}")
        table_df["CV (%)"] = table_df["CV (%)"].apply(lambda x: f"{x:.2f}%")
        _add_table_page(pdf, table_df, "Reprodutibilidade Inter-Run (3 execucoes)")

        # --- Table 2: Classical vs PQC comparison ---
        comp_df = comparison[["comparison", "classical_mean_ms", "pqc_mean_ms",
                               "speedup_factor"]].copy()
        comp_df.columns = ["Comparacao", "Classical Mean (ms)", "PQC Mean (ms)", "Speedup"]
        comp_df["Classical Mean (ms)"] = comp_df["Classical Mean (ms)"].apply(lambda x: f"{x:.4f}")
        comp_df["PQC Mean (ms)"] = comp_df["PQC Mean (ms)"].apply(lambda x: f"{x:.4f}")
        comp_df["Speedup"] = comp_df["Speedup"].apply(lambda x: f"{x:.1f}x")
        _add_table_page(pdf, comp_df, "Comparacao Classical vs PQC (Grand Means, 3 runs)")

        # --- Charts ---
        charts = [
            (RESULTS_DIR / "latency_comparison.png", "Latencia: Classical (RS256) vs PQC (ML-DSA-44)"),
            (RESULTS_DIR / "latency_boxplot.png", "Distribuicao de Latencia (N=300 total, Service Layer)"),
            (RESULTS_DIR / "latency_violin.png", "Distribuicao Raw Crypto (Violin Plot)"),
            (RESULTS_DIR / "memory_comparison.png", "Consumo de Memoria por Operacao (tracemalloc)"),
            (RESULTS_DIR / "payload_sizes.png", "Tamanho de Payloads e Artefatos"),
            (multi_dir / "inter_run_boxplot.png", "Reprodutibilidade: Distribuicao por Run"),
            (multi_dir / "inter_run_cv.png", "Coeficiente de Variacao (CV%) por Operacao"),
            (multi_dir / "run_means_comparison.png", "Medias por Run — Comparacao Lado a Lado"),
        ]

        for chart_path, title in charts:
            if chart_path.exists():
                _add_image_page(pdf, chart_path, title)

    print(f"PDF gerado: {OUTPUT_PDF}")
    print(f"  Paginas: 2 tabelas + {len([c for c in charts if c[0].exists()])} graficos + capa = "
          f"{2 + len([c for c in charts if c[0].exists()]) + 1} paginas total")


if __name__ == "__main__":
    main()
