"""Shewhart X-bar and R charts with Western Electric rules.

Control limit factors A2, D3 and D4 are copied from the NIST/SEMATECH e-Handbook of
Statistical Methods, section 6.3.2.1 (https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc321.htm).
d2 (expected range of n standard normal values) is not printed there; it is computed by
numerical integration, and the tests check that 3 / (d2 * sqrt(n)) reproduces NIST's A2.

Western Electric rules, as listed in section 6.3.2 of the same handbook:
1. One point beyond 3 sigma.
2. Two out of the last three points beyond 2 sigma, on the same side.
3. Four out of the last five points beyond 1 sigma, on the same side.
4. Eight consecutive points on the same side of the center line.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# n: (A2, D3, D4) as printed by NIST.
NIST_FACTORS: dict[int, tuple[float, float, float]] = {
    2: (1.880, 0, 3.267),
    3: (1.023, 0, 2.575),
    4: (0.729, 0, 2.282),
    5: (0.577, 0, 2.115),
    6: (0.483, 0, 2.004),
    7: (0.419, 0.076, 1.924),
    8: (0.373, 0.136, 1.864),
    9: (0.337, 0.184, 1.816),
    10: (0.308, 0.223, 1.777),
}


def d2(n: int) -> float:
    """Expected range of n independent standard normal values, by numerical integration.

    d2 = integral over x of [1 - Phi(x)^n - (1 - Phi(x))^n].
    """
    x = np.linspace(-12, 12, 200_001)
    phi = 0.5 * (1 + np.vectorize(math.erf)(x / math.sqrt(2)))
    integrand = 1 - phi**n - (1 - phi) ** n
    return float(np.sum((integrand[1:] + integrand[:-1]) / 2 * np.diff(x)))


def subgroup_stats(df: pd.DataFrame, value: str, subgroup: str) -> pd.DataFrame:
    """Mean, range and size of each subgroup, in subgroup order."""
    g = df.groupby(subgroup, sort=True)[value]
    out = pd.DataFrame({"mean": g.mean(), "range": g.max() - g.min(), "n": g.size()})
    return out.reset_index()


def xbar_r_limits(stats: pd.DataFrame) -> dict[str, float]:
    """Center lines and 3-sigma limits for the X-bar and R charts from R-bar."""
    sizes = stats["n"].unique()
    if len(sizes) != 1:
        raise ValueError(f"subgroups must have equal size, got {sorted(sizes)}")
    n = int(sizes[0])
    a2, d3_factor, d4_factor = NIST_FACTORS[n]
    xbarbar = float(stats["mean"].mean())
    rbar = float(stats["range"].mean())
    return {
        "n": n,
        "xbar_center": xbarbar,
        "xbar_ucl": xbarbar + a2 * rbar,
        "xbar_lcl": xbarbar - a2 * rbar,
        "r_center": rbar,
        "r_ucl": d4_factor * rbar,
        "r_lcl": d3_factor * rbar,
        "sigma_hat": rbar / d2(n),
        "sigma_xbar": a2 * rbar / 3,
    }


def _add(signals: dict[int, list[int]], i: int, rule: int) -> None:
    signals.setdefault(i, []).append(rule)


def western_electric(values: np.ndarray, center: float, sigma: float) -> dict[int, list[int]]:
    """Positions that trigger each Western Electric rule (sigma is the sigma of the plotted points).

    A rule fires at the point that completes the pattern. Windows at the start of the series
    may be shorter than 3 or 5 points.
    """
    z = (np.asarray(values, dtype=float) - center) / sigma
    signals: dict[int, list[int]] = {}
    for i in range(len(z)):
        if abs(z[i]) > 3:
            _add(signals, i, 1)
        for side in (1, -1):
            w3 = side * z[max(0, i - 2) : i + 1]
            w5 = side * z[max(0, i - 4) : i + 1]
            if side * z[i] > 2 and (w3 > 2).sum() >= 2:
                _add(signals, i, 2)
            if side * z[i] > 1 and (w5 > 1).sum() >= 4:
                _add(signals, i, 3)
            if i >= 7 and (side * z[i - 7 : i + 1] > 0).all():
                _add(signals, i, 4)
    return signals


def r_chart_signals(
    ranges: np.ndarray, center: float, ucl: float, lcl: float
) -> dict[int, list[int]]:
    """R chart: rule 1 (outside the limits) and rule 4 (8 in a row on one side of R-bar)."""
    r = np.asarray(ranges, dtype=float)
    signals: dict[int, list[int]] = {}
    for i in range(len(r)):
        if r[i] > ucl or (lcl > 0 and r[i] < lcl):
            _add(signals, i, 1)
        if i >= 7 and ((r[i - 7 : i + 1] > center).all() or (r[i - 7 : i + 1] < center).all()):
            _add(signals, i, 4)
    return signals


def chart_table(
    df: pd.DataFrame,
    value: str = "crimp_height_mm",
    baseline: pd.Series | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """X-bar and R chart table for one process stream (for example one machine).

    Limits come from the subgroups flagged in `baseline` (a boolean Series indexed like the
    subgroup table, Phase I); every subgroup is then checked against them (Phase II).
    Returns the per-subgroup table with the rules fired, and the limits.
    """
    keys = [c for c in ("day", "shift", "slot", "machine") if c in df.columns]
    stats = subgroup_stats(df, value, "subgroup")
    info = df.drop_duplicates("subgroup").set_index("subgroup")[keys]
    stats = stats.join(info, on="subgroup")
    base = stats if baseline is None else stats[baseline.to_numpy()]
    lim = xbar_r_limits(base)
    x_sig = western_electric(stats["mean"].to_numpy(), lim["xbar_center"], lim["sigma_xbar"])
    r_sig = r_chart_signals(stats["range"].to_numpy(), lim["r_center"], lim["r_ucl"], lim["r_lcl"])
    stats["baseline"] = True if baseline is None else baseline.to_numpy()
    stats["xbar_rules"] = [",".join(map(str, x_sig.get(i, []))) for i in range(len(stats))]
    stats["r_rules"] = [",".join(map(str, r_sig.get(i, []))) for i in range(len(stats))]
    return stats, lim


def signal_log(table: pd.DataFrame) -> pd.DataFrame:
    """One row per chart and subgroup with at least one rule fired."""
    rows = []
    for chart, col in (("X-bar", "xbar_rules"), ("R", "r_rules")):
        hits = table[table[col] != ""]
        rows.append(hits.assign(chart=chart, rules=hits[col]))
    context = [c for c in ("machine", "day", "shift", "slot") if c in table.columns]
    out = pd.concat(rows)[["chart", "subgroup", *context, "mean", "range", "rules", "baseline"]]
    return out.sort_values(["subgroup", "chart"]).reset_index(drop=True)
