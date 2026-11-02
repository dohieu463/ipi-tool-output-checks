#!/usr/bin/env bash
# Full-grid runner, kept for reference. Prefer scripts/run_batch.sh: it takes the same
# environment variables but writes per-batch log names and is what produced results/.
#
#   bash scripts/run_grid.sh            # 12 configs, 3 in parallel
#   MAX_PARALLEL=2 bash scripts/run_grid.sh
#   bash scripts/run_grid.sh smoke      # tiny end-to-end check
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

MODE="${1:-full}"
MAX_PARALLEL="${MAX_PARALLEL:-3}"
ATTEMPTS="${ATTEMPTS:-4}"
mkdir -p logs

if [[ "$MODE" == "smoke" ]]; then
  EXTRA="--max-user-tasks 2 --max-injection-tasks 1 --results results_smoke --logdir runs_smoke --overwrite"
else
  EXTRA=""
fi
MAIN="none spotlighting_with_delimiting repeat_user_prompt regex_detector transformers_pi_detector llm_detector llm_sanitizer"
GEN="none regex_detector transformers_pi_detector llm_detector llm_sanitizer"

JOBS=()
for d in $MAIN; do JOBS+=("important_instructions $d"); done
for d in $GEN;  do JOBS+=("casual_note $d"); done

run_job() {
  local attack="$1" defense="$2" attempt
  local log="logs/grid_${attack}_${defense}.log"
  for attempt in $(seq 1 "$ATTEMPTS"); do
    echo "=== $(date -Is) attempt $attempt: $attack / $defense" >> "$log"
    # shellcheck disable=SC2086
    if python run_experiment.py --defense "$defense" --attack "$attack" $EXTRA >> "$log" 2>&1; then
      echo "[ok] $(date -Is) $attack / $defense" | tee -a "$log"
      return 0
    fi
    echo "[retry] $(date -Is) $attack / $defense failed; sleeping 90s" | tee -a "$log"
    sleep 90
  done
  echo "[FAIL] $(date -Is) $attack / $defense" | tee -a "$log"
  return 1
}
export -f run_job
export ATTEMPTS EXTRA

printf '%s\n' "${JOBS[@]}" | xargs -P "$MAX_PARALLEL" -L 1 bash -c 'run_job $0 $1'
status=$?

if [[ "$MODE" == "smoke" ]]; then
  python analyze.py --results results_smoke --out paper_outputs_smoke
else
  python analyze.py
fi
exit "$status"
