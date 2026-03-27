#!/bin/bash
# Run benchmarks locally (native ARM64 on macOS, or native x86_64 on Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "=== Phase 5: Benchmark Runner ==="
echo "Environment: $(python -c 'from benchmark.metrics import detect_environment; print(detect_environment())')"

# Step 1: Run the benchmark (raw crypto + service layer)
echo ""
echo "--- Running benchmark (N=100, warmup=10) ---"
python -m benchmark.runner "$@"

# Step 2: Compute statistics
echo ""
echo "--- Computing summary statistics ---"
python -m benchmark.analysis

# Step 3: Generate charts
echo ""
echo "--- Generating charts ---"
python -m benchmark.charts

echo ""
echo "=== Done! Results in results/ ==="
ls -la results/
