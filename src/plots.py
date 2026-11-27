"""Static charts for the field failure analysis (matplotlib, light theme)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
NEUTRAL = "#b5b4ae"

DISPLAY_NAMES = {
    "BOLT EV": "Bolt EV",
    "IONIQ 5": "Ioniq 5",
    "MODEL 3": "Model 3",
    "MUSTANG MACH E": "Mustang Mach-E",
}


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)


def pareto_chart(
    table: pd.DataFrame,
    title: str,
    path: Path,
    neutral_labels: list[str] | None = None,
    unit: str = "complaints",
) -> Path:
    """Horizontal Pareto: bars show each label's share; text gives count and cumulative share.

    The cumulative share is written next to each bar instead of drawn on a second axis.
    Labels in `neutral_labels` (unknown or not coded) are drawn in gray.
    """
    neutral = set(neutral_labels or [])
    rows = table.iloc[::-1]  # largest at the top
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(rows) + 1.2), facecolor=SURFACE)
    colors = [NEUTRAL if label in neutral else SERIES_1 for label in rows["label"]]
    ax.barh(rows["label"], rows["share"] * 100, color=colors, height=0.6)
    xmax = rows["share"].max() * 100
    for y, (_, r) in enumerate(rows.iterrows()):
        ax.text(
            r["share"] * 100 + xmax * 0.01,
            y,
            f"{r['count']:,}  ({r['share']:.0%}, cum. {r['cum_share']:.0%})",
            va="center",
            fontsize=8.5,
            color=TEXT_SECONDARY,
        )
    ax.set_xlim(0, xmax * 1.45)
    ax.set_xlabel(f"Share of {unit} (%)", color=TEXT_SECONDARY, fontsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _style(ax)
    ax.tick_params(axis="y", colors=TEXT, length=0)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=11, fontweight="bold")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def share_trend_chart(
    trend: pd.DataFrame, title: str, path: Path, min_complaints: int = 30
) -> Path:
    """Small multiples, one panel per vehicle: target share of complaints by model year.

    Model years with fewer than `min_complaints` complaints are left out; their share
    would move by several points with each new complaint. Counts per point are in the table.
    """
    trend = trend[trend["complaints"] >= min_complaints]
    vehicles = sorted(trend["MODELTXT"].unique())
    fig, axes = plt.subplots(
        1, len(vehicles), figsize=(2.6 * len(vehicles), 3), sharey=True, facecolor=SURFACE
    )
    for ax, vehicle in zip(axes, vehicles, strict=True):
        d = trend[trend["MODELTXT"] == vehicle].sort_values("YEARTXT")
        ax.plot(d["YEARTXT"], d["target_share"] * 100, color=SERIES_1, linewidth=2)
        ax.scatter(d["YEARTXT"], d["target_share"] * 100, color=SERIES_1, s=28, zorder=3)
        ax.set_title(DISPLAY_NAMES.get(vehicle, vehicle), color=TEXT, fontsize=10)
        ax.set_ylim(0, 100)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", rotation=45)
        _style(ax)
    axes[0].set_ylabel("Share of complaints (%)", color=TEXT_SECONDARY, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=11, fontweight="bold")
    fig.supxlabel("Model year", color=TEXT_SECONDARY, fontsize=9)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


SIGNAL = "#eb6834"  # categorical slot 2 (orange), used for points that fire a rule


def xbar_r_chart(table: pd.DataFrame, lim: dict, title: str, path: Path) -> Path:
    """Two stacked panels: X-bar chart and R chart, Phase I baseline shaded, signals marked."""
    fig, (ax_x, ax_r) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True, facecolor=SURFACE, height_ratios=[3, 2]
    )
    x = table["subgroup"].to_numpy()
    base = table.loc[table["baseline"], "subgroup"]
    panels = (
        (ax_x, "mean", "xbar", "xbar_rules", "Subgroup mean (mm)"),
        (ax_r, "range", "r", "r_rules", "Subgroup range (mm)"),
    )
    for ax, col, key, rules, ylabel in panels:
        if len(base):
            ax.axvspan(base.min() - 0.5, base.max() + 0.5, color=GRID, alpha=0.6, lw=0)
        ax.plot(x, table[col], color=SERIES_1, lw=1, marker="o", ms=2.5, zorder=2)
        hit = table[rules] != ""
        ax.scatter(x[hit], table.loc[hit, col], s=40, color=SIGNAL, zorder=3,
                   edgecolor=SURFACE, linewidth=1)  # fmt: skip
        ax.axhline(lim[f"{key}_center"], color=TEXT_SECONDARY, lw=1)
        for bound in ("ucl", "lcl"):
            if key == "r" and bound == "lcl" and lim["r_lcl"] == 0:
                continue
            ax.axhline(lim[f"{key}_{bound}"], color=TEXT_SECONDARY, lw=1, ls="--")
        ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=9)
        _style(ax)
    ax_r.set_xlabel("Subgroup (production order)", color=TEXT_SECONDARY, fontsize=9)
    handles = [
        plt.Line2D([], [], color=SERIES_1, marker="o", ms=4, lw=1, label="Subgroup"),
        plt.Line2D([], [], color=SIGNAL, marker="o", ms=7, lw=0, label="Western Electric signal"),
        plt.Line2D([], [], color=TEXT_SECONDARY, lw=1, ls="--", label="Control limits"),
        plt.Rectangle((0, 0), 1, 1, color=GRID, alpha=0.6, label="Phase I baseline"),
    ]
    ax_x.legend(handles=handles, loc="upper left", fontsize=8, frameon=False, ncol=4)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=11, fontweight="bold")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def capability_histograms(
    panels: list[tuple[str, pd.Series]], lsl: float, usl: float, title: str, path: Path
) -> Path:
    """One histogram per panel (shared x axis) with the spec limits marked."""
    fig, axes = plt.subplots(
        len(panels), 1, figsize=(9, 2.4 * len(panels)), sharex=True, facecolor=SURFACE
    )
    bins = np.arange(lsl - 0.01, usl + 0.0105, 0.002)
    for ax, (label, values) in zip(axes, panels, strict=True):
        ax.hist(values, bins=bins, color=SERIES_1, edgecolor=SURFACE, linewidth=0.5)
        for limit, name in ((lsl, "LSL"), (usl, "USL")):
            ax.axvline(limit, color=SIGNAL, lw=1.5)
            ax.text(limit, ax.get_ylim()[1] * 0.92, f" {name}", color=TEXT_SECONDARY, fontsize=8)
        ax.set_title(label, loc="left", fontsize=9.5, color=TEXT)
        ax.set_ylabel("Parts", color=TEXT_SECONDARY, fontsize=9)
        _style(ax)
    axes[-1].set_xlabel("Crimp height (mm)", color=TEXT_SECONDARY, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=11, fontweight="bold")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def normal_probability_plot(values: pd.Series, title: str, path: Path) -> Path:
    """Ordered values against normal quantiles (Blom plotting positions)."""
    from scipy import stats

    x = np.sort(np.asarray(values, dtype=float))
    n = len(x)
    q = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    slope, intercept = np.polyfit(q, x, 1)
    fig, ax = plt.subplots(figsize=(5.5, 4.5), facecolor=SURFACE)
    ax.scatter(q, x, s=8, color=SERIES_1, alpha=0.7, lw=0)
    ax.plot(q, intercept + slope * q, color=TEXT_SECONDARY, lw=1)
    ax.set_xlabel("Normal quantile", color=TEXT_SECONDARY, fontsize=9)
    ax.set_ylabel("Crimp height (mm)", color=TEXT_SECONDARY, fontsize=9)
    _style(ax)
    fig.suptitle(title, x=0.01, ha="left", color=TEXT, fontsize=10.5, fontweight="bold")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
