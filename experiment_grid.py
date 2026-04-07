"""
Thesis experimental grids after the urban/rural archetype parameter update.

Main chapter grid — five density levels and six acceptance tiers; EMS held fixed per environment:
    2 environments × 5 density regimes × 6 acceptance tiers × 1 EMS setting
  = 60 scenario cells per policy (travel friction fixed at baseline).

Secondary travel-friction sweep (EMS + acceptance at baseline; five friction levels):
    2 environments × 5 densities × 5 travel factors
  = 50 cells per policy.

Outputs default to results/thesis_archetype_grid/ (see THESIS_RESULTS_SUBDIR).
"""

from __future__ import annotations

import os
from typing import Any, Dict

# ----------------------------------------------------------------------------
# EMS presets for thesis sensitivity runs.
#
# By default, THESIS_EMS_FIXED uses the values below (current repo default).
# If THESIS_EMS_PRESET is set to one of the keys here (e.g. "10_15"), that
# preset overrides THESIS_EMS_FIXED.
# ----------------------------------------------------------------------------
# Marginal mean/std (minutes) for lognormal EMS times; urban σ ∈ {2,3,4}, rural σ ∈ {3,5,6} by preset.
THESIS_EMS_PRESETS: Dict[str, Dict[str, Dict[str, float]]] = {
    "5_10": {
        "urban": {"mean": 5.0, "std": 2.0},
        "rural": {"mean": 10.0, "std": 3.0},
    },
    "10_15": {
        "urban": {"mean": 10.0, "std": 3.0},
        "rural": {"mean": 15.0, "std": 5.0},
    },
    "15_20": {
        "urban": {"mean": 15.0, "std": 4.0},
        "rural": {"mean": 20.0, "std": 6.0},
    },
}

# ---------------------------------------------------------------------------
# Output folder (all runs after the archetype / EMS / speed update)
# ---------------------------------------------------------------------------
THESIS_RESULTS_SUBDIR = os.path.join("results", "thesis_archetype_grid")

# ---------------------------------------------------------------------------
# Responder counts as proxies for sparse / moderate / dense *availability*
# (literature often states responders/km²; counts map to regimes, not a named city).
# ---------------------------------------------------------------------------
# Five density labels (same keys per environment); counts proxy coverage regimes.
THESIS_DENSITIES_BY_ENV: Dict[str, Dict[str, int]] = {
    "urban": {
        "low": 10,
        "mid_low": 25,
        "medium": 50,
        "mid_high": 75,
        "high": 100,
    },
    "rural": {
        "low": 3,
        "mid_low": 8,
        "medium": 15,
        "mid_high": 22,
        "high": 30,
    },
}

# Same label order for both environments (used for batched slice filenames / merge).
THESIS_DENSITY_LABELS: tuple[str, ...] = tuple(THESIS_DENSITIES_BY_ENV["urban"].keys())

# ---------------------------------------------------------------------------
# EMS: single literature-aligned archetype per environment (not factorial).
# Distinct urban vs rural mean/std; main experiments vary density + acceptance only.
# ---------------------------------------------------------------------------
THESIS_EMS_FIXED_DEFAULT = {
    "urban": {"mean": 5.0, "std": 2.0},
    "rural": {"mean": 10.0, "std": 3.0},
}

_ems_preset_env = os.environ.get("THESIS_EMS_PRESET")
if _ems_preset_env in THESIS_EMS_PRESETS:
    THESIS_EMS_FIXED = THESIS_EMS_PRESETS[_ems_preset_env]
else:
    THESIS_EMS_FIXED = THESIS_EMS_FIXED_DEFAULT
THESIS_EMS_SCENARIOS = {"fixed": THESIS_EMS_FIXED}

# ---------------------------------------------------------------------------
# Acceptance: six tiers (uniform ranges per type).
# - CPR bands have width 0.04 (4 percentage points).
# - Tier lower bounds start at 0.06 and advance by 0.10 each tier (10 percentage-point gaps).
# - `none` and `professional` bands are shifted relative to CPR so the tier structure stays consistent.
# ---------------------------------------------------------------------------
THESIS_ACCEPTANCE_SCENARIOS = {
    "acc_v1": {
        "none": (0.03, 0.07),
        "cpr": (0.06, 0.10),
        "professional": (0.13, 0.17),
    },
    "acc_v2": {
        "none": (0.13, 0.17),
        "cpr": (0.16, 0.20),
        "professional": (0.23, 0.27),
    },
    "acc_v3": {
        "none": (0.23, 0.27),
        "cpr": (0.26, 0.30),
        "professional": (0.33, 0.37),
    },
    "acc_v4": {
        "none": (0.33, 0.37),
        "cpr": (0.36, 0.40),
        "professional": (0.43, 0.47),
    },
    "acc_v5": {
        "none": (0.43, 0.47),
        "cpr": (0.46, 0.50),
        "professional": (0.53, 0.57),
    },
    "acc_v6": {
        "none": (0.53, 0.57),
        "cpr": (0.56, 0.60),
        "professional": (0.63, 0.67),
    },
}

# Travel friction multipliers (secondary analysis): scales speed_mean / speed_std.
THESIS_TRAVEL_FRICTION = {
    "trav_v1": {"factor": 0.60},
    "trav_v2": {"factor": 0.80},
    "trav_v3": {"factor": 1.00},
    "trav_v4": {"factor": 1.20},
    "trav_v5": {"factor": 1.40},
}

# Cell counts (for thesis text / sanity checks)
THESIS_MAIN_GRID_CELLS = 2 * 5 * 6  # 60; EMS not varied
THESIS_TRAVEL_GRID_CELLS = 2 * 5 * 5  # 50


def thesis_main_grid_kwargs(
    num_runs: int | None = None,
    results_folder: str | None = None,
) -> Dict[str, Any]:
    """Keyword arguments for run_experiment_grid — main 60-cell grid (EMS fixed)."""
    from config import SIM_RUNS, TOTAL_EVENTS_PER_REPLICATION

    return {
        "environments": ["urban", "rural"],
        "densities_by_env": THESIS_DENSITIES_BY_ENV,
        "ems_scenarios": THESIS_EMS_SCENARIOS,
        "speed_scenarios": {"baseline": {"factor": 1.0}},
        "acceptance_scenarios": THESIS_ACCEPTANCE_SCENARIOS,
        "total_events": TOTAL_EVENTS_PER_REPLICATION,
        "num_runs": num_runs if num_runs is not None else SIM_RUNS,
        "results_folder": results_folder or THESIS_RESULTS_SUBDIR,
        "save_combined_csv": True,
        "log_every_iterations": 1,
        "distance_mode": "uniform_1km",
        "max_distance_km": 1.0,
    }


def thesis_travel_sensitivity_kwargs(
    num_runs: int | None = None,
    results_folder: str | None = None,
) -> Dict[str, Any]:
    """
    Secondary grid: vary travel friction only; EMS and acceptance at baseline tiers.
    2 × 5 density × 5 friction = 50 cells per policy.
    """
    from config import SIM_RUNS, TOTAL_EVENTS_PER_REPLICATION

    out = os.path.join(
        results_folder or THESIS_RESULTS_SUBDIR,
        "travel_friction_sensitivity",
    )
    return {
        "environments": ["urban", "rural"],
        "densities_by_env": THESIS_DENSITIES_BY_ENV,
        "ems_scenarios": THESIS_EMS_SCENARIOS,
        "speed_scenarios": THESIS_TRAVEL_FRICTION,
        "acceptance_scenarios": {"acc_v3": THESIS_ACCEPTANCE_SCENARIOS["acc_v3"]},
        "total_events": TOTAL_EVENTS_PER_REPLICATION,
        "num_runs": num_runs if num_runs is not None else SIM_RUNS,
        "results_folder": out,
        "save_combined_csv": True,
        "log_every_iterations": 1,
        "distance_mode": "uniform_1km",
        "max_distance_km": 1.0,
    }


def run_thesis_main_grid(**overrides: Any):
    """Run the primary 60-cell thesis grid; passes overrides to kwargs."""
    from main import run_experiment_grid

    kw = thesis_main_grid_kwargs()
    kw.update(overrides)
    os.makedirs(kw["results_folder"], exist_ok=True)
    return run_experiment_grid(**kw)


def run_thesis_travel_sensitivity(**overrides: Any):
    from main import run_experiment_grid

    kw = thesis_travel_sensitivity_kwargs()
    kw.update(overrides)
    os.makedirs(kw["results_folder"], exist_ok=True)
    return run_experiment_grid(**kw)


if __name__ == "__main__":
    print("Running thesis MAIN grid (60 cells × runs × policies)...")
    print(f"Outputs -> {thesis_main_grid_kwargs()['results_folder']}")
    df = run_thesis_main_grid()
    print(df.shape)
