"""Known-answer tests for the FAA SDR reader, A320 family / ATA 24 filter and part mapping."""

import pandas as pd
import pytest

from src.data.download_faa_sdr import KEEP, filter_a320_ata24, read_sdr_csv
from src.field import load_jasc_titles, load_part_groups, map_values

HEADER = (
    "OperatorControlNumber,DifficultyDate,JASCCode,AircraftMake,AircraftModel,"
    "RegistryNNumber,AircraftSerialNumber,PartName,PartCondition,Discrepancy"
)
ROWS = [
    'A1,01/02/2024,2421,AIRBUS,A320232,N1,1,IDG,FAILED,"IDG #2 FAULT, REPLACED"',
    "A2,01/03/2024,2497,AIRBUS,A321271NX,N2,2,WIRE HARNESS,CHAFED,WIRE CHAFED",
    "A3,01/04/2024,2421,AIRBUS,A330323,N3,3,IDG,FAILED,WIDEBODY - OUT",
    "A4,01/05/2024,3200,AIRBUS,A319114,N4,4,STRUT,CRACKED,NOT ATA 24 - OUT",
    "A5,01/06/2024,2450,airbus ,a318112,N5,5,contactor ,FAULTED,LOWER CASE MAKE AND MODEL",
    "A6,01/07/2024,2421,BOEING,737824,N6,6,IDG,FAILED,OTHER MAKE - OUT",
    'A7,01/08/2024,2400,AIRBUS,A320214,N7,7,UNKNOWN,ODOR,"ELECTRICAL ODOR ""HOT PLASTIC"""',
]


@pytest.fixture
def sdr_csv(tmp_path):
    path = tmp_path / "SDR-TEST.csv"
    path.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8")
    return path


def test_read_sdr_csv_keeps_text_and_quoted_commas(sdr_csv):
    df = read_sdr_csv(sdr_csv)
    assert len(df) == 7
    assert df.loc[0, "Discrepancy"] == "IDG #2 FAULT, REPLACED"
    assert df.loc[6, "Discrepancy"] == 'ELECTRICAL ODOR "HOT PLASTIC"'
    assert df.loc[0, "JASCCode"] == "2421"


def test_filter_keeps_a318_to_a321_including_neo_and_ata_24_only(sdr_csv):
    out = filter_a320_ata24(read_sdr_csv(sdr_csv))
    assert out["OperatorControlNumber"].tolist() == ["A1", "A2", "A5", "A7"]


def test_filter_normalizes_text_fields(sdr_csv):
    out = filter_a320_ata24(read_sdr_csv(sdr_csv)).set_index("OperatorControlNumber")
    assert out.loc["A5", "AircraftMake"] == "AIRBUS"
    assert out.loc["A5", "AircraftModel"] == "A318112"
    assert out.loc["A5", "PartName"] == "CONTACTOR"


def test_output_drops_aircraft_identifiers(sdr_csv):
    out = filter_a320_ata24(read_sdr_csv(sdr_csv))
    assert "RegistryNNumber" not in KEEP and "AircraftSerialNumber" not in KEEP
    assert list(out.columns) == KEEP


def test_map_values_fails_loudly_on_unmapped():
    assert map_values(pd.Series(["IDG"]), {"IDG": "Gen"}).tolist() == ["Gen"]
    with pytest.raises(KeyError, match="NEW PART"):
        map_values(pd.Series(["NEW PART"]), {"IDG": "Gen"})


def test_published_sdr_mappings_load():
    titles = load_jasc_titles()
    assert titles["2421"] == "AC GENERATOR-ALTERNATOR"
    assert titles["2497"] == "ELECTRICAL POWER SYSTEM WIRING"
    groups = load_part_groups()
    assert groups["IDG"] == "Generator and drive (IDG)"
    assert groups["WIRE HARNESS"] == "Wiring, connector or terminal"
