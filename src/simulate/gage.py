"""Simulated crossed Gage R&R study for the crimp height gauge.

10 parts drawn from the crimp process, measured 3 times each by 3 operators. Each operator has
a fixed bias (drawn once), and every reading adds repeatability noise; readings are rounded to
the gauge resolution. The true settings go to a separate truth file.

Usage:
    python -m src.simulate.gage     # writes data/simulated/gage_study.csv and gage_truth.json
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "simulated"
COLUMNS = ["part", "operator", "trial", "crimp_height_mm"]


@dataclass(frozen=True)
class GageConfig:
    seed: int = 20261127
    parts: int = 10
    operators: tuple[str, ...] = ("A", "B", "C")
    trials: int = 3
    process_mean: float = 1.80
    process_sigma: float = 0.010  # spread of the parts, same as the crimp process
    repeatability_sigma: float = 0.0020
    operator_sigma: float = 0.0012  # spread of operator biases
    resolution: float = 0.001
    tolerance: float = 0.10


def simulate_study(cfg: GageConfig | None = None) -> tuple[pd.DataFrame, dict]:
    """Return the study table and the hidden truth."""
    cfg = cfg or GageConfig()
    rng = np.random.default_rng(cfg.seed)
    true_parts = cfg.process_mean + cfg.process_sigma * rng.standard_normal(cfg.parts)
    biases = cfg.operator_sigma * rng.standard_normal(len(cfg.operators))
    rows = []
    for trial in range(1, cfg.trials + 1):
        for op, bias in zip(cfg.operators, biases, strict=True):
            for part, true_value in enumerate(true_parts, start=1):
                noise = cfg.repeatability_sigma * rng.standard_normal()
                rows.append((part, op, trial, true_value + bias + noise))
    df = pd.DataFrame(rows, columns=COLUMNS).sort_values(["part", "operator", "trial"])
    df["crimp_height_mm"] = (
        (df["crimp_height_mm"] / cfg.resolution).round() * cfg.resolution
    ).round(6)
    grr_var = cfg.repeatability_sigma**2 + cfg.operator_sigma**2
    total_var = grr_var + cfg.process_sigma**2
    truth = {
        "seed": cfg.seed,
        "config": asdict(cfg),
        "true_part_values_mm": [round(float(v), 6) for v in true_parts],
        "operator_bias_mm": {
            op: round(float(b), 6) for op, b in zip(cfg.operators, biases, strict=True)
        },
        "population": {
            "gage_rr_sd": math.sqrt(grr_var),
            "pct_study_var": 100 * math.sqrt(grr_var / total_var),
            "pct_tolerance": 100 * 6 * math.sqrt(grr_var) / cfg.tolerance,
            "ndc": math.floor(1.41 * cfg.process_sigma / math.sqrt(grr_var)),
        },
    }
    return df.reset_index(drop=True), truth


def write_outputs(cfg: GageConfig | None = None, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    df, truth = simulate_study(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path, truth_path = out_dir / "gage_study.csv", out_dir / "gage_truth.json"
    df.to_csv(data_path, index=False, lineterminator="\n")
    truth_path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return data_path, truth_path


def main() -> None:
    data_path, truth_path = write_outputs()
    print(f"wrote {data_path.relative_to(ROOT)} and {truth_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
