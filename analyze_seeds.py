"""Aggregate several single-seed result directories into mean +- sd tables.

    python analyze_seeds.py results results/seed-2 results/seed-3 --out paper_outputs_seeds

Each directory is one replication (one sampling seed). Per defense we report the mean and
the sample standard deviation across seeds, plus the McNemar p-value of every seed against
that seed's own undefended baseline. We deliberately do not merge seeds into a single
p-value: seeds are independent runs, so a per-seed test is the honest unit of inference.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

ORDER = ["none", "spotlighting_with_delimiting", "repeat_user_prompt", "regex_detector",
         "transformers_pi_detector", "transformers_line_filter", "llm_detector", "llm_sanitizer"]
LABEL = {
    "none": "No defense",
    "spotlighting_with_delimiting": "Spotlighting (delimiters)",
    "repeat_user_prompt": "Repeat user prompt",
    "regex_detector": "Regex detector",
    "transformers_pi_detector": "DeBERTa (block output)",
    "transformers_line_filter": "DeBERTa (drop flagged lines)",
    "llm_detector": "LLM detector",
    "llm_sanitizer": "LLM sanitizer",
}


def load(root: Path):
    data: dict[str, dict[str, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    for f in sorted(root.glob("*/*/*/*.json")):
        r = json.loads(f.read_text())
        data[r["attack"]][r["defense"]][r["suite"]] = r
    return data


def outcomes(recs, field):
    return {(r["suite"], x["user_task"], x["injection_task"]): x["value"]
            for r in recs for x in r[field]}


def detection_counters(recs, phase):
    checked = flagged = 0
    for r in recs:
        d = r.get("detections", {}).get(phase, {})
        checked += d.get("checked", 0)
        flagged += d.get("flagged", 0)
    return checked, flagged


def spend(recs):
    """USD spent in the benign (no-attack) phase, matching the paper's cost definition."""
    total = 0.0
    for r in recs:
        for key, s in r.get("usage", {}).items():
            if not key.startswith("benign/"):
                continue
            total += (s.get("cost_usd", 0.0) or 0.0) + (s.get("allowance_usd", 0.0) or 0.0)
    return total


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def seed_stats(recs):
    bu, ua, asr = outcomes(recs, "benign_utility"), outcomes(recs, "attack_utility"), outcomes(recs, "attack_success")
    checked, flagged = detection_counters(recs, "benign")
    n_benign = len(bu)
    return {
        "bu": sum(bu.values()), "n_bu": len(bu),
        "ua": sum(ua.values()), "n_ua": len(ua),
        "asr": sum(asr.values()), "n_asr": len(asr),
        "fpr": (flagged / checked) if checked else None,
        "usd_per_task": (spend(recs) / n_benign) if n_benign else float("nan"),
        "_asr": asr, "_ua": ua,
    }


def mean_sd(values):
    values = [v for v in values if v is not None]
    if not values:
        return None, None
    m = sum(values) / len(values)
    if len(values) == 1:
        return m, None
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return m, math.sqrt(var)


def fmt(mean, sd, pct=True):
    if mean is None:
        return "–"
    scale = 100 if pct else 1
    digits = 1 if pct else 5
    if sd is not None:
        return f"{scale*mean:.{digits}f} ± {scale*sd:.{digits}f}"
    return f"{scale*mean:.{digits}f}"


def report(seed_dirs, out: Path) -> None:
    loaded = [(d, load(d)) for d in seed_dirs]
    attacks = sorted({a for _, data in loaded for a in data})
    summary: dict = {}

    lines = ["# Multi-seed summary", "",
             f"Seeds: {', '.join(str(d) for d in seed_dirs)}", ""]
    for attack in attacks:
        lines += [f"## {attack}", "",
                  "| Defense | BU % (mean ± sd) | UA % | ASR % | p vs none (per seed) | Benign flag rate % | USD / task |",
                  "|---|---|---|---|---|---|---|"]
        per_defense = {}
        for defense in [d for d in ORDER if any(defense_in(data, attack, d) for _, data in loaded)]:
            stats = []
            ps = []
            for _, data in loaded:
                if not defense_in(data, attack, defense):
                    continue
                recs = list(data[attack][defense].values())
                st = seed_stats(recs)
                stats.append(st)
                if defense != "none" and defense_in(data, attack, "none"):
                    base = seed_stats(list(data[attack]["none"].values()))
                    common = set(base["_asr"]) & set(st["_asr"])
                    b = sum(1 for k in common if base["_asr"][k] and not st["_asr"][k])
                    c = sum(1 for k in common if not base["_asr"][k] and st["_asr"][k])
                    ps.append(mcnemar_exact(b, c))
            bu_m, bu_sd = mean_sd([s["bu"] / s["n_bu"] for s in stats if s["n_bu"]])
            ua_m, ua_sd = mean_sd([s["ua"] / s["n_ua"] for s in stats if s["n_ua"]])
            asr_m, asr_sd = mean_sd([s["asr"] / s["n_asr"] for s in stats if s["n_asr"]])
            fpr_m, fpr_sd = mean_sd([s["fpr"] for s in stats])
            usd_m, usd_sd = mean_sd([s["usd_per_task"] for s in stats])
            p_txt = "–" if not ps else " / ".join(f"{p:.2g}" for p in ps)
            lines.append(
                f"| {LABEL.get(defense, defense)} | {fmt(bu_m, bu_sd)} | {fmt(ua_m, ua_sd)} | "
                f"{fmt(asr_m, asr_sd)} | {p_txt} | {fmt(fpr_m, fpr_sd)} | {fmt(usd_m, usd_sd, pct=False)} |"
            )
            per_defense[defense] = {
                "bu": [bu_m, bu_sd], "ua": [ua_m, ua_sd], "asr": [asr_m, asr_sd],
                "fpr": [fpr_m, fpr_sd], "usd_per_task": [usd_m, usd_sd], "p_vs_none": ps,
                "n_seeds": len(stats),
            }
        lines.append("")
        summary[attack] = per_defense

    out.mkdir(parents=True, exist_ok=True)
    (out / "multiseed_table.md").write_text("\n".join(lines) + "\n")
    (out / "multiseed_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n".join(lines))


def defense_in(data, attack, defense) -> bool:
    return attack in data and defense in data[attack] and bool(data[attack][defense])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", help="one directory per seed, e.g. results results/seed-2")
    ap.add_argument("--out", default="paper_outputs_seeds")
    args = ap.parse_args()
    dirs = [Path(p) for p in args.results if Path(p).exists()]
    missing = [p for p in args.results if not Path(p).exists()]
    if missing:
        print("skipping missing directories:", missing)
    if not dirs:
        raise SystemExit("no result directories found")
    report(dirs, Path(args.out))


if __name__ == "__main__":
    main()
