"""Static charts (matplotlib) in the visual identity of the Stephany Alves Design System.

Colors are the design system's light-theme tokens (tokens.css): ivory page surface, near-black
ink, `--dv-*` data-viz tokens for series, context, gridlines and axes, and the semantic
favorable / unfavorable colors for meaning. Type: IBM Plex Sans for titles and labels, IBM Plex
Mono uppercase for eyebrows, axis titles and footers (fallbacks Segoe UI / Arial and Consolas).
Rules applied: rows-only gridlines, a visible baseline, square data nodes, no rounded corners,
one highlighted series with the rest in context gray, meaning shown by color plus a label,
and a source line under every chart.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# --- Design system tokens (light theme) ---------------------------------------------------
SURFACE = "#F5F4EC"  # --surface-page (sa-ivory)
TEXT = "#101714"  # --text-primary (sa-near-black)
TEXT_SECONDARY = "#454C48"  # --text-secondary (sa-gray-700)
TEXT_TERTIARY = "#5E6561"  # --text-tertiary (sa-gray-600)
GRID = "#E8E9E5"  # --dv-gridline
AXIS = "#5E6561"  # --dv-axis
BASELINE_FILL = "#E4ECE7"  # --surface-accent (sa-sage-100)
SERIES_1 = "#1E5246"  # --dv-cat-1 (forest 700), the highlighted series
SERIES_2 = "#8FA99D"  # --dv-cat-2 (muted sage)
SERIES_3 = "#4F6D8A"  # --dv-cat-3
CONTEXT = "#D6D8D2"  # --dv-context, everything that is not the point of the chart
NEUTRAL = CONTEXT
UNFAVORABLE = "#A63A2A"  # --dv-unfavorable (out of control, reject)
FAVORABLE = "#1F7A4F"  # --dv-favorable (accept)
TARGET = "#101714"  # --dv-target (spec limits)
SIGNAL = UNFAVORABLE  # chart points that fire a rule are unfavorable signals
CATEGORICAL = [SERIES_1, SERIES_2, SERIES_3, "#C49A45", "#B4694A", "#35D58A", "#7A6A85", "#5E6561"]

SANS = ["IBM Plex Sans", "Segoe UI", "Arial", "DejaVu Sans"]
MONO = ["IBM Plex Mono", "Consolas", "DejaVu Sans Mono"]

plt.rcParams.update(
    {
        "font.family": SANS,
        "font.size": 9,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": TEXT_TERTIARY,
        "xtick.color": TEXT_TERTIARY,
        "ytick.color": TEXT_TERTIARY,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    }
)

DISPLAY_NAMES = {
    "BOLT EV": "Bolt EV",
    "IONIQ 5": "Ioniq 5",
    "MODEL 3": "Model 3",
    "MUSTANG MACH E": "Mustang Mach-E",
}

HEADER_IN = 0.78  # inches reserved above the plot for eyebrow and title
FOOTER_IN = 0.36  # inches reserved below for the source line


def _style(ax: plt.Axes, grid_axis: str = "y", mono_ticks: str = "both") -> None:
    """Rows-only gridlines, baseline in the axis color, no frame, mono tick labels."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(1)
    ax.grid(False)
    ax.grid(True, axis=grid_axis, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXT_TERTIARY, labelsize=8, length=0, pad=6)
    axes = {"both": ("x", "y"), "x": ("x",), "y": ("y",), "none": ()}[mono_ticks]
    for name in axes:
        for label in getattr(ax, f"get_{name}ticklabels")():
            label.set_fontfamily(MONO)


def _axis_title(ax: plt.Axes, x: str | None = None, y: str | None = None) -> None:
    """Axis titles in mono uppercase, as the design system's axis labels."""
    if x:
        ax.set_xlabel(x.upper(), fontfamily=MONO, fontsize=7.5, color=TEXT_TERTIARY, labelpad=8)
    if y:
        ax.set_ylabel(y.upper(), fontfamily=MONO, fontsize=7.5, color=TEXT_TERTIARY, labelpad=8)


def _finish(fig: plt.Figure, title: str, path: Path, eyebrow: str | None, source: str | None):
    """Eyebrow + title header, source footer, tight layout inside the reserved bands, save."""
    width, height = fig.get_size_inches()
    top = 1 - HEADER_IN / height
    bottom = FOOTER_IN / height if source else 0.02
    fig.tight_layout(rect=(0, bottom, 1, top))
    left = 0.18 / width
    if eyebrow:
        fig.text(left, 1 - 0.22 / height, eyebrow.upper(), fontfamily=MONO, fontsize=7.5,
                 fontweight="medium", color=TEXT_TERTIARY, va="top")  # fmt: skip
    fig.text(left, 1 - 0.40 / height, title, fontsize=12.5, fontweight="medium", color=TEXT,
             va="top")  # fmt: skip
    if source:
        fig.text(left, 0.12 / height, f"SOURCE · {source.upper()}", fontfamily=MONO, fontsize=6.5,
                 color=TEXT_TERTIARY, va="bottom")  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _legend(ax: plt.Axes, handles: list, ncol: int, align: str = "left") -> None:
    """Legend in one row just above the plot area, so it never covers data."""
    anchor = (0.0, 1.01) if align == "left" else (1.0, 1.01)
    leg = ax.legend(handles=handles, loc=f"lower {align}", bbox_to_anchor=anchor, fontsize=8,
                    frameon=False, ncol=ncol, handlelength=1.4, columnspacing=1.6,
                    borderaxespad=0.0)  # fmt: skip
    for text in leg.get_texts():
        text.set_color(TEXT_SECONDARY)


def _square(color: str, label: str) -> plt.Line2D:
    return plt.Line2D([], [], color=color, marker="s", ms=7, lw=0, label=label)


def pareto_chart(
    table: pd.DataFrame,
    title: str,
    path: Path,
    neutral_labels: list[str] | None = None,
    unit: str = "complaints",
    eyebrow: str | None = None,
    source: str | None = None,
    highlight_top: int = 3,
) -> Path:
    """Horizontal Pareto. The top-N bars (the KPI) carry the brand color, the other failure
    modes are sage, and labels in `neutral_labels` (unknown, not coded) are context gray.
    Count, share and cumulative share are written next to each bar (no second axis).
    """
    neutral = set(neutral_labels or [])
    ranked = [lbl for lbl in table["label"] if lbl not in neutral][:highlight_top]
    rows = table.iloc[::-1]  # largest at the top

    def color(label: str) -> str:
        if label in neutral:
            return CONTEXT
        return SERIES_1 if label in ranked else SERIES_2

    fig, ax = plt.subplots(figsize=(8.4, 0.42 * len(rows) + HEADER_IN + FOOTER_IN + 1.0))
    ax.barh(rows["label"], rows["share"] * 100, color=[color(lbl) for lbl in rows["label"]],
            height=0.62)  # fmt: skip
    xmax = rows["share"].max() * 100
    for y, (_, r) in enumerate(rows.iterrows()):
        ax.text(r["share"] * 100 + xmax * 0.012, y,
                f"{r['count']:,}  ·  {r['share']:.0%}  ·  cum. {r['cum_share']:.0%}",
                va="center", fontsize=7.8, fontfamily=MONO, color=TEXT_SECONDARY)  # fmt: skip
    ax.set_xlim(0, xmax * 1.55)
    _axis_title(ax, x=f"Share of {unit} (%)")
    _style(ax, grid_axis="x", mono_ticks="x")
    ax.tick_params(axis="y", colors=TEXT, labelsize=8.5)
    handles = [_square(SERIES_1, f"Top {highlight_top}"), _square(SERIES_2, "Other")]
    if neutral & set(table["label"]):
        handles.append(_square(CONTEXT, "Not a failure mode"))
    _legend(ax, handles, ncol=len(handles), align="right")
    return _finish(fig, title, path, eyebrow, source)


def share_trend_chart(
    trend: pd.DataFrame,
    title: str,
    path: Path,
    min_complaints: int = 30,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """Small multiples, one panel per vehicle: target share of complaints by model year.

    Model years with fewer than `min_complaints` complaints are left out; their share
    would move by several points with each new complaint. Counts per point are in the table.
    """
    trend = trend[trend["complaints"] >= min_complaints]
    vehicles = sorted(trend["MODELTXT"].unique())
    fig, axes = plt.subplots(
        1, len(vehicles), figsize=(2.7 * len(vehicles), 3.0 + HEADER_IN + FOOTER_IN), sharey=True
    )
    for ax, vehicle in zip(axes, vehicles, strict=True):
        d = trend[trend["MODELTXT"] == vehicle].sort_values("YEARTXT")
        ax.plot(d["YEARTXT"], d["target_share"] * 100, color=SERIES_1, linewidth=2)
        ax.scatter(d["YEARTXT"], d["target_share"] * 100, color=SERIES_1, s=26, marker="s",
                   zorder=3, linewidth=0)  # fmt: skip
        ax.set_title(DISPLAY_NAMES.get(vehicle, vehicle), color=TEXT, fontsize=9.5,
                     fontweight="medium", loc="left")  # fmt: skip
        ax.set_ylim(0, 100)
        ax.tick_params(axis="x", rotation=45)
        _style(ax)
    _axis_title(axes[0], y="Share of complaints (%)")
    for ax in axes:
        _axis_title(ax, x="Model year")
    return _finish(fig, title, path, eyebrow, source)


def xbar_r_chart(
    table: pd.DataFrame,
    lim: dict,
    title: str,
    path: Path,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """Two stacked panels: X-bar chart and R chart, Phase I baseline shaded, signals marked."""
    fig, (ax_x, ax_r) = plt.subplots(
        2, 1, figsize=(11, 6 + HEADER_IN + FOOTER_IN), sharex=True, height_ratios=[3, 2]
    )
    x = table["subgroup"].to_numpy()
    base = table.loc[table["baseline"], "subgroup"]
    panels = (
        (ax_x, "mean", "xbar", "xbar_rules", "Subgroup mean (mm)"),
        (ax_r, "range", "r", "r_rules", "Subgroup range (mm)"),
    )
    for ax, col, key, rules, ylabel in panels:
        if len(base):
            ax.axvspan(base.min() - 0.5, base.max() + 0.5, color=BASELINE_FILL, lw=0)
        ax.plot(x, table[col], color=SERIES_1, lw=1, marker="s", ms=2.2, zorder=2)
        hit = table[rules] != ""
        ax.scatter(x[hit], table.loc[hit, col], s=30, marker="s", color=SIGNAL, zorder=3,
                   edgecolor=SURFACE, linewidth=0.8)  # fmt: skip
        ax.axhline(lim[f"{key}_center"], color=TEXT_SECONDARY, lw=1)
        for bound in ("ucl", "lcl"):
            if key == "r" and bound == "lcl" and lim["r_lcl"] == 0:
                continue
            ax.axhline(lim[f"{key}_{bound}"], color=TEXT_SECONDARY, lw=1, ls=(0, (4, 3)))
        _axis_title(ax, y=ylabel)
        _style(ax)
    _axis_title(ax_r, x="Subgroup (production order)")
    handles = [
        plt.Line2D([], [], color=SERIES_1, marker="s", ms=3.5, lw=1, label="Subgroup"),
        _square(SIGNAL, "Out of control (Western Electric rule)"),
        plt.Line2D([], [], color=TEXT_SECONDARY, lw=1, ls=(0, (4, 3)), label="Control limits"),
        plt.Rectangle((0, 0), 1, 1, color=BASELINE_FILL, label="Phase I baseline"),
    ]
    _legend(ax_x, handles, ncol=4)
    return _finish(fig, title, path, eyebrow, source)


def capability_histograms(
    panels: list[tuple[str, pd.Series]],
    lsl: float,
    usl: float,
    title: str,
    path: Path,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """One histogram per panel (shared x axis) with the spec limits marked."""
    fig, axes = plt.subplots(
        len(panels), 1, figsize=(9, 2.3 * len(panels) + HEADER_IN + FOOTER_IN), sharex=True
    )
    bins = np.arange(lsl - 0.01, usl + 0.0105, 0.002)
    for ax, (label, values) in zip(axes, panels, strict=True):
        ax.hist(values, bins=bins, color=SERIES_1, edgecolor=SURFACE, linewidth=0.8)
        for limit, name in ((lsl, "LSL"), (usl, "USL")):
            ax.axvline(limit, color=TARGET, lw=1.25, ls=(0, (4, 3)))
            ax.text(limit, ax.get_ylim()[1] * 0.95, f" {name} {limit:.2f}", fontfamily=MONO,
                    fontsize=7, color=TEXT, va="top")  # fmt: skip
        ax.set_title(label, loc="left", fontsize=9, color=TEXT_SECONDARY)
        _axis_title(ax, y="Parts")
        _style(ax)
    _axis_title(axes[-1], x="Crimp height (mm)")
    return _finish(fig, title, path, eyebrow, source)


def normal_probability_plot(
    values: pd.Series,
    title: str,
    path: Path,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """Ordered values against normal quantiles (Blom plotting positions)."""
    from scipy import stats

    x = np.sort(np.asarray(values, dtype=float))
    n = len(x)
    q = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    slope, intercept = np.polyfit(q, x, 1)
    fig, ax = plt.subplots(figsize=(6, 4.4 + HEADER_IN + FOOTER_IN))
    ax.scatter(q, x, s=9, marker="s", color=SERIES_1, alpha=0.75, lw=0)
    ax.plot(q, intercept + slope * q, color=TEXT_SECONDARY, lw=1)
    _axis_title(ax, x="Normal quantile", y="Crimp height (mm)")
    _style(ax)
    return _finish(fig, title, path, eyebrow, source)


def grr_study_var_chart(
    evaluation: pd.DataFrame,
    title: str,
    path: Path,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """%Study Var by source with the 10% (accept) and 30% (reject) lines."""
    keep = ["Total Gage R&R", "Repeatability", "Reproducibility", "Part-To-Part"]
    ev = evaluation.set_index("source").loc[keep].iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 2.6 + HEADER_IN + FOOTER_IN))
    colors = [SERIES_1 if s == "Total Gage R&R" else (CONTEXT if s == "Part-To-Part" else SERIES_2)
              for s in ev.index]  # fmt: skip
    ax.barh(ev.index, ev["pct_study_var"], color=colors, height=0.62)
    for y, v in enumerate(ev["pct_study_var"]):
        # value inside the bar end when it fits, so it never meets the threshold lines
        inside = v >= 12
        on_dark = inside and ev.index[y] != "Part-To-Part"
        ax.text(v - 1 if inside else v + 1, y, f"{v:.1f}%", va="center",
                ha="right" if inside else "left", fontsize=7.8, fontfamily=MONO,
                color=SURFACE if on_dark else TEXT_SECONDARY)  # fmt: skip
    for line, label, color in ((10, "10% · ACCEPT BELOW", FAVORABLE),
                               (30, "30% · REJECT ABOVE", UNFAVORABLE)):  # fmt: skip
        ax.axvline(line, color=color, lw=1.25, ls=(0, (4, 3)))
        ax.text(line + 0.8, len(ev) - 0.42, label, fontsize=6.8, fontfamily=MONO, color=color)
    ax.set_xlim(0, 110)
    _axis_title(ax, x="% of study variation")
    _style(ax, grid_axis="x", mono_ticks="x")
    ax.tick_params(axis="y", colors=TEXT, labelsize=8.5)
    return _finish(fig, title, path, eyebrow, source)


def grr_by_part_chart(
    df: pd.DataFrame,
    title: str,
    path: Path,
    eyebrow: str | None = None,
    source: str | None = None,
) -> Path:
    """Readings by part, one color and one marker per operator (fixed categorical order)."""
    markers = ["s", "D", "^"]
    fig, ax = plt.subplots(figsize=(9, 3.6 + HEADER_IN + FOOTER_IN))
    operators = sorted(df["operator"].unique())
    handles = []
    for k, op in enumerate(operators):
        d = df[df["operator"] == op]
        color, marker = CATEGORICAL[k], markers[k % len(markers)]
        ax.scatter(d["part"] + (k - 1) * 0.18, d["crimp_height_mm"], s=20, color=color,
                   marker=marker, edgecolor=SURFACE, linewidth=0.5)  # fmt: skip
        handles.append(
            plt.Line2D([], [], color=color, marker=marker, ms=6, lw=0, label=f"Operator {op}")
        )
    means = df.groupby("part")["crimp_height_mm"].mean()
    ax.plot(means.index, means.values, color=TEXT_SECONDARY, lw=1)
    handles.append(plt.Line2D([], [], color=TEXT_SECONDARY, lw=1, label="Part mean"))
    ax.set_xticks(means.index)
    _axis_title(ax, x="Part", y="Crimp height (mm)")
    _style(ax)
    _legend(ax, handles, ncol=4)
    return _finish(fig, title, path, eyebrow, source)
