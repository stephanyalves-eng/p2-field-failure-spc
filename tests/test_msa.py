"""Known-answer tests for the crossed Gage R&R by ANOVA.

Published reference: Minitab, "Example of Crossed Gage R&R Study" (10 parts, 3 operators,
3 trials, tolerance 8), https://support.minitab.com/minitab/help-and-how-to/quality-and-process-improvement/measurement-system-analysis/how-to/gage-study/crossed-gage-r-r-study/before-you-start/example
Its raw data is not printed on the page, so the variance-component step is tested from the
published ANOVA table, and the ANOVA step is tested on a small set computed by hand.
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.msa import (
    anova_crossed,
    decision,
    f_test,
    gage_evaluation,
    variance_components,
)


def _hand_data():
    # 2 parts x 2 operators x 2 trials. Cells: P1O1 = 1, 3; P1O2 = 2, 4; P2O1 = 5, 7; P2O2 = 8, 10.
    rows = [
        (1, "O1", 1), (1, "O1", 3), (1, "O2", 2), (1, "O2", 4),
        (2, "O1", 5), (2, "O1", 7), (2, "O2", 8), (2, "O2", 10),
    ]  # fmt: skip
    return pd.DataFrame(rows, columns=["part", "operator", "y"])


def test_anova_sums_of_squares_by_hand():
    # Grand mean 5; part means 2.5, 7.5 -> SS 50; operator means 4, 6 -> SS 8;
    # cell means 2, 3, 6, 9 -> SS cells 60, so SS interaction 2; within cells SS 8; total 68.
    t = anova_crossed(_hand_data(), "part", "operator", "y").set_index("source")
    assert t.loc["Part", "ss"] == pytest.approx(50)
    assert t.loc["Operator", "ss"] == pytest.approx(8)
    assert t.loc["Part * Operator", "ss"] == pytest.approx(2)
    assert t.loc["Repeatability", "ss"] == pytest.approx(8)
    assert t.loc["Total", "ss"] == pytest.approx(68)
    assert t.loc[["Part", "Operator", "Part * Operator", "Repeatability"], "df"].tolist() == [
        1,
        1,
        1,
        4,
    ]
    assert t.loc["Repeatability", "ms"] == pytest.approx(2)


def test_anova_rejects_unbalanced_data():
    with pytest.raises(ValueError, match="balanced"):
        anova_crossed(_hand_data().iloc[:-1], "part", "operator", "y")


def test_interaction_f_test_matches_minitab():
    # Minitab: Part * Operator MS 0.01994 (df 18), Repeatability MS 0.04598 (df 60)
    # -> F 0.434, P 0.974
    f, p = f_test(0.01994, 0.04598, 18, 60)
    assert f == pytest.approx(0.434, abs=1e-3)
    assert p == pytest.approx(0.974, abs=1e-3)


def _minitab_table():
    # Two-way ANOVA table with interaction as printed by Minitab.
    return pd.DataFrame(
        {
            "source": ["Part", "Operator", "Part * Operator", "Repeatability", "Total"],
            "df": [9, 2, 18, 60, 89],
            "ss": [88.3619, 3.1673, 0.3590, 2.7589, 94.6471],
        }
    ).assign(ms=lambda t: t["ss"] / t["df"])


def test_variance_components_reproduce_minitab():
    vc = variance_components(_minitab_table(), parts=10, operators=3, trials=3, alpha=0.05)
    assert vc["interaction_removed"] is True
    assert vc["repeatability"] == pytest.approx(0.03997, abs=5e-5)
    assert vc["operator"] == pytest.approx(0.05146, abs=5e-5)
    assert vc["interaction"] == 0
    assert vc["reproducibility"] == pytest.approx(0.05146, abs=5e-5)
    assert vc["gage_rr"] == pytest.approx(0.09143, abs=5e-5)
    assert vc["part"] == pytest.approx(1.08645, abs=5e-5)
    assert vc["total"] == pytest.approx(1.17788, abs=5e-5)
    # the components add up to the total
    assert vc["gage_rr"] + vc["part"] == pytest.approx(vc["total"])


def test_gage_evaluation_reproduces_minitab():
    vc = variance_components(_minitab_table(), parts=10, operators=3, trials=3, alpha=0.05)
    ev = gage_evaluation(vc, tolerance=8).set_index("source")
    assert ev.loc["Total Gage R&R", "std_dev"] == pytest.approx(0.30237, abs=5e-5)
    assert ev.loc["Total Gage R&R", "pct_study_var"] == pytest.approx(27.86, abs=0.01)
    assert ev.loc["Total Gage R&R", "pct_contribution"] == pytest.approx(7.76, abs=0.01)
    assert ev.loc["Total Gage R&R", "pct_tolerance"] == pytest.approx(22.68, abs=0.01)
    assert ev.loc["Repeatability", "pct_study_var"] == pytest.approx(18.42, abs=0.01)
    assert ev.loc["Part-To-Part", "pct_study_var"] == pytest.approx(96.04, abs=0.01)
    assert ev.attrs["ndc"] == 4


def test_interaction_kept_when_significant():
    t = _minitab_table()
    t.loc[t["source"] == "Part * Operator", "ss"] = 3.0  # MS 0.1667, F about 3.6 -> p < 0.05
    t = t.assign(ms=lambda d: d["ss"] / d["df"])
    vc = variance_components(t, parts=10, operators=3, trials=3, alpha=0.05)
    assert vc["interaction_removed"] is False
    assert vc["repeatability"] == pytest.approx(2.7589 / 60)
    assert vc["interaction"] == pytest.approx((3.0 / 18 - 2.7589 / 60) / 3)
    assert vc["operator"] == pytest.approx((3.1673 / 2 - 3.0 / 18) / 30)


@pytest.mark.parametrize(
    ("pct", "ndc", "expected"),
    [(8.0, 12, "accept"), (18.0, 6, "conditional"), (18.0, 4, "reject"), (35.0, 9, "reject")],
)
def test_decision_rules(pct, ndc, expected):
    assert decision(pct, ndc) == expected


def test_full_pipeline_on_noise_free_parts_gives_zero_gage_error():
    parts = np.repeat(np.arange(1, 11), 9)
    ops = np.tile(np.repeat(["A", "B", "C"], 3), 10)
    y = 1.80 + 0.001 * parts.astype(float)
    df = pd.DataFrame({"part": parts, "operator": ops, "y": y})
    vc = variance_components(anova_crossed(df, "part", "operator", "y"), 10, 3, 3)
    assert vc["gage_rr"] == pytest.approx(0, abs=1e-12)
    assert math.isclose(vc["part"], np.var(np.arange(1, 11) * 0.001, ddof=1), rel_tol=1e-9)


def test_simulated_study_is_balanced_and_hides_the_truth():
    from src.simulate.gage import COLUMNS, GageConfig, simulate_study

    df, truth = simulate_study(GageConfig())
    assert list(df.columns) == COLUMNS
    assert len(df) == 90
    assert (df.groupby(["part", "operator"]).size() == 3).all()
    # population %GRR: sqrt((0.002^2 + 0.0012^2) / (0.002^2 + 0.0012^2 + 0.01^2)) = 22.71%
    assert truth["population"]["pct_study_var"] == pytest.approx(22.71, abs=0.01)
    assert truth["population"]["ndc"] == 6  # floor(1.41 * 0.010 / 0.002332)


def test_simulated_study_without_noise_reads_part_value_plus_operator_bias():
    from src.simulate.gage import GageConfig, simulate_study

    df, truth = simulate_study(GageConfig(repeatability_sigma=0.0, resolution=1e-9))
    cell = df[(df["part"] == 3) & (df["operator"] == "B")]["crimp_height_mm"]
    expected = truth["true_part_values_mm"][2] + truth["operator_bias_mm"]["B"]
    assert np.allclose(cell, expected, atol=2e-6)
