"""Process capability (Cp, Cpk, Pp, Ppk), normality check and detection scoring.

Formulas follow the NIST/SEMATECH e-Handbook 6.1.6 "What is Process Capability?"
(https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm):
    Cp = (USL - LSL) / (6 sigma), Cpu = (USL - mu) / (3 sigma), Cpl = (mu - LSL) / (3 sigma),
    Cpk = min(Cpu, Cpl), approximate interval Cpk +/- z sqrt(1/(9n) + Cpk^2 / (2(n-1))).

Convention used here (AIAG): Cp and Cpk use the within-subgroup sigma (R-bar / d2), the
short-term spread a stable process would show; Pp and Ppk use the overall sample standard
deviation, which also carries any shift between subgroups.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from src.spc import d2, subgroup_stats


def indices(mean: float, sigma: float, lsl: float, usl: float) -> dict[str, float]:
    cpu = (usl - mean) / (3 * sigma)
    cpl = (mean - lsl) / (3 * sigma)
    return {"cp": (usl - lsl) / (6 * sigma), "cpu": cpu, "cpl": cpl, "cpk": min(cpu, cpl)}


def cpk_interval(cpk: float, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Approximate two-sided (1 - alpha) interval for Cpk (NIST 6.1.6)."""
    z = stats.norm.ppf(1 - alpha / 2)
    half = z * math.sqrt(1 / (9 * n) + cpk**2 / (2 * (n - 1)))
    return cpk - half, cpk + half


def anderson_darling_normal(values: np.ndarray) -> dict[str, float | bool]:
    """Anderson-Darling test for normality, p-value interpolated from SciPy's tables.

    The interpolated p-value is clipped to the range of the tables (about 0.01 to 0.15).
    """
    result = stats.anderson(np.asarray(values, dtype=float), dist="norm", method="interpolate")
    return {
        "a2": float(result.statistic),
        "p_value": float(result.pvalue),
        "normal_at_5pct": bool(result.pvalue > 0.05),
    }


def capability_study(
    df: pd.DataFrame, value: str, subgroup: str, lsl: float, usl: float
) -> dict[str, float]:
    """Cp/Cpk (within sigma = R-bar / d2) and Pp/Ppk (overall sigma) for one data set."""
    sg = subgroup_stats(df, value, subgroup)
    sizes = sg["n"].unique()
    if len(sizes) != 1:
        raise ValueError(f"subgroups must have equal size, got {sorted(sizes)}")
    x = df[value].to_numpy(dtype=float)
    mean = float(x.mean())
    sigma_within = float(sg["range"].mean()) / d2(int(sizes[0]))
    sigma_overall = float(x.std(ddof=1))
    within = indices(mean, sigma_within, lsl, usl)
    overall = indices(mean, sigma_overall, lsl, usl)
    low, high = cpk_interval(within["cpk"], len(x))
    return {
        "n": len(x),
        "subgroups": len(sg),
        "mean": mean,
        "sigma_within": sigma_within,
        "sigma_overall": sigma_overall,
        "cp": within["cp"],
        "cpk": within["cpk"],
        "cpk_low_95": low,
        "cpk_high_95": high,
        "pp": overall["cp"],
        "ppk": overall["cpk"],
    }


def score_signals(signaled: pd.Series, special: pd.Series) -> dict[str, float]:
    """Confusion counts of chart signals against the true special-cause labels."""
    s = signaled.to_numpy(dtype=bool)
    t = special.to_numpy(dtype=bool)
    tp, fn = int((s & t).sum()), int((~s & t).sum())
    fp, tn = int((s & ~t).sum()), int((~s & ~t).sum())
    return {
        "true_pos": tp,
        "false_neg": fn,
        "false_pos": fp,
        "true_neg": tn,
        "detection_rate": tp / (tp + fn) if tp + fn else float("nan"),
        "false_alarm_rate": fp / (fp + tn) if fp + tn else float("nan"),
    }


def detection_delay(subgroups: pd.Series, signaled: pd.Series, start: int) -> int | None:
    """Stream subgroups between a change at `start` and the first signal (0 = immediate)."""
    after = signaled[subgroups.to_numpy() >= start].to_numpy(dtype=bool)
    hits = np.flatnonzero(after)
    return int(hits[0]) if len(hits) else None
