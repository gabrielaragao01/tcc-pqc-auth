"""Benchmark data models and environment detection."""

from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass
class BenchmarkSample:
    """Single measurement from one benchmark iteration."""

    iteration: int
    operation: str
    algorithm: str
    duration_ms: float
    tracemalloc_peak_bytes: int | float
    tracemalloc_current_bytes: int | float
    payload_size_bytes: int | None
    timestamp: str
    environment: str


def detect_environment() -> str:
    """Detect current platform for the environment field."""
    arch = platform.machine()  # e.g. "arm64", "x86_64"
    system = platform.system().lower()  # e.g. "darwin", "linux"
    return f"{arch}-{system}"
