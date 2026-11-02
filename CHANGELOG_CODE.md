# Code changelog

Every change made to the original drop of `ipi-tool-output-checks`, why it was needed, and
the evidence that it mattered. Read this before comparing against any earlier output of
this repository: two of the fixes below change results qualitatively.

A pristine copy of the original tree is at
`/tmp/opencode/ipi-tool-output-checks-backup-082511.tar.gz` (may be gone after a `/tmp`
cleanup; the files listed here are the complete delta).

---

## A. Correctness fixes that change results

### A1. `llm_detector` was silently a no-op (fail-open)

`ipi_eval/defenses.py`, `LLMInjectionDetector.detect` + `_LLMChecker.ask`.

The detector asked the checker for `max_tokens=5`. With any reasoning model (and, in
general, any model that emits hidden reasoning tokens first), those 5 tokens are consumed
before any visible text is produced, so the response is:

```
content=None, finish_reason="length", completion_tokens=5, reasoning_tokens=5
```

The old code then did `"INJECTION" in (content or "").upper()` → `False` → **every tool
output was classified as CLEAN**. The defense would have appeared to do nothing.

Evidence (measured on GLM-5.3-Flash; the same failure mode applies to any reasoning model):

| max_tokens | content | finish_reason |
|---|---|---|
| 5 | `None` | `length` |
| 32 | `INJECTION` | `stop` |
| 128 | `INJECTION` | `stop` |

Fix: `max_tokens=64`, the budget is escalated ×4 (capped at `max(max_tokens, 512)`) when
`finish_reason == "length"` or the content is empty, and a missing answer is treated as
**injection** (fail closed). Truncation/empty/API failures are counted in `checker_stats()`
and written to every result JSON under `checker_errors`.

### A2. `LLMOutputSanitizer` reported a wrong false-positive rate

When the checker failed, the output was replaced by
`<Tool output withheld: the safety filter was unavailable>` but `record_detection(flagged=False)`
was still called, so a blocked output counted as "not flagged". Now `withheld` is folded
into the flag counter. The sanitizer budget was also raised from 4096 to 8192 tokens, since
a rewrite can be as long as the original output.

### A3. Cost was never recorded for OpenAI

`ipi_eval/usage.py`. The gateway-style `usage.cost` field does not exist on OpenAI
responses, so the paper's cost axis was always zero. Added `estimate_cost()` with a price
table (`gpt-4o-mini` 0.15/0.60, `gpt-4o` 2.50/10.00 USD per Mtok) and kept the real
`cost` / `opencode.allowance` values when a gateway provides them. Verified: a 9-input /
2-output-token call records `$2.55e-6`.

## B. Portability fixes

### B1. Hard-coded OpenAI client

`build_pipeline` used `openai.OpenAI()`, which cannot talk to an OpenAI-compatible gateway.
Added `_make_client()` reading `OPENAI_BASE_URL`, a custom `User-Agent`, and — only for the
OpenCode gateway — the required `x-opencode-session` header (without it the gateway returns
HTTP 400 `MissingSessionID`).

### B2. Empty `OPENAI_BASE_URL` broke the client

The OpenAI SDK reads `OPENAI_BASE_URL` from the environment itself. A `.env` line
`OPENAI_BASE_URL=` set it to `""`, which the SDK accepted and then failed with
`UnsupportedProtocol: Request URL is missing an 'http://' or 'https://' protocol`.
`_make_client()` now substitutes `https://api.openai.com/v1` when the value is empty.

### B3. `important_instructions` refused to run on non-OpenAI models

`agentdojo.attacks.base_attacks.get_model_name_from_pipeline` raises unless the pipeline
name contains a key of `agentdojo.models.MODEL_NAMES`, which only lists the original
paper's models. `ipi_eval/attacks.py` now registers the configured model under its own
name (`glm-5.3-flash → GLM-5.3`, `beam-free → Beam`, generic fallback for anything else),
so the injected text addresses the real model instead of pretending to be GPT-4.

### B4. `load_dotenv` ran after argparse

`run_experiment.py` read `OPENAI_MODEL` for the `--model` default *before* loading `.env`,
so every run silently fell back to `gpt-4o-mini-2024-07-18`. With a non-OpenAI gateway this
produced `400 Model is unavailable` for all 12 configurations. `load_dotenv` now runs first.

### B5. No timeout or retry on the client

A hung gateway request could stall a run for ~30 minutes and a single HTTP 429 aborted a
whole configuration. Added `timeout=OPENAI_TIMEOUT` (default 120 s) and
`max_retries=OPENAI_MAX_RETRIES` (default 8).

## C. New capability

### C1. Seed plumbing

`--seed` seeds `random` and `numpy`, records `seed` in the result, and is injected into
every chat completion via `usage.set_request_seed()`.

### C2. `transformers_line_filter` (ablation)

Same DeBERTa classifier, but each output line is classified separately and only flagged
lines are replaced with `[REMOVED]`. Added to `ALL_DEFENSES` and `build_pipeline`.
Measured effect: UA 29.3 → 53.4, ASR 10.8 → 1.6 on `important_instructions`.

### C3. `checker_errors` in results

`run_experiment.py` writes `checker_errors`, `allowance_usd`, `cost_usd`, `seed`, and
`checker_model` into every result JSON. `analyze.py` gained a `USD / task` column based on
`cost_usd + allowance_usd`.

### C4. `analyze_seeds.py`

Aggregates several single-seed result directories into mean ± sample sd and reports the
McNemar p-value **per seed**. Seeds are independent runs, so they are not pooled into a
single p-value.

### C5. Scripts

- `scripts/run_batch.sh` — environment-configured runner: per-batch `RESULTS_DIR`,
  `LOGDIR`, `TAG`, `SEED`, `CHECKER_MODEL`, defense lists; retries each job up to
  `ATTEMPTS` times with a 90 s pause; finished suites are skipped on rerun.
- `scripts/run_grid.sh` — the original full-grid runner, kept for reference.
- `scripts/finalize.sh` — rebuilds every paper artifact and prints an integrity table.
- `scripts/preflight.py` — checks gateway, tool calling, detector, sanitizer, long-output
  handling and cost accounting before spending money.

## D. Data-hygiene bugs caught during the run

- The ablation batch was once started without `RESULTS_DIR`, so four files landed in the
  seed-1 directory. They were moved to `results/ablation/` and `results/` was verified back
  at 24 files. Always pass `RESULTS_DIR` and `TAG` explicitly.
- The `gpt-4o` checker batch was run before `gpt-4o` existed in the price table, so its
  recorded `cost_usd` is $0.60 instead of the true ≈$3.95. The corrected figure is
  computed from the logged token counts; the price table now includes `gpt-4o`.

## E. Verification performed

| Check | Result |
|---|---|
| `python -m py_compile` on all modules | pass |
| Preflight vs OpenAI (`gpt-4o-mini`) | 8/8 pass |
| Preflight vs OpenCode Go (`glm-5.3-flash`, `beam-free`) | 8/8 pass |
| DeBERTa loads under transformers 5.22.1 | pass (24 s, correct labels) |
| 24/24 result files, `checker_errors` empty | pass |
| `cost_is_partial` false everywhere | pass |
| Multi-seed aggregate reproduces single-run numbers | pass |
