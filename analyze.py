"""Aggregate results/ into the paper's tables and figures.

    python analyze.py                # reads results/, writes paper_outputs/

Outputs:
    paper_outputs/<attack>/main_table.md / .csv     pooled over suites (main results table)
    paper_outputs/<attack>/per_suite_table.md / .csv
    paper_outputs/<attack>/fig_tradeoff.png         ASR vs utility under attack, 95% CIs
    paper_outputs/<attack>/fig_cost.png             tokens and latency per task
    paper_outputs/<attack>/summary.json             everything above, machine-readable
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ORDER = ["none", "spotlighting_with_delimiting", "repeat_user_prompt", "regex_detector",
         "transformers_pi_detector", "llm_detector", "llm_sanitizer"]
LABEL = {
    "none": "No defense",
    "spotlighting_with_delimiting": "Spotlighting (delimiters)",
    "repeat_user_prompt": "Repeat user prompt",
    "regex_detector": "Regex detector",
    "transformers_pi_detector": "DeBERTa classifier",
    "transformers_line_filter": "DeBERTa line filter",
    "llm_detector": "LLM detector",
    "llm_sanitizer": "LLM sanitizer",
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pair counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def load(results_dir: Path):
    data = defaultdict(lambda: defaultdict(dict))  # attack -> defense -> suite -> record
    model = None
    for f in sorted(results_dir.glob("*/*/*/*.json")):
        r = json.loads(f.read_text())
        data[r["attack"]][r["defense"]][r["suite"]] = r
        model = r["model"]
    return data, model


def tokens(rec: dict, phase: str, component: str | None = None) -> int:
    total = 0
    for key, s in rec.get("usage", {}).items():
        ph, comp = key.split("/")
        if ph == phase and (component is None or comp == component):
            total += s["prompt_tokens"] + s["completion_tokens"]
    return total


def summarize(recs: list[dict]) -> dict:
    def outcomes(field):
        return {(r["suite"], x["user_task"], x["injection_task"]): x["value"] for r in recs for x in r[field]}

    bu, ua, asr = outcomes("benign_utility"), outcomes("attack_utility"), outcomes("attack_success")
    n_benign = len(bu)
    det_b = defaultdict(int)
    for r in recs:
        for k, v in r.get("detections", {}).get("benign", {}).items():
            det_b[k] += v
    benign_tokens = sum(tokens(r, "benign") for r in recs)
    checker_tokens = sum(tokens(r, "benign", "checker") for r in recs)
    benign_secs = sum(r["benign_seconds"] for r in recs)
    allowance = sum(
        s.get("allowance_usd", 0.0)
        for r in recs
        for key, s in r.get("usage", {}).items()
        if key.startswith("benign/")
    )
    # Go plans report allowance_usd; plain OpenAI-compatible APIs report cost_usd
    # (estimated locally from tokens). Adding them covers both without double counting.
    spend = sum(
        s.get("allowance_usd", 0.0) + s.get("cost_usd", 0.0)
        for r in recs
        for key, s in r.get("usage", {}).items()
        if key.startswith("benign/")
    )
    out = {
        "BU": wilson(sum(bu.values()), len(bu)), "n_BU": len(bu),
        "UA": wilson(sum(ua.values()), len(ua)), "n_UA": len(ua),
        "ASR": wilson(sum(asr.values()), len(asr)), "n_ASR": len(asr),
        "tokens_per_task": benign_tokens / n_benign if n_benign else float("nan"),
        "checker_tokens_per_task": checker_tokens / n_benign if n_benign else float("nan"),
        "seconds_per_task": benign_secs / n_benign if n_benign else float("nan"),
        "allowance_usd_per_task": allowance / n_benign if n_benign else float("nan"),
        "usd_per_task": spend / n_benign if n_benign else float("nan"),
        "benign_flag_rate": (det_b["flagged"] / det_b["checked"]) if det_b.get("checked") else None,
        "benign_outputs_checked": det_b.get("checked", 0),
        "cost_is_partial": any(r.get("cost_is_partial") for r in recs),
        "_asr_outcomes": asr, "_ua_outcomes": ua,
    }
    return out


def pct(t):
    p, lo, hi = t
    return "–" if math.isnan(p) else f"{100*p:.1f} [{100*lo:.1f}, {100*hi:.1f}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="paper_outputs")
    a = ap.parse_args()
    all_data, model = load(Path(a.results))
    if not all_data:
        raise SystemExit("No results found. Run run_experiment.py first.")
    for attack_name, data in all_data.items():
        out = Path(a.out) / attack_name
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n=== attack: {attack_name} ===")
        report(data, model, out)


def report(data, model, out: Path) -> None:
    defenses = [d for d in ORDER if d in data] + [d for d in data if d not in ORDER]
    suites = sorted({s for d in data.values() for s in d})

    pooled = {d: summarize(list(data[d].values())) for d in defenses}
    base = pooled.get("none")
    base_tok = base["tokens_per_task"] if base else None

    # Paired significance vs. no defense (same user/injection task pairs).
    for d in defenses:
        s = pooled[d]
        s["p_ASR_vs_none"] = s["p_UA_vs_none"] = None
        if base and d != "none":
            for metric, key in (("ASR", "_asr_outcomes"), ("UA", "_ua_outcomes")):
                common = set(base[key]) & set(s[key])
                b = sum(1 for k in common if base[key][k] and not s[key][k])
                c = sum(1 for k in common if not base[key][k] and s[key][k])
                s[f"p_{metric}_vs_none"] = mcnemar_exact(b, c)

    # ---- main table
    header = ["Defense", "BU % [95% CI]", "UA % [95% CI]", "ASR % [95% CI]", "p (ASR vs none)",
              "Benign flag rate %", "Tokens / task", "USD / task", "Overhead vs none %", "Seconds / task"]
    rows = []
    for d in defenses:
        s = pooled[d]
        over = (100 * (s["tokens_per_task"] / base_tok - 1)) if base_tok else float("nan")
        rows.append([
            LABEL.get(d, d), pct(s["BU"]), pct(s["UA"]), pct(s["ASR"]),
            "–" if s["p_ASR_vs_none"] is None else f"{s['p_ASR_vs_none']:.3g}",
            "–" if s["benign_flag_rate"] is None else f"{100*s['benign_flag_rate']:.1f}",
            f"{s['tokens_per_task']:.0f}", f"{s['usd_per_task']:.4f}",
            "–" if d == "none" else f"{over:+.0f}",
            f"{s['seconds_per_task']:.1f}",
        ])
    _write_table(out / "main_table", header, rows)

    # ---- per-suite table
    header2 = ["Suite", "Defense", "BU %", "UA %", "ASR %", "n (attack pairs)"]
    rows2 = []
    for su in suites:
        for d in defenses:
            if su in data[d]:
                s = summarize([data[d][su]])
                rows2.append([su, LABEL.get(d, d), f"{100*s['BU'][0]:.1f}", f"{100*s['UA'][0]:.1f}",
                              f"{100*s['ASR'][0]:.1f}", s["n_ASR"]])
    _write_table(out / "per_suite_table", header2, rows2)

    clean = {d: {k: v for k, v in s.items() if not k.startswith("_")} for d, s in pooled.items()}
    (out / "summary.json").write_text(json.dumps({"model": model, "suites": suites, "pooled": clean}, indent=2))
    _figures(out, defenses, pooled)
    print((out / "main_table.md").read_text())
    if any(s["cost_is_partial"] for s in pooled.values()):
        print("WARNING: some runs used --resume, so token/latency numbers are partial.")


def _write_table(stem: Path, header, rows) -> None:
    with open(stem.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    stem.with_suffix(".md").write_text("\n".join(md) + "\n")


def _figures(out: Path, defenses, pooled) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping figures")
        return
    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for i, d in enumerate(defenses):
        s = pooled[d]
        x, xl, xh = s["UA"]
        y, yl, yh = s["ASR"]
        ax.errorbar(100 * x, 100 * y, xerr=[[100 * (x - xl)], [100 * (xh - x)]],
                    yerr=[[100 * (y - yl)], [100 * (yh - y)]], fmt="o", ms=7, capsize=3,
                    color=cmap(i), label=LABEL.get(d, d))
    ax.set_xlabel("Utility under attack (%)  →  better")
    ax.set_ylabel("Attack success rate (%)  ↓  better")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    ax.set_title("Security–utility trade-off (95% Wilson CIs)")
    fig.tight_layout()
    fig.savefig(out / "fig_tradeoff.png", dpi=200)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    names = [LABEL.get(d, d) for d in defenses]
    agent = [pooled[d]["tokens_per_task"] - pooled[d]["checker_tokens_per_task"] for d in defenses]
    check = [pooled[d]["checker_tokens_per_task"] for d in defenses]
    axes[0].barh(names, agent, color="#4C72B0", label="Agent")
    axes[0].barh(names, check, left=agent, color="#DD8452", label="Checker")
    axes[0].set_xlabel("Tokens per task (no attack)")
    axes[0].legend(fontsize=8)
    axes[0].invert_yaxis()
    axes[1].barh(names, [pooled[d]["seconds_per_task"] for d in defenses], color="#55A868")
    axes[1].set_xlabel("Seconds per task (no attack)")
    axes[1].invert_yaxis()
    axes[1].set_yticklabels([])
    fig.tight_layout()
    fig.savefig(out / "fig_cost.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
