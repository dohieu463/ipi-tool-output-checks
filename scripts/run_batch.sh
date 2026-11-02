#!/usr/bin/env bash
# Resilient batch runner. All configuration comes from the environment so several batches
# can run at once without clobbering each other's logs or results.
#
#   RESULTS_DIR=results/seed-2 LOGDIR=runs/seed-2 TAG=seed2 SEED=2 \
#     ATTACKS="important_instructions" MAX_PARALLEL=2 bash scripts/run_batch.sh
#
#   TAG=ablation RESULTS_DIR=results/ablation MAIN_DEFENSES="transformers_line_filter" \
#     GEN_DEFENSES="transformers_line_filter" bash scripts/run_batch.sh
#
#   TAG=checker RESULTS_DIR=results/checker-gpt4o CHECKER_MODEL=gpt-4o \
#     MAIN_DEFENSES="llm_detector llm_sanitizer" ATTACKS="important_instructions" \
#     MAX_PARALLEL=1 bash scripts/run_batch.sh
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

RESULTS_DIR="${RESULTS_DIR:-results}"
LOGDIR="${LOGDIR:-runs}"
TAG="${TAG:-batch}"
SEED="${SEED:-}"
CHECKER_MODEL="${CHECKER_MODEL:-}"
MAX_PARALLEL="${MAX_PARALLEL:-2}"
ATTEMPTS="${ATTEMPTS:-4}"
EXTRA="${EXTRA:-}"
ATTACKS="${ATTACKS:-important_instructions casual_note}"
MAIN_DEFENSES="${MAIN_DEFENSES:-none spotlighting_with_delimiting repeat_user_prompt regex_detector transformers_pi_detector llm_detector llm_sanitizer}"
GEN_DEFENSES="${GEN_DEFENSES:-none regex_detector transformers_pi_detector llm_detector llm_sanitizer}"

SEED_ARG=""
[[ -n "$SEED" ]] && SEED_ARG="--seed $SEED"
CHECKER_ARG=""
[[ -n "$CHECKER_MODEL" ]] && CHECKER_ARG="--checker-model $CHECKER_MODEL"

mkdir -p logs
JOBS=()
for attack in $ATTACKS; do
  if [[ "$attack" == "important_instructions" ]]; then
    for d in $MAIN_DEFENSES; do JOBS+=("$attack $d"); done
  else
    for d in $GEN_DEFENSES; do JOBS+=("$attack $d"); done
  fi
done

run_job() {
  local attack="$1" defense="$2" attempt
  local log="logs/${TAG}_${attack}_${defense}.log"
  for attempt in $(seq 1 "$ATTEMPTS"); do
    {
      echo "=== $(date -Is) attempt $attempt | $attack / $defense"
      echo "    results=$RESULTS_DIR logdir=$LOGDIR seed=${SEED:-none} checker=${CHECKER_MODEL:-$OPENAI_MODEL}"
    } >> "$log"
    # shellcheck disable=SC2086
    if python run_experiment.py --defense "$defense" --attack "$attack" \
        --results "$RESULTS_DIR" --logdir "$LOGDIR" $SEED_ARG $CHECKER_ARG $EXTRA >> "$log" 2>&1; then
      echo "[ok] $(date -Is) $attack / $defense" | tee -a "$log"
      return 0
    fi
    echo "[retry] $(date -Is) $attack / $defense failed; sleeping 90s" | tee -a "$log"
    sleep 90
  done
  echo "[FAIL] $(date -Is) $attack / $defense after $ATTEMPTS attempts" | tee -a "$log"
  return 1
}
export -f run_job
export ATTEMPTS RESULTS_DIR LOGDIR SEED_ARG CHECKER_ARG EXTRA

printf '%s\n' "${JOBS[@]}" | xargs -P "$MAX_PARALLEL" -L 1 bash -c 'run_job $0 $1'
exit $?
