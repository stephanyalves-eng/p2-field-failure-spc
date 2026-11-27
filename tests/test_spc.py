"""Known-answer tests for X-bar and R charts and the Western Electric rules."""

import math

import numpy as np
import pandas as pd
import pytest

from src.spc import (
    NIST_FACTORS,
    chart_table,
    d2,
    r_chart_signals,
    signal_log,
    subgroup_stats,
    western_electric,
    xbar_r_limits,
)


def test_nist_table_values_as_printed():
    # NIST/SEMATECH e-Handbook 6.3.2.1, "Factors for Calculating Limits for X-bar and R Charts"
    assert NIST_FACTORS[5] == (0.577, 0, 2.115)
    assert NIST_FACTORS[10] == (0.308, 0.223, 1.777)


@pytest.mark.parametrize("n", range(2, 11))
def test_numeric_d2_reproduces_nist_a2(n):
    # NIST defines A2 = 3 / (d2 * sqrt(n)); d2 is computed here by numerical integration.
    a2 = 3 / (d2(n) * math.sqrt(n))
    assert a2 == pytest.approx(NIST_FACTORS[n][0], abs=0.0006)


def test_d2_known_values():
    # Expected range of n standard normals: n=2 is exactly 2/sqrt(pi).
    assert d2(2) == pytest.approx(2 / math.sqrt(math.pi), abs=1e-6)
    assert d2(5) == pytest.approx(2.326, abs=5e-4)


def _hand_example():
    # Three subgroups of 5, computed by hand:
    # means 3, 4, 3 -> grand mean 10/3; ranges 4, 4, 0 -> R-bar 8/3.
    values = [1, 2, 3, 4, 5, 2, 3, 4, 5, 6, 3, 3, 3, 3, 3]
    return pd.DataFrame({"subgroup": np.repeat([1, 2, 3], 5), "x": values})


def test_subgroup_stats_known_answer():
    stats = subgroup_stats(_hand_example(), "x", "subgroup")
    assert stats["mean"].tolist() == [3, 4, 3]
    assert stats["range"].tolist() == [4, 4, 0]
    assert stats["n"].tolist() == [5, 5, 5]


def test_xbar_r_limits_known_answer():
    lim = xbar_r_limits(subgroup_stats(_hand_example(), "x", "subgroup"))
    rbar = 8 / 3
    assert lim["xbar_center"] == pytest.approx(10 / 3)
    assert lim["xbar_ucl"] == pytest.approx(10 / 3 + 0.577 * rbar)  # 4.8720
    assert lim["xbar_lcl"] == pytest.approx(10 / 3 - 0.577 * rbar)  # 1.7946
    assert lim["r_center"] == pytest.approx(rbar)
    assert lim["r_ucl"] == pytest.approx(2.115 * rbar)  # 5.640
    assert lim["r_lcl"] == 0
    assert lim["sigma_hat"] == pytest.approx(rbar / d2(5))


def test_xbar_r_limits_rejects_unequal_subgroups():
    df = _hand_example().iloc[:-1]
    with pytest.raises(ValueError, match="equal"):
        xbar_r_limits(subgroup_stats(df, "x", "subgroup"))


# Western Electric rules on standardized values z = (x - center) / sigma_xbar.
@pytest.mark.parametrize(
    ("z", "expected"),
    [
        ([0, 0, 0, 0, 3.1], {4: [1]}),
        ([0, 0, 0, 0, -3.1], {4: [1]}),
        ([0, 2.5, 0, 2.5], {3: [2]}),
        ([0, -2.5, -2.5], {2: [2]}),
        ([0, 2.5, -2.5], {}),  # two beyond 2 sigma but on opposite sides
        ([1.5, 1.5, 0, 1.5, 1.5], {4: [3]}),
        ([0.5] * 8, {7: [4]}),
        ([0.5] * 7 + [0.0], {}),  # a point on the center line breaks the run
        ([-0.5] * 9, {7: [4], 8: [4]}),
    ],
)
def test_western_electric_rules(z, expected):
    assert western_electric(np.array(z, dtype=float), 0.0, 1.0) == expected


def test_western_electric_rules_can_fire_together():
    z = [2.5, 2.5, 3.5]
    # index 1: 2 of 3 beyond 2 sigma; index 2: beyond 3 sigma and still 2 of 3 beyond 2 sigma
    assert western_electric(np.array(z), 0.0, 1.0) == {1: [2], 2: [1, 2]}


def test_r_chart_signals_above_ucl_and_long_run():
    r = np.array([1.0, 5.0] + [1.5] * 8)
    # center 1.2, UCL 4: index 1 above UCL; indexes 1..8 are 8 in a row above the center
    assert r_chart_signals(r, center=1.2, ucl=4.0, lcl=0.0) == {1: [1], 8: [4], 9: [4]}


def test_chart_table_flags_a_planted_outlier_and_logs_it():
    rng = np.random.default_rng(3)
    values = 10 + 0.1 * rng.standard_normal(200)
    values[150:155] += 1.0  # subgroup 31 shifted by 10 sigma
    df = pd.DataFrame({"subgroup": np.repeat(np.arange(1, 41), 5), "x": values})
    df["day"] = (df["subgroup"] - 1) // 4 + 1
    stats = subgroup_stats(df, "x", "subgroup")
    table, lim = chart_table(df, "x", baseline=stats["subgroup"] <= 20)
    assert table["baseline"].sum() == 20
    assert "1" in table.loc[table["subgroup"] == 31, "xbar_rules"].item().split(",")
    log = signal_log(table)
    assert set(log.columns) >= {"chart", "subgroup", "rules", "baseline"}
    assert ((log["subgroup"] == 31) & (log["chart"] == "X-bar")).any()
