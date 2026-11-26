"""Field failure analysis: component taxonomy, Pareto tables and trend by model year.

Counting rule: an NHTSA complaint (ODINO) can name several components. A complaint counts
once in every group it names, and Pareto shares are shares of these complaint-group
mentions, so they add up to 100%.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAPPINGS_DIR = ROOT / "data" / "mappings"
NOT_CODED = "Not coded"


def load_taxonomy(path: Path = MAPPINGS_DIR / "component_taxonomy.csv") -> dict[str, str]:
    """NHTSA top-level system -> project component group."""
    table = pd.read_csv(path, dtype=str)
    return dict(zip(table["nhtsa_system"], table["group"], strict=True))


def load_failure_mode_rules(
    path: Path = MAPPINGS_DIR / "electrical_failure_modes.csv",
) -> list[tuple[str, str]]:
    """Ordered (failure_mode, regex) rules for coding electrical complaint narratives."""
    table = pd.read_csv(path, dtype={"priority": int, "failure_mode": str, "pattern": str})
    table = table.sort_values("priority")
    return list(zip(table["failure_mode"], table["pattern"], strict=True))


def load_jasc_titles(path: Path = MAPPINGS_DIR / "jasc_ata24.csv") -> dict[str, str]:
    """JASC code -> official title (FAA JASC code table, ATA chapter 24)."""
    table = pd.read_csv(path, dtype=str)
    return dict(zip(table["jasc_code"], table["title"], strict=True))


def load_part_groups(path: Path = MAPPINGS_DIR / "sdr_part_groups.csv") -> dict[str, str]:
    """SDR part name -> project part group."""
    table = pd.read_csv(path, dtype=str)
    return dict(zip(table["part_name"], table["group"], strict=True))


def map_values(values: pd.Series, mapping: dict[str, str]) -> pd.Series:
    """Map values with a published table; raise if any value is missing from it."""
    missing = sorted(set(values) - set(mapping))
    if missing:
        raise KeyError(f"values missing from the mapping: {missing}")
    return values.map(mapping)


def system_of(component: pd.Series) -> pd.Series:
    """Top-level system: the text before the first colon, trimmed and upper-cased."""
    return component.str.split(":", n=1).str[0].str.strip().str.upper()


def map_groups(component: pd.Series, taxonomy: dict[str, str]) -> pd.Series:
    """Map component text to groups; raise if any top-level system is not in the taxonomy."""
    return map_values(system_of(component), taxonomy)


def complaint_mentions(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """One row per complaint and group."""
    return df.drop_duplicates(subset=["ODINO", group_col]).reset_index(drop=True)


def pareto(labels: pd.Series, last: list[str] | None = None) -> pd.DataFrame:
    """Pareto table sorted by count (ties alphabetical); labels in `last` go to the end."""
    last = last or []
    counts = labels.value_counts().rename_axis("label").reset_index(name="count")
    counts["is_last"] = counts["label"].isin(last)
    counts = counts.sort_values(["is_last", "count", "label"], ascending=[True, False, True])
    counts = counts.drop(columns="is_last").reset_index(drop=True)
    total = counts["count"].sum()
    counts["share"] = counts["count"] / total
    counts["cum_share"] = counts["share"].cumsum()
    return counts


def top_n_share(table: pd.DataFrame, n: int = 3, last: list[str] | None = None) -> float:
    """Share of all mentions held by the n largest labels, not counting labels in `last`."""
    ranked = table[~table["label"].isin(last or [])]
    return float(ranked["count"].head(n).sum() / table["count"].sum())


def code_failure_mode(text: pd.Series, rules: list[tuple[str, str]]) -> pd.Series:
    """Assign each narrative the first rule whose regex matches (case-insensitive)."""
    compiled = [(mode, re.compile(pattern, re.IGNORECASE)) for mode, pattern in rules]

    def code(narrative: str) -> str:
        for mode, regex in compiled:
            if regex.search(narrative or ""):
                return mode
        return NOT_CODED

    return text.fillna("").map(code)


def trend_by_model_year(mentions: pd.DataFrame, group_col: str, target: str) -> pd.DataFrame:
    """Per vehicle and model year: complaints, complaints naming `target`, and their share.

    The share is used instead of raw counts because sales volumes are not in the data:
    a share does not grow just because more vehicles of a model year were sold.
    """
    keys = ["MODELTXT", "YEARTXT"]
    complaints = mentions.groupby(keys)["ODINO"].nunique().rename("complaints")
    hits = (
        mentions[mentions[group_col] == target]
        .groupby(keys)["ODINO"]
        .nunique()
        .rename("target_complaints")
    )
    out = pd.concat([complaints, hits], axis=1).fillna(0).astype(int).reset_index()
    out["target_share"] = out["target_complaints"] / out["complaints"]
    return out
