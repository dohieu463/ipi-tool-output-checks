#!/usr/bin/env bash
# Deprecated entry point, kept so existing commands keep working.
#
# Use scripts/run_batch.sh instead: it takes RESULTS_DIR / LOGDIR / TAG / SEED so several
# batches can run in parallel without overwriting each other, and it retries failed jobs.
# This shim runs the full grid into results/ exactly like the original run_all.sh; note
# that results/ is the unseeded pilot, so do not point it at the reported seed directories.
set -euo pipefail
echo "WARNING: run_all.sh is deprecated; see README.md and scripts/run_batch.sh" >&2
exec bash "$(dirname "$0")/scripts/run_grid.sh" "$@"
