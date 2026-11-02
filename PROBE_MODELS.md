# Model screening (not part of the reported grid)

Before spending credits on the full grid we screened candidate models for a basic
precondition: the standard AgentDojo attack must actually succeed often enough to measure
a defense. All probes use defence `none`, the same prompt and the same benchmark; cost is
the total recorded for the probe.

| Model | Attack | Pairs | ASR | Cost | Note |
|---|---|---|---|---|---|
| `gpt-4o-mini-2024-07-18` | `important_instructions` | 105 (slack) | **62.9%** | $0.14 | chosen: signal + comparable to published AgentDojo baselines |
| `beam-free` | `important_instructions` | 105 (slack) | **44.8%** | $0.00 | works, but the free tier rate-limits after ~50 runs (HTTP 429) and is "limited time/regions" — cannot carry a 3,400-run grid |
| `glm-5.3-flash` | `important_instructions` | 249 (both suites) | **2.0%** | $0.17 | floor effect |
| `glm-5.3-flash` | `injecagent` | 249 (both suites) | **0.4%** | $0.15 | a stronger attack does not help |
| `minimax-m3` | `important_instructions` | 105 (slack) | **1.9%** | $0.91 | floor effect, 11× the cost of `glm-5.3-flash` |
| `mimo-v2.6-flash` | `important_instructions` | 105 (slack) | **1.0%** | $0.08 | floor effect |
| `deepseek-v4.1-flash` | `important_instructions` | 105 (slack) | **0.0%** | $0.10 | floor effect |

Also checked for availability and tool calling on the OpenCode Go gateway (not run): 8 free
model ids were unreachable from an external client (`Model is unavailable`, or
`FreeUsageLimitError`); `minimax-m3.1-flash`, `mimo-v2.6-flash`, `qwen3.8-flash`,
`longcat-2.0`, `hy4-preview`, `step-5-preview`, `grok-4.7` and `glm-5.3` all answered a
tool-call request. `qwen3.8-flash` later failed inside the harness with a 400
`invalid_parameter_error`; the rest were not probed further once `gpt-4o-mini` was
available.

## Why this matters for the paper

With a 2% baseline, the paired design is underpowered: even a defense that removed *every*
baseline success would only produce 5 discordant pairs, giving an exact McNemar
p = 0.0625 — it could not reach p < 0.05. Six or more baseline successes are needed for a
perfect defense to become significant. This is why the model choice is a design constraint,
not a convenience, and why the screening is worth one paragraph in the paper's setup or in
the discussion: current open-weight models resist the standard attack strongly enough to
make security–utility trade-off studies meaningless unless a susceptible model is chosen.

Raw probe results are in `results_probe*` and can be shipped with `results/` (they are
small, ≈380 KB in total).
