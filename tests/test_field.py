"""Known-answer tests for the field failure Pareto, taxonomy and trend functions."""

import pandas as pd
import pytest

from src.field import (
    code_failure_mode,
    complaint_mentions,
    load_failure_mode_rules,
    load_taxonomy,
    map_groups,
    pareto,
    system_of,
    top_n_share,
    trend_by_model_year,
)


def test_system_of_takes_text_before_first_colon_trimmed_and_upper():
    s = pd.Series(["ELECTRICAL SYSTEM:12V/24V/48V BATTERY", " steering ", "SERVICE BRAKES, AIR"])
    assert system_of(s).tolist() == ["ELECTRICAL SYSTEM", "STEERING", "SERVICE BRAKES, AIR"]


def test_map_groups_uses_the_mapping():
    s = pd.Series(["ELECTRICAL SYSTEM:ADAS", "TIRES"])
    out = map_groups(s, {"ELECTRICAL SYSTEM": "Electrical", "TIRES": "Wheels"})
    assert out.tolist() == ["Electrical", "Wheels"]


def test_map_groups_fails_loudly_on_unmapped_systems():
    with pytest.raises(KeyError, match="NEW SYSTEM"):
        map_groups(pd.Series(["NEW SYSTEM:PART"]), {"TIRES": "Wheels"})


def test_complaint_mentions_counts_each_complaint_once_per_group():
    df = pd.DataFrame(
        {
            "ODINO": ["1", "1", "1", "2"],
            "group": ["Electrical", "Electrical", "Steering", "Electrical"],
            "MODELTXT": ["A", "A", "A", "B"],
        }
    )
    out = complaint_mentions(df, "group")
    assert len(out) == 3
    assert sorted(out["group"]) == ["Electrical", "Electrical", "Steering"]


def test_pareto_known_answer():
    # 5 A, 3 B, 1 C, 1 Unknown: shares 50/30/10/10, Unknown forced to the end.
    labels = pd.Series(["A"] * 5 + ["B"] * 3 + ["Unknown"] * 1 + ["C"] * 1)
    table = pareto(labels, last=["Unknown"])
    assert table["label"].tolist() == ["A", "B", "C", "Unknown"]
    assert table["count"].tolist() == [5, 3, 1, 1]
    assert table["share"].tolist() == pytest.approx([0.5, 0.3, 0.1, 0.1])
    assert table["cum_share"].tolist() == pytest.approx([0.5, 0.8, 0.9, 1.0])


def test_pareto_breaks_ties_alphabetically():
    table = pareto(pd.Series(["B", "A", "B", "A", "C"]))
    assert table["label"].tolist() == ["A", "B", "C"]


def test_top_n_share_ignores_labels_listed_as_last():
    labels = pd.Series(["Unknown"] * 6 + ["A"] * 2 + ["B"] + ["C"] + ["D"] * 0)
    table = pareto(labels, last=["Unknown"])
    # Top 3 real modes are A, B, C: 4 of 10 mentions, even though Unknown is the largest.
    assert top_n_share(table, 3, last=["Unknown"]) == pytest.approx(0.4)


def test_code_failure_mode_first_matching_rule_wins():
    rules = [("Wiring", r"\bWIR(E|ING)\b"), ("Thermal", r"\bSMOKE|\bBURN")]
    text = pd.Series(
        [
            "Smoke came from the wiring behind the seat",  # both match, priority 1 wins
            "burning smell from the vents",
            "the wireless charger stopped",  # WIRE inside WIRELESS must not match
            "",
        ]
    )
    assert code_failure_mode(text, rules).tolist() == [
        "Wiring",
        "Thermal",
        "Not coded",
        "Not coded",
    ]


def test_trend_by_model_year_counts_and_share():
    mentions = pd.DataFrame(
        {
            "ODINO": ["1", "1", "2", "3", "4"],
            "MODELTXT": ["A", "A", "A", "A", "A"],
            "YEARTXT": ["2021", "2021", "2021", "2022", "2022"],
            "group": ["Electrical", "Steering", "Steering", "Electrical", "Electrical"],
        }
    )
    out = trend_by_model_year(mentions, "group", "Electrical").set_index("YEARTXT")
    assert out.loc["2021", "complaints"] == 2
    assert out.loc["2021", "target_complaints"] == 1
    assert out.loc["2021", "target_share"] == pytest.approx(0.5)
    assert out.loc["2022", "target_share"] == pytest.approx(1.0)


def test_published_taxonomy_and_rules_load():
    taxonomy = load_taxonomy()
    assert taxonomy["ELECTRICAL SYSTEM"] == "Electrical system"
    assert taxonomy["UNKNOWN OR OTHER"] == "Unknown or other"
    rules = load_failure_mode_rules()
    assert rules[0][0].startswith("Charging unit")
    assert len(rules) == 8
