"""Token, latency and cost accounting for every OpenAI call made in one process.

Each experiment config runs in its own process, so a module-level counter is enough.
Counts are split by `component` ("agent" = the agent's own LLM calls, "checker" = calls
made by a defense) and by `phase` ("benign" or "attack"), so the paper can report the
extra cost a defense adds on top of the undefended agent.
"""
from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from contextvars import ContextVar
from pathlib import Path

_lock = threading.Lock()
_stats: dict[str, dict[str, float]] = defaultdict(
    lambda: {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "seconds": 0.0,
        "cost_usd": 0.0,
        "allowance_usd": 0.0,
    }
)
# Which part of the pipeline is calling the API right now.
current_component: ContextVar[str] = ContextVar("current_component", default="agent")
# Which benchmark phase is running (set by the runner).
current_phase: ContextVar[str] = ContextVar("current_phase", default="benign")
# Sampling seed passed to every request when the run is part of a multi-seed replication.
_request_seed: int | None = None


def set_request_seed(seed: int | None) -> None:
    """Pass `seed` to every chat completion (best-effort determinism, provider permitting)."""
    global _request_seed
    _request_seed = seed

# Detection counters for the check-based defenses.
_detect: dict[str, dict[str, int]] = defaultdict(lambda: {"checked": 0, "flagged": 0, "rewritten": 0})


def _key() -> str:
    return f"{current_phase.get()}/{current_component.get()}"


# USD per million tokens (input, output). Keep in sync with the provider's price sheet;
# only used when the API response does not report a cost itself.
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = _PRICE_PER_MTOK.get(model)
    if price is None:
        return 0.0
    p_in, p_out = price
    return (prompt_tokens * p_in + completion_tokens * p_out) / 1_000_000


def record_call(
    prompt_tokens: int,
    completion_tokens: int,
    seconds: float,
    cost_usd: float = 0.0,
    allowance_usd: float = 0.0,
) -> None:
    with _lock:
        s = _stats[_key()]
        s["calls"] += 1
        s["prompt_tokens"] += prompt_tokens
        s["completion_tokens"] += completion_tokens
        s["seconds"] += seconds
        s["cost_usd"] += cost_usd
        s["allowance_usd"] += allowance_usd


def record_detection(flagged: bool, rewritten: bool = False) -> None:
    with _lock:
        d = _detect[current_phase.get()]
        d["checked"] += 1
        d["flagged"] += int(flagged)
        d["rewritten"] += int(rewritten)


def _extra_field(usage, name):
    """Read a non-standard field from an OpenAI usage object (pydantic extra or mapping)."""
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(name)
    try:
        val = getattr(usage, name, None)
    except Exception:
        val = None
    if val is not None:
        return val
    extra = getattr(usage, "model_extra", None)
    try:
        return extra.get(name) if extra is not None else None
    except Exception:
        return None


class _CountingCompletions:
    def __init__(self, inner):
        self._inner = inner

    def create(self, *args, **kwargs):
        if _request_seed is not None and "seed" not in kwargs:
            kwargs = {**kwargs, "seed": _request_seed}
        t0 = time.perf_counter()
        resp = self._inner.create(*args, **kwargs)
        dt = time.perf_counter() - t0
        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        try:
            cost_usd = float(_extra_field(usage, "cost") or 0.0)
        except (TypeError, ValueError):
            cost_usd = 0.0
        if cost_usd == 0.0:
            # Plain OpenAI-compatible APIs do not report a price; estimate it locally so the
            # paper's cost axis is still populated. Prices are USD per million tokens.
            cost_usd = estimate_cost(str(kwargs.get("model", "")), prompt_tokens, completion_tokens)
        try:
            allowance_usd = float(_extra_field(_extra_field(usage, "opencode"), "allowance") or 0.0)
        except (TypeError, ValueError):
            allowance_usd = 0.0
        record_call(
            prompt_tokens,
            completion_tokens,
            dt,
            cost_usd=cost_usd,
            allowance_usd=allowance_usd,
        )
        return resp

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _CountingChat:
    def __init__(self, inner):
        self._inner = inner
        self.completions = _CountingCompletions(inner.completions)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CountingOpenAI:
    """Wraps an `openai.OpenAI` client so every chat completion is counted."""

    def __init__(self, client):
        self._client = client
        self.chat = _CountingChat(client.chat)

    def __getattr__(self, name):
        return getattr(self._client, name)


def snapshot() -> dict:
    with _lock:
        return {
            "usage": {k: dict(v) for k, v in _stats.items()},
            "detections": {k: dict(v) for k, v in _detect.items()},
        }


def reset() -> None:
    with _lock:
        _stats.clear()
        _detect.clear()


def dump(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot(), indent=2))
