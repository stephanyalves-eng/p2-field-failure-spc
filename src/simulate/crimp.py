"""Crimp height process simulator with injected special causes.

The process: terminal crimp height, spec 1.80 +/- 0.05 mm, two crimping machines (A, B),
three shifts, 30 production days, two subgroups of 5 consecutive parts per machine and shift.

Injected special causes (the "hidden truth"):
1. Machine B gets a tool change at the start of `tool_change_day`; from then on its mean
   crimp height is `mean_shift` higher.
2. Shift 3 runs with `shift3_sigma_factor` times the base standard deviation on both machines.

The analysis table (`crimp_height.csv`) has no column that reveals these causes. The true
parameters go to a separate file (`crimp_truth.json`) that the SPC and capability steps may
only use to score themselves after the fact.

Usage:
    python -m src.simulate.crimp     # writes data/simulated/crimp_height.csv and crimp_truth.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "simulated"

COLUMNS = ["subgroup", "day", "shift", "slot", "machine", "part", "crimp_height_mm"]


@dataclass(frozen=True)
class CrimpConfig:
    seed: int = 20261126
    days: int = 30
    machines: tuple[str, ...] = ("A", "B")
    shifts: tuple[str, ...] = ("1", "2", "3")
    subgroups_per_shift: int = 2
    subgroup_size: int = 5
    lsl: float = 1.75
    target: float = 1.80
    usl: float = 1.85
    mean: float = 1.80
    sigma: float = 0.010
    tool_change_machine: str = "B"
    tool_change_day: int = 16
    mean_shift: float = 0.015
    shift3_sigma_factor: float = 1.5
    resolution: float = 0.001  # gauge resolution, mm


def _true_mean(cfg: CrimpConfig, machine: str, day: int) -> float:
    shifted = machine == cfg.tool_change_machine and day >= cfg.tool_change_day
    return cfg.mean + (cfg.mean_shift if shifted else 0.0)


def _true_sigma(cfg: CrimpConfig, shift: str) -> float:
    return cfg.sigma * (cfg.shift3_sigma_factor if shift == "3" else 1.0)


def simulate(cfg: CrimpConfig | None = None) -> pd.DataFrame:
    """Return one row per measured part, in production order."""
    cfg = cfg or CrimpConfig()
    rng = np.random.default_rng(cfg.seed)
    rows = []
    subgroup = 0
    for day in range(1, cfg.days + 1):
        for shift in cfg.shifts:
            for slot in range(1, cfg.subgroups_per_shift + 1):
                for machine in cfg.machines:
                    subgroup += 1
                    mu = _true_mean(cfg, machine, day)
                    sd = _true_sigma(cfg, shift)
                    values = mu + sd * rng.standard_normal(cfg.subgroup_size)
                    for part, value in enumerate(values, start=1):
                        rows.append((subgroup, day, shift, slot, machine, part, value))
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["crimp_height_mm"] = (df["crimp_height_mm"] / cfg.resolution).round() * cfg.resolution
    df["crimp_height_mm"] = df["crimp_height_mm"].round(6)
    return df


def true_parameters(cfg: CrimpConfig | None = None) -> dict:
    """The hidden truth: settings, injected causes and the true capability they imply."""
    cfg = cfg or CrimpConfig()
    tol = cfg.usl - cfg.lsl

    def cpk(mu: float, sd: float) -> float:
        return round(min(cfg.usl - mu, mu - cfg.lsl) / (3 * sd), 3)

    shifted_mean = cfg.mean + cfg.mean_shift
    return {
        "seed": cfg.seed,
        "config": asdict(cfg),
        "spec": {"lsl": cfg.lsl, "target": cfg.target, "usl": cfg.usl},
        "base_process": {
            "mean_mm": cfg.mean,
            "sigma_mm": cfg.sigma,
            "cp": round(tol / (6 * cfg.sigma), 3),
            "cpk": cpk(cfg.mean, cfg.sigma),
        },
        "special_causes": [
            {
                "type": "mean shift after tool change",
                "machine": cfg.tool_change_machine,
                "from_day": cfg.tool_change_day,
                "first_subgroup": first_shifted_subgroup(cfg),
                "mean_shift_mm": cfg.mean_shift,
                "cpk_after": cpk(shifted_mean, cfg.sigma),
            },
            {
                "type": "higher variance",
                "shift": "3",
                "machines": list(cfg.machines),
                "sigma_mm": round(cfg.sigma * cfg.shift3_sigma_factor, 6),
                "sigma_factor": cfg.shift3_sigma_factor,
                "cpk_on_shift": cpk(cfg.mean, cfg.sigma * cfg.shift3_sigma_factor),
            },
        ],
    }


def first_shifted_subgroup(cfg: CrimpConfig) -> int:
    """Subgroup number of machine B's first subgroup after the tool change."""
    per_day = len(cfg.shifts) * cfg.subgroups_per_shift * len(cfg.machines)
    before = (cfg.tool_change_day - 1) * per_day
    return before + 1 + cfg.machines.index(cfg.tool_change_machine)


def write_outputs(cfg: CrimpConfig | None = None, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    cfg = cfg or CrimpConfig()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "crimp_height.csv"
    truth_path = out_dir / "crimp_truth.json"
    simulate(cfg).to_csv(data_path, index=False, lineterminator="\n")
    truth_path.write_text(json.dumps(true_parameters(cfg), indent=2) + "\n", encoding="utf-8")
    return data_path, truth_path


def main() -> None:
    data_path, truth_path = write_outputs()
    print(f"wrote {data_path.relative_to(ROOT)} and {truth_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
