# Manifest — what is here and what to ship

Study: *Checking Tool Outputs Against Indirect Prompt Injection: An Empirical Study of the
Security–Utility–Cost Trade-off in LLM Agents*.
Status: **complete**. Experiments ran 2026-11-01 → 2026-11-02.

## Ship these two archives

| File | Size | Contents |
|---|---|---|
| `ship/paper_outputs.tar.gz` | 441 KB | tables, figures, summaries + docs + scripts |
| `ship/results.tar.gz` | 110 KB | raw per-configuration results for every batch |
| `ship/SHA256SUMS` | 168 B | checksums of both archives |

Plus the hand-off document at the repository root: `METHODS_AND_RESULTS.md`.

Do **not** ship `runs/` (161 MB of full conversation logs) — but keep it: it is the
evidence trail if a reviewer asks "what exactly did the agent see". It can be re-shipped
on request.

## What each result directory is

| Directory | Files | What it is | Used in the paper |
|---|---|---|---|
| `results/` | 24 | pilot run, **no explicit seed** | no — kept for the ablation baseline and for the reproducibility note |
| `results/seed-1/` | 24 | full grid, `--seed 1` (both attacks) | yes — single-run tables and figures |
| `results/seed-2/` | 14 | `important_instructions`, `--seed 2` | yes — 3-seed aggregate |
| `results/seed-3/` | 14 | `important_instructions`, `--seed 3` | yes — 3-seed aggregate |
| `results/ablation/` | 12 | DeBERTa line-filter ablation + copied baseline rows | yes — §5 of the report |
| `results/checker-gpt4o/` | 4 | `gpt-4o` checker control | yes — §6 of the report |
| `results_probe*/` | 7 dirs | model/attack screening | yes — §8 (discussion), see `PROBE_MODELS.md` |

Each JSON holds every per-task outcome, the token/latency/allowance accounting split by
phase and component, detection counters, `checker_errors`, `seed`, and `checker_model`.

## Paper artifacts

| Path | Contents |
|---|---|
| `paper_outputs/<attack>/main_table.md/.csv` | pooled table with Wilson 95% CI and McNemar p |
| `paper_outputs/<attack>/per_suite_table.md/.csv` | per-suite breakdown |
| `paper_outputs/<attack>/summary.json` | machine-readable version of the above |
| `paper_outputs/<attack>/fig_tradeoff.png` | UA vs ASR with CIs |
| `paper_outputs/<attack>/fig_cost.png` | tokens and latency per task |
| `paper_outputs_seeds/multiseed_table.md` | **mean ± sd across 3 seeds** — use this table in the paper |
| `paper_outputs_seeds/multiseed_summary.json` | machine-readable multi-seed version |
| `paper_outputs_ablation/<attack>/…` | ablation tables and figures |

## Documents

| File | Purpose |
|---|---|
| `README.md` | setup, configurations, how to run, metrics, reproducibility notes |
| `METHODS_AND_RESULTS.md` | paper-ready methods, every result table, findings, threats to validity |
| `CHANGELOG_CODE.md` | every code change vs the original drop, with evidence |
| `PROBE_MODELS.md` | model screening that motivated `gpt-4o-mini`; supports §8 of the report |
| `MANIFEST.md` | this file |

## Code

| File | Role |
|---|---|
| `ipi_eval/defenses.py` | 8 configurations, pipeline builder, checker retry/fail-closed logic |
| `ipi_eval/attacks.py` | `casual_note` attack + model-name registration for AgentDojo |
| `ipi_eval/usage.py` | token, latency, cost/allowance accounting, seed injection |
| `run_experiment.py` | runs one (defense, attack, suite) configuration |
| `analyze.py` | tables and figures for one run |
| `analyze_seeds.py` | mean ± sd across several seeds, per-seed McNemar |
| `scripts/run_batch.sh` | resilient runner used for every reported batch |
| `scripts/run_grid.sh` | original full-grid runner, kept for reference |
| `scripts/finalize.sh` | rebuilds all artifacts and prints an integrity table |
| `scripts/preflight.py` | 8 checks before spending money on a run |

## Provenance

| Item | Value |
|---|---|
| Benchmark | AgentDojo v1.2.2 (`slack`, `banking`) |
| Agent model | `gpt-4o-mini-2024-07-18` |
| Attack pairs per configuration | 249 (slack 105 + banking 144) |
| Runs executed | ≈ 10,300 agent runs across all batches |
| Total OpenAI spend | ≈ **$28.3** (pilot 6.16 + seed-1 7.04 + seed-2 4.43 + seed-3 4.63 + ablation 2.13 + checker 3.95) |
| Wall-clock | ≈ 10 h, 3–4 processes in parallel |
| Python / torch | 3.12.13 / 2.15.0+cpu (no GPU) |

## Integrity checks performed

- 24/24 result files present for every batch; no empty result.
- `checker_errors` empty (`unavailable` = `api_error` = 0) in every file.
- `cost_is_partial` false everywhere.
- Every result records its `seed`; seed-1/2/3 are distinct.
- `scripts/preflight.py` passes 8/8 against the live API.
- Multi-seed aggregate reproduces the single-run numbers of seed-1 within its sd.
- Ablation data was verified to live in `results/ablation/` only (it was once misfiled into
  `results/` and moved back; `results/` has exactly 24 files).

## Known caveats (also in §8 of the report)

1. `cost_usd` is estimated from tokens on OpenAI, not read from a bill; for
   `results/checker-gpt4o/` the stored value understates by ~$3.35 because the price table
   lacked `gpt-4o` at run time. The corrected figure ($3.95) is used in the report.
2. Seeds are OpenAI best-effort; between-run sd is reported instead of claiming determinism.
3. `casual_note` has 2 runs, not 3.
4. The ablation is a single run against the same-day baseline.
5. `regex_detector` is an optimistic bound by construction; see `casual_note`.
