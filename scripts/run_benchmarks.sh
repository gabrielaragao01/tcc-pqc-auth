#!/bin/bash
# Run benchmarks locally (native ARM64 on macOS, or native x86_64 on Linux)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
source venv/bin/activate

ENV_LABEL="$(python -c 'from benchmark.metrics import detect_environment; print(detect_environment())')"
echo "Environment: $ENV_LABEL"

# Check for --multi-run flag
MULTI_RUN=false
NUM_RUNS=3
COOLDOWN=30
REMAINING_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --multi-run) MULTI_RUN=true ;;
        *) REMAINING_ARGS+=("$arg") ;;
    esac
done

if [ "$MULTI_RUN" = true ]; then
    echo ""
    echo "=== Multi-Run Benchmark (${NUM_RUNS} runs, ${COOLDOWN}s cooldown) ==="

    for RUN_ID in $(seq 1 $NUM_RUNS); do
        echo ""
        echo "--- Run ${RUN_ID}/${NUM_RUNS} ---"
        python -m benchmark.runner --run-id "$RUN_ID" "${REMAINING_ARGS[@]}"
        echo "  Run ${RUN_ID} complete."

        if [ "$RUN_ID" -lt "$NUM_RUNS" ]; then
            echo "  Cooling down ${COOLDOWN}s (avoid thermal throttling)..."
            sleep "$COOLDOWN"
        fi
    done

    echo ""
    echo "--- Computing multi-run analysis ---"
    python -m benchmark.analysis --multi-run

    echo ""
    echo "--- Generating multi-run charts ---"
    python -m benchmark.charts --multi-run

    echo ""
    echo "=== Done! Multi-run results ==="
    echo "Per-run data:"
    ls -la results/runs/run_*/
    echo ""
    echo "Combined analysis:"
    ls -la results/multi_run/
else
    echo ""
    echo "=== Phase 5: Benchmark Runner (single run) ==="

    # Step 1: Run the benchmark (raw crypto + service layer)
    echo ""
    echo "--- Running benchmark (N=100, warmup=10) ---"
    python -m benchmark.runner "${REMAINING_ARGS[@]}"

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
fi
