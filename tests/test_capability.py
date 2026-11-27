"""Known-answer tests for capability indices, normality check and detection scoring."""

import math

import numpy as np
import pandas as pd
import pytest

from src.capability import (
    anderson_darling_normal,
    capability_study,
    cpk_interval,
    detection_delay,
    indices,
    score_signals,
)
from src.spc import d2


def test_indices_nist_worked_example():
    # NIST/SEMATECH e-Handbook 6.1.6, "Capability Index Example": USL 20, LSL 8, mean 16, s 2.
    out = indices(mean=16, sigma=2, lsl=8, usl=20)
    assert out["cp"] == pytest.approx(1.0)
    assert out["cpu"] == pytest.approx(0.6667, abs=1e-4)
    assert out["cpl"] == pytest.approx(1.3333, abs=1e-4)
    assert out["cpk"] == pytest.approx(0.6667, abs=1e-4)


def test_cpk_interval_hand_computed():
    # se = sqrt(1/900 + 1/198) = 0.078496; z(0.975) = 1.959964 -> 1 +/- 0.15385
    low, high = cpk_interval(cpk=1.0, n=100)
    assert low == pytest.approx(0.84615, abs=1e-4)
    assert high == pytest.approx(1.15385, abs=1e-4)


def test_capability_study_hand_computed():
    df = pd.DataFrame({"subgroup": np.repeat([1, 2], 5), "x": [1, 2, 3, 4, 5, 2, 3, 4, 5, 6]})
    out = capability_study(df, "x", "subgroup", lsl=0, usl=8)
    assert out["n"] == 10
    assert out["mean"] == pytest.approx(3.5)
    assert out["sigma_within"] == pytest.approx(4 / d2(5))  # R-bar = 4
    assert out["sigma_overall"] == pytest.approx(math.sqrt(22.5 / 9))  # 1.5811
    assert out["pp"] == pytest.approx(8 / (6 * math.sqrt(2.5)))  # 0.8433
    assert out["ppk"] == pytest.approx(3.5 / (3 * math.sqrt(2.5)))  # 0.7379
    assert out["cp"] == pytest.approx(8 / (6 * 4 / d2(5)))
    assert out["cpk"] == pytest.approx(3.5 / (3 * 4 / d2(5)))


def test_anderson_darling_accepts_normal_and_rejects_skewed():
    rng = np.random.default_rng(0)
    assert anderson_darling_normal(rng.normal(size=500))["normal_at_5pct"]
    assert not anderson_darling_normal(rng.exponential(size=500))["normal_at_5pct"]


def test_score_signals_hand_counts():
    signaled = pd.Series([True, True, False, False, True, False])
    special = pd.Series([True, False, True, False, False, False])
    out = score_signals(signaled, special)
    assert (out["true_pos"], out["false_neg"], out["false_pos"], out["true_neg"]) == (1, 1, 2, 2)
    assert out["detection_rate"] == pytest.approx(0.5)
    assert out["false_alarm_rate"] == pytest.approx(0.5)


def test_detection_delay_counts_stream_subgroups_after_the_change():
    subgroups = pd.Series([10, 12, 14, 16, 18])
    signaled = pd.Series([True, False, False, True, True])
    # change at subgroup 12: first signal at 16, two stream subgroups after the change
    assert detection_delay(subgroups, signaled, start=12) == 2
    assert detection_delay(subgroups, pd.Series([False] * 5), start=12) is None
