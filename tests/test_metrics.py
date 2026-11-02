"""Tests for the pure statistics and cost helpers.

These run without AgentDojo, torch or any API access:

    python -m pytest -q
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analyze import mcnemar_exact, wilson  # noqa: E402
from ipi_eval.usage import estimate_cost  # noqa: E402


def test_wilson_matches_known_value():
    p, lo, hi = wilson(5, 5)
    assert p == 1.0
    assert 0.56 < lo < 0.57  # Wilson lower bound for 5/5 is ~0.566, not 1.0
    assert hi == 1.0

    p, lo, hi = wilson(0, 249)
    assert p == 0.0
    assert lo == 0.0
    assert 0.014 < hi < 0.016  # 95% upper bound ~1.5%


def test_wilson_is_symmetric_and_bounded():
    p, lo, hi = wilson(50, 100)
    assert abs(p - 0.5) < 1e-12
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61
    assert lo < p < hi


def test_wilson_handles_empty_sample():
    for value in wilson(0, 0):
        assert math.isnan(value)


def test_mcnemar_exact_known_values():
    # 5 discordant pairs, all in one direction: 2 * (1/2)^5
    assert abs(mcnemar_exact(5, 0) - 0.0625) < 1e-12
    assert abs(mcnemar_exact(6, 0) - 0.03125) < 1e-12
    # no discordant pairs -> p = 1
    assert mcnemar_exact(0, 0) == 1.0
    # symmetric in its arguments
    assert mcnemar_exact(3, 9) == mcnemar_exact(9, 3)


def test_mcnemar_is_never_above_one():
    for b in range(0, 12):
        for c in range(0, 12):
            assert 0.0 <= mcnemar_exact(b, c) <= 1.0


def test_estimate_cost_matches_price_table():
    # gpt-4o-mini: 0.15 USD/Mtok in, 0.60 USD/Mtok out
    assert abs(estimate_cost("gpt-4o-mini-2024-07-18", 1_000_000, 0) - 0.15) < 1e-12
    assert abs(estimate_cost("gpt-4o-mini-2024-07-18", 0, 1_000_000) - 0.60) < 1e-12
    # unknown model must not invent a price
    assert estimate_cost("some-unlisted-model", 1_000_000, 1_000_000) == 0.0
