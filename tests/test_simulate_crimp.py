"""Known-answer tests for the crimp height simulator.

With the noise switched off (sigma = 0) every value equals its designed mean exactly, so the
injected causes can be checked by hand. Statistical checks use long runs and wide tolerances.
"""

import json

import numpy as np
import pytest

from src.simulate.crimp import (
    COLUMNS,
    CrimpConfig,
    first_shifted_subgroup,
    simulate,
    true_parameters,
    write_outputs,
)


def test_table_shape_and_columns():
    cfg = CrimpConfig()
    df = simulate(cfg)
    n_subgroups = cfg.days * len(cfg.shifts) * len(cfg.machines) * cfg.subgroups_per_shift
    assert n_subgroups == 360
    assert len(df) == n_subgroups * cfg.subgroup_size == 1800
    assert list(df.columns) == COLUMNS


def test_analysis_table_hides_the_truth():
    df = simulate(CrimpConfig())
    for hidden in ("true_mean", "true_sigma", "tool_change", "special_cause", "after_shift"):
        assert not any(hidden in col for col in df.columns)


def test_same_seed_same_data_and_different_seed_different_data():
    a = simulate(CrimpConfig(seed=7))
    b = simulate(CrimpConfig(seed=7))
    c = simulate(CrimpConfig(seed=8))
    assert a.equals(b)
    assert not a["crimp_height_mm"].equals(c["crimp_height_mm"])


def test_noise_free_run_reproduces_the_designed_means():
    cfg = CrimpConfig(sigma=0.0)
    df = simulate(cfg)
    a = df[df["machine"] == "A"]
    b = df[df["machine"] == "B"]
    assert np.allclose(a["crimp_height_mm"], 1.800)
    before = b[b["day"] < cfg.tool_change_day]
    after = b[b["day"] >= cfg.tool_change_day]
    assert np.allclose(before["crimp_height_mm"], 1.800)
    assert np.allclose(after["crimp_height_mm"], 1.800 + 0.015)
    assert len(after) == (cfg.days - cfg.tool_change_day + 1) * 3 * 2 * 5


def test_subgroups_are_in_time_order_with_five_parts_each():
    df = simulate(CrimpConfig())
    sizes = df.groupby("subgroup")["part"].count()
    assert (sizes == 5).all()
    order = df.drop_duplicates("subgroup")[["day", "shift", "slot"]]
    assert order.equals(order.sort_values(["day", "shift", "slot"]))
    assert df["subgroup"].is_monotonic_increasing


def test_shift_3_spread_is_larger_by_the_designed_factor():
    cfg = CrimpConfig(days=400, seed=1)
    df = simulate(cfg)
    a = df[(df["machine"] == "A")]
    sd = a.groupby("shift")["crimp_height_mm"].std()
    assert sd["1"] == pytest.approx(0.010, rel=0.05)
    assert sd["3"] / sd["1"] == pytest.approx(1.5, rel=0.08)


def test_values_are_rounded_to_gauge_resolution():
    df = simulate(CrimpConfig())
    scaled = df["crimp_height_mm"] * 1000
    assert np.allclose(scaled, scaled.round())


def test_true_parameters_and_outputs(tmp_path):
    cfg = CrimpConfig()
    truth = true_parameters(cfg)
    assert truth["spec"] == {"lsl": 1.75, "target": 1.80, "usl": 1.85}
    assert truth["special_causes"][0]["machine"] == "B"
    assert truth["special_causes"][0]["mean_shift_mm"] == 0.015
    assert truth["special_causes"][1]["shift"] == "3"
    # Cp of the base process: 0.10 / (6 * 0.010)
    assert truth["base_process"]["cp"] == pytest.approx(1.667, abs=1e-3)
    data_path, truth_path = write_outputs(cfg, tmp_path)
    assert json.loads(truth_path.read_text())["seed"] == cfg.seed
    assert data_path.read_text().splitlines()[0] == ",".join(COLUMNS)


def test_first_shifted_subgroup_known_answer():
    # 15 days x 3 shifts x 2 slots x 2 machines = 180 subgroups before day 16;
    # on day 16 machine A takes subgroup 181 and machine B subgroup 182.
    cfg = CrimpConfig()
    assert first_shifted_subgroup(cfg) == 182
    row = simulate(cfg).query("subgroup == 182").iloc[0]
    assert (row["day"], row["shift"], row["slot"], row["machine"]) == (16, "1", 1, "B")
