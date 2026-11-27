"""Crossed Gage R&R by ANOVA (parts x operators x trials, balanced).

Method (AIAG MSA, as implemented by common software and checked in the tests against the
published Minitab "Example of Crossed Gage R&R Study"):

1. Two-way ANOVA with the part x operator interaction. Part and operator are tested against
   the interaction mean square; the interaction is tested against repeatability.
2. If the interaction p-value is not below alpha (0.05), the interaction is pooled into
   repeatability (reduced model).
3. Variance components from expected mean squares (p parts, o operators, r trials):
   repeatability = MS_E; interaction = (MS_PO - MS_E) / r; operator = (MS_O - MS_PO) / (p r)
   (or (MS_O - MS_E) / (p r) in the reduced model); part = (MS_P - MS_PO) / (o r)
   (or (MS_P - MS_E) / (o r)). Negative estimates are set to zero.
4. %Study Var = 100 sd / sd_total, %Contribution = 100 var / var_total,
   %Tolerance = 100 * 6 sd / tolerance, ndc = floor(1.41 * sd_part / sd_gage_rr).

Acceptance (this project's KPI table): %GRR < 10% accept, 10-30% conditional, > 30% reject,
and ndc >= 5.
"""

from __future__ import annotations

import math

import pandas as pd
from scipy import stats


def f_test(ms_num: float, ms_den: float, df_num: int, df_den: int) -> tuple[float, float]:
    if ms_den <= 0:
        return float("nan"), float("nan")
    f = ms_num / ms_den
    return f, float(stats.f.sf(f, df_num, df_den))


def anova_crossed(df: pd.DataFrame, part: str, operator: str, value: str) -> pd.DataFrame:
    """Two-way crossed ANOVA table with interaction: source, df, ss, ms, f, p."""
    cells = df.groupby([part, operator])[value]
    sizes = cells.size()
    p, o = df[part].nunique(), df[operator].nunique()
    if sizes.nunique() != 1 or len(sizes) != p * o:
        raise ValueError("the study must be balanced: every part x operator cell, same trials")
    r = int(sizes.iloc[0])
    grand = df[value].mean()
    ss_total = float(((df[value] - grand) ** 2).sum())
    ss_part = float(o * r * ((df.groupby(part)[value].mean() - grand) ** 2).sum())
    ss_oper = float(p * r * ((df.groupby(operator)[value].mean() - grand) ** 2).sum())
    ss_cells = float(r * ((cells.mean() - grand) ** 2).sum())
    ss_inter = ss_cells - ss_part - ss_oper
    ss_error = ss_total - ss_cells
    dfs = {"part": p - 1, "oper": o - 1, "inter": (p - 1) * (o - 1), "error": p * o * (r - 1)}
    ms = {
        "part": ss_part / dfs["part"],
        "oper": ss_oper / dfs["oper"],
        "inter": ss_inter / dfs["inter"],
        "error": ss_error / dfs["error"],
    }
    f_part = f_test(ms["part"], ms["inter"], dfs["part"], dfs["inter"])
    f_oper = f_test(ms["oper"], ms["inter"], dfs["oper"], dfs["inter"])
    f_inter = f_test(ms["inter"], ms["error"], dfs["inter"], dfs["error"])
    nan = (float("nan"), float("nan"))
    rows = [
        ("Part", dfs["part"], ss_part, ms["part"], *f_part),
        ("Operator", dfs["oper"], ss_oper, ms["oper"], *f_oper),
        ("Part * Operator", dfs["inter"], ss_inter, ms["inter"], *f_inter),
        ("Repeatability", dfs["error"], ss_error, ms["error"], *nan),
        ("Total", p * o * r - 1, ss_total, float("nan"), *nan),
    ]
    return pd.DataFrame(rows, columns=["source", "df", "ss", "ms", "f", "p"])


def variance_components(
    table: pd.DataFrame, parts: int, operators: int, trials: int, alpha: float = 0.05
) -> dict[str, float | bool]:
    """Variance components from an ANOVA table with columns source, df, ss, ms."""
    t = table.set_index("source")
    ms_p, ms_o = t.loc["Part", "ms"], t.loc["Operator", "ms"]
    ms_po, ms_e = t.loc["Part * Operator", "ms"], t.loc["Repeatability", "ms"]
    df_po, df_e = int(t.loc["Part * Operator", "df"]), int(t.loc["Repeatability", "df"])
    _, p_inter = f_test(ms_po, ms_e, df_po, df_e)
    removed = not (p_inter < alpha)  # also removes when the test is undefined
    if removed:
        ms_e = (t.loc["Part * Operator", "ss"] + t.loc["Repeatability", "ss"]) / (df_po + df_e)
        denom, inter = ms_e, 0.0
    else:
        denom, inter = ms_po, max((ms_po - ms_e) / trials, 0.0)
    oper = max((ms_o - denom) / (parts * trials), 0.0)
    part = max((ms_p - denom) / (operators * trials), 0.0)
    repeat = float(ms_e)
    repro = oper + inter
    grr = repeat + repro
    return {
        "interaction_p": p_inter,
        "interaction_removed": removed,
        "repeatability": repeat,
        "operator": oper,
        "interaction": inter,
        "reproducibility": repro,
        "gage_rr": grr,
        "part": part,
        "total": grr + part,
    }


def gage_evaluation(vc: dict, tolerance: float | None = None) -> pd.DataFrame:
    """Std dev, study variation (6 sd), %Study Var, %Contribution, %Tolerance; ndc in attrs."""
    sources = [
        ("Total Gage R&R", vc["gage_rr"]),
        ("Repeatability", vc["repeatability"]),
        ("Reproducibility", vc["reproducibility"]),
        ("Operator", vc["operator"]),
        ("Operator * Part", vc["interaction"]),
        ("Part-To-Part", vc["part"]),
        ("Total Variation", vc["total"]),
    ]
    sd_total = math.sqrt(vc["total"])
    rows = []
    for name, var in sources:
        sd = math.sqrt(var)
        rows.append(
            {
                "source": name,
                "var_comp": var,
                "pct_contribution": 100 * var / vc["total"],
                "std_dev": sd,
                "study_var": 6 * sd,
                "pct_study_var": 100 * sd / sd_total,
                "pct_tolerance": 100 * 6 * sd / tolerance if tolerance else float("nan"),
            }
        )
    out = pd.DataFrame(rows)
    grr_sd = math.sqrt(vc["gage_rr"])
    out.attrs["ndc"] = math.floor(1.41 * math.sqrt(vc["part"]) / grr_sd) if grr_sd > 0 else None
    return out


def decision(pct_grr: float, ndc: int) -> str:
    """Accept, conditional or reject, from %GRR (study variation) and ndc."""
    if pct_grr > 30 or ndc < 5:
        return "reject"
    if pct_grr < 10:
        return "accept"
    return "conditional"
