#!/usr/bin/env bash
# Rebuild every paper artifact from the clean, seeded results, then print an integrity table.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source .venv/bin/activate

echo "== 1/3 multi-seed aggregate (3 explicit seeds)"
python analyze_seeds.py results/seed-1 results/seed-2 results/seed-3 --out paper_outputs_seeds

echo "== 2/3 single-run tables/figures (seed 1)"
python analyze.py --results results/seed-1 --out paper_outputs

echo "== 3/3 ablation tables/figures"
python analyze.py --results results/ablation --out paper_outputs_ablation

echo "== integrity summary"
python - <<'PY'
import glob, json
rows = []
for d in ("results/seed-1", "results/seed-2", "results/seed-3", "results/ablation", "results/checker-gpt4o"):
    fs = glob.glob(f"{d}/*/*/*/*.json")
    spend = sum(json.load(open(f)).get("cost_usd", 0) or 0 for f in fs)
    faults = sum(
        1 for f in fs
        if (lambda r: (r.get("checker_errors") or {}).get("unavailable")
            or (r.get("checker_errors") or {}).get("api_error"))(json.load(open(f)))
    )
    partial = sum(1 for f in fs if json.load(open(f)).get("cost_is_partial"))
    rows.append((d, len(fs), faults, partial, spend))
print(f"{'dir':24} {'files':>6} {'checker_fail':>13} {'partial':>8} {'usd':>8}")
for d, n, faults, partial, spend in rows:
    print(f"{d:24} {n:>6} {faults:>13} {partial:>8} {spend:>8.2f}")
PY
