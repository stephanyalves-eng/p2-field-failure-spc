"""Known-answer tests for the NHTSA flat-file reader and model filter.

The fixtures are tiny hand-made zip files laid out like the official files:
tab delimited, no header, one row per complaint (or recall) and component.
"""

import zipfile

import pytest

from src.data.download_nhtsa import (
    COMPLAINT_COLUMNS,
    COMPLAINT_KEEP,
    MODELS,
    RECALL_COLUMNS,
    RECALL_KEEP,
    filter_models,
    read_flat_zip,
)


def _row(columns, **values):
    return "\t".join(values.get(col, "") for col in columns)


def _write_zip(path, columns, rows):
    text = "\n".join(_row(columns, **r) for r in rows) + "\n"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(path.stem + ".txt", text)
    return path


COMPLAINTS = [
    # Same complaint (ODINO 1) filed against two components: two rows, one complaint.
    dict(
        CMPLID="10",
        ODINO="1",
        MAKETXT="HYUNDAI",
        MODELTXT="IONIQ 5",
        YEARTXT="2022",
        COMPDESC="ELECTRICAL SYSTEM",
        CITY="SOMEWHERE",
        VIN="KM8KM4AE0NU",
        VEHICLE_OPERATOR="JANE DOE",
    ),
    dict(
        CMPLID="11",
        ODINO="1",
        MAKETXT="HYUNDAI",
        MODELTXT="IONIQ 5",
        YEARTXT="2022",
        COMPDESC="ELECTRICAL SYSTEM: 12V/24V/48V BATTERY",
    ),
    dict(CMPLID="12", ODINO="2", MAKETXT="TESLA", MODELTXT="MODEL 3", YEARTXT="2021"),
    # Variants that must not match: different model names of the same family.
    dict(CMPLID="13", ODINO="3", MAKETXT="HYUNDAI", MODELTXT="IONIQ 5 N", YEARTXT="2025"),
    dict(CMPLID="14", ODINO="4", MAKETXT="CHEVROLET", MODELTXT="BOLT EUV", YEARTXT="2022"),
    dict(CMPLID="15", ODINO="5", MAKETXT="TOYOTA", MODELTXT="CAMRY", YEARTXT="2020"),
    # Lowercase or padded text in the file still matches.
    dict(CMPLID="16", ODINO="6", MAKETXT="ford ", MODELTXT="Mustang Mach E", YEARTXT="2023"),
]


@pytest.fixture
def complaints_zip(tmp_path):
    return _write_zip(tmp_path / "COMPLAINTS_TEST.zip", COMPLAINT_COLUMNS, COMPLAINTS)


def test_layouts_match_the_official_field_counts():
    assert len(COMPLAINT_COLUMNS) == 51
    assert len(RECALL_COLUMNS) == 29


def test_read_flat_zip_reads_every_row_as_text(complaints_zip):
    df = read_flat_zip(complaints_zip, COMPLAINT_COLUMNS)
    assert len(df) == 7
    assert list(df.columns) == COMPLAINT_COLUMNS
    assert df.loc[0, "YEARTXT"] == "2022"  # kept as text, not parsed to int


def test_read_flat_zip_keeps_quotes_literal(tmp_path):
    rows = [dict(CMPLID="1", ODINO="1", CDESCR='CAR SAID "CHECK EV SYSTEM" AND STOPPED')]
    path = _write_zip(tmp_path / "Q.zip", COMPLAINT_COLUMNS, rows)
    df = read_flat_zip(path, COMPLAINT_COLUMNS)
    assert df.loc[0, "CDESCR"] == 'CAR SAID "CHECK EV SYSTEM" AND STOPPED'


def test_filter_models_keeps_exact_models_only(complaints_zip):
    df = read_flat_zip(complaints_zip, COMPLAINT_COLUMNS)
    out = filter_models(df, MODELS)
    assert sorted(out["CMPLID"]) == ["10", "11", "12", "16"]
    assert out["ODINO"].nunique() == 3  # three complaints, four component rows


def test_filter_models_normalizes_make_and_model_text(complaints_zip):
    df = read_flat_zip(complaints_zip, COMPLAINT_COLUMNS)
    out = filter_models(df, MODELS)
    row = out[out["CMPLID"] == "16"].iloc[0]
    assert (row["MAKETXT"], row["MODELTXT"]) == ("FORD", "MUSTANG MACH E")


def test_complaint_output_drops_personal_data():
    for col in ("CITY", "VIN", "DEALER_NAME", "DEALER_TEL", "VEHICLE_OPERATOR"):
        assert col not in COMPLAINT_KEEP
    assert set(COMPLAINT_KEEP) <= set(COMPLAINT_COLUMNS)
    assert set(RECALL_KEEP) <= set(RECALL_COLUMNS)


def test_models_are_the_four_scoped_vehicles():
    assert set(MODELS) == {
        ("HYUNDAI", "IONIQ 5"),
        ("FORD", "MUSTANG MACH E"),
        ("TESLA", "MODEL 3"),
        ("CHEVROLET", "BOLT EV"),
    }
