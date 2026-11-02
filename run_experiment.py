"""Run one defense config on one or more AgentDojo suites and save raw results.

Example:
    python run_experiment.py --defense llm_sanitizer --suites slack banking

Writes results/<model>/<attack>/<defense>/<suite>.json containing every per-task outcome
(benign utility, utility under attack, attack success) plus token/latency usage.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv

from agentdojo.attacks.attack_registry import load_attack
from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
from agentdojo.logging import OutputLogger
from agentdojo.task_suite.load_suites import get_suite

from ipi_eval import attacks as _register_extra_attacks  # noqa: F401  (registers "casual_note")
from ipi_eval import usage
from ipi_eval.defenses import ALL_DEFENSES, build_pipeline, checker_stats, reset_checker_stats


def _pairs(d: dict) -> list[dict]:
    return [{"user_task": u, "injection_task": i, "value": bool(v)} for (u, i), v in d.items()]


def run_suite(args, suite_name: str) -> None:
    out = Path(args.results) / args.model / args.attack / args.defense / f"{suite_name}.json"
    if out.exists() and not args.overwrite:
        print(f"[skip] {out} exists (use --overwrite to redo)")
        return

    suite = get_suite(args.benchmark_version, suite_name)
    user_tasks = list(suite.user_tasks.keys())
    if args.max_user_tasks:
        user_tasks = user_tasks[: args.max_user_tasks]
    injection_tasks = list(suite.injection_tasks.keys())
    if args.max_injection_tasks:
        injection_tasks = injection_tasks[: args.max_injection_tasks]

    pipeline = build_pipeline(args.model, args.defense, args.checker_model)
    logdir = Path(args.logdir) / args.model / args.attack / args.defense
    usage.reset()
    reset_checker_stats()
    record: dict = {
        "model": args.model,
        "checker_model": args.checker_model or args.model,
        "seed": args.seed,
        "defense": args.defense,
        "suite": suite_name,
        "benchmark_version": args.benchmark_version,
        "attack": args.attack,
        "n_user_tasks": len(user_tasks),
        "n_injection_tasks": len(injection_tasks),
    }

    with OutputLogger(str(logdir)):
        # Phase 1: no attack -> benign utility (BU) and false-positive rate of checks.
        tok = usage.current_phase.set("benign")
        t0 = time.perf_counter()
        benign = benchmark_suite_without_injections(
            pipeline, suite, logdir=logdir, force_rerun=not args.resume,
            user_tasks=user_tasks, benchmark_version=args.benchmark_version,
        )
        record["benign_seconds"] = time.perf_counter() - t0
        usage.current_phase.reset(tok)

        # Phase 2: under attack -> utility under attack (UA) and attack success rate (ASR).
        tok = usage.current_phase.set("attack")
        t0 = time.perf_counter()
        attack = load_attack(args.attack, suite, pipeline)
        attacked = benchmark_suite_with_injections(
            pipeline, suite, attack, logdir=logdir, force_rerun=not args.resume,
            user_tasks=user_tasks, injection_tasks=injection_tasks,
            verbose=False, benchmark_version=args.benchmark_version,
        )
        record["attack_seconds"] = time.perf_counter() - t0
        usage.current_phase.reset(tok)

    record["benign_utility"] = _pairs(benign["utility_results"])
    record["attack_utility"] = _pairs(attacked["utility_results"])
    # In AgentDojo, security_results == True means the injection task SUCCEEDED.
    record["attack_success"] = _pairs(attacked["security_results"])
    record["injection_tasks_solvable"] = {k: bool(v) for k, v in attacked["injection_tasks_utility_results"].items()}
    record.update(usage.snapshot())
    record["allowance_usd"] = round(sum(s.get("allowance_usd", 0.0) for s in record["usage"].values()), 6)
    record["cost_usd"] = round(sum(s.get("cost_usd", 0.0) for s in record["usage"].values()), 6)
    record["checker_errors"] = checker_stats()
    record["cost_is_partial"] = bool(args.resume)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2))

    bu = sum(r["value"] for r in record["benign_utility"]) / max(1, len(record["benign_utility"]))
    ua = sum(r["value"] for r in record["attack_utility"]) / max(1, len(record["attack_utility"]))
    asr = sum(r["value"] for r in record["attack_success"]) / max(1, len(record["attack_success"]))
    print(f"[done] {args.defense} / {suite_name}: BU={bu:.1%}  UA={ua:.1%}  ASR={asr:.1%}"
          f"  allow=${record['allowance_usd']:.4f}  -> {out}")


def main() -> None:
    # Load .env before argparse: the --model/--checker-model defaults read the environment.
    if not load_dotenv(".env"):
        warnings.warn("No .env file found; OPENAI_API_KEY must be set in the environment.")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--defense", required=True, choices=ALL_DEFENSES)
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18"))
    p.add_argument("--checker-model", default=os.getenv("CHECKER_MODEL") or None,
                   help="Model for llm_detector/llm_sanitizer (default: same as --model; "
                        "falls back to the CHECKER_MODEL env var)")
    p.add_argument("--seed", type=int, default=None,
                   help="Sampling seed (best effort). Sent with every completion request and "
                        "recorded in the result, so multi-seed replications are distinguishable.")
    p.add_argument("--suites", nargs="+", default=["slack", "banking"])
    p.add_argument("--attack", default="important_instructions",
                   help="important_instructions (main) or casual_note (generalization test)")
    p.add_argument("--benchmark-version", default="v1.2.2")
    p.add_argument("--max-user-tasks", type=int, default=0, help="Limit user tasks per suite (0 = all). For smoke tests.")
    p.add_argument("--max-injection-tasks", type=int, default=0, help="Limit injection tasks per suite (0 = all).")
    p.add_argument("--results", default="results")
    p.add_argument("--logdir", default="runs")
    p.add_argument("--resume", action="store_true", help="Reuse cached task logs (cost numbers become partial).")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        try:
            import numpy as np

            np.random.seed(args.seed)
        except ImportError:
            pass
        usage.set_request_seed(args.seed)

    for s in args.suites:
        run_suite(args, s)


if __name__ == "__main__":
    main()
