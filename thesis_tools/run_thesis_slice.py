"""
Run one slice of the thesis factorial (one environment at a time) for parallel execution.

Main grid: 5 density × 6 acceptance × 1 EMS × 1 speed = 30 cells per policy per env.
Travel grid: 5 density × 5 travel friction × 1 EMS × 1 acc = 25 cells per policy per env.

Outputs:
  results/thesis_archetype_grid/thesis_main_{urban|rural}.csv   (full 30-cell slice)
  results/thesis_archetype_grid/thesis_main_{urban|rural}_{density}.csv   (--density)
  same pattern for thesis_travel_*   (mode=travel)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cfr_sim.config import SIM_RUNS, TOTAL_EVENTS_PER_REPLICATION  # noqa: E402
from src.cfr_sim.experiment_grid import (  # noqa: E402
    THESIS_ACCEPTANCE_SCENARIOS,
    THESIS_DENSITIES_BY_ENV,
    THESIS_DENSITY_LABELS,
    THESIS_EMS_SCENARIOS,
    THESIS_RESULTS_SUBDIR,
    THESIS_TRAVEL_FRICTION,
    thesis_main_grid_kwargs,
)
from src.cfr_sim.main import run_experiment_grid  # noqa: E402


def _out_path(mode: str, env: str, results_folder: Path, density: str | None) -> Path:
    prefix = "thesis_main" if mode == "main" else "thesis_travel"
    if density is None:
        return results_folder / f"{prefix}_{env}.csv"
    return results_folder / f"{prefix}_{env}_{density}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["urban", "rural"], required=True)
    parser.add_argument(
        "--mode",
        choices=["main", "travel"],
        default="main",
        help="main = 5x6 density x acceptance; travel = 5x5 density x travel friction",
    )
    parser.add_argument("--num-runs", type=int, default=None, help="Override SIM_RUNS")
    parser.add_argument(
        "--results-folder",
        type=Path,
        default=None,
        help=f"Default: project/{THESIS_RESULTS_SUBDIR}",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="If output CSV already exists, exit 0 without re-running.",
    )
    parser.add_argument(
        "--density",
        default=None,
        choices=THESIS_DENSITY_LABELS,
        metavar="LABEL",
        help=(
            "Optional: run only this density regime (6 acceptance tiers in main mode, or "
            "5 travel-friction levels in travel mode, per env). Output becomes "
            "thesis_*_{env}_{LABEL}.csv. Omit for a full slice (30 cells per env in main, "
            "25 in travel): thesis_*_{env}.csv."
        ),
    )
    args = parser.parse_args()

    results_folder = (args.results_folder or (ROOT / THESIS_RESULTS_SUBDIR)).resolve()
    results_folder.mkdir(parents=True, exist_ok=True)
    out_file = _out_path(args.mode, args.environment, results_folder, args.density)

    if args.skip_existing and out_file.exists() and out_file.stat().st_size > 100:
        print(f"Skipping existing: {out_file}")
        return

    env = args.environment
    dens_map = THESIS_DENSITIES_BY_ENV[env]
    if args.density is not None:
        dens_map = {args.density: dens_map[args.density]}
    if args.mode == "main":
        kw = thesis_main_grid_kwargs(
            num_runs=args.num_runs,
            results_folder=str(results_folder),
        )
        kw["environments"] = [env]
        kw["densities_by_env"] = {env: dens_map}
        kw["save_combined_csv"] = False
    else:
        num_runs = args.num_runs if args.num_runs is not None else SIM_RUNS
        kw = {
            "environments": [env],
            "densities_by_env": {env: dens_map},
            "ems_scenarios": THESIS_EMS_SCENARIOS,
            "speed_scenarios": THESIS_TRAVEL_FRICTION,
            "acceptance_scenarios": {"acc_v3": THESIS_ACCEPTANCE_SCENARIOS["acc_v3"]},
            "total_events": TOTAL_EVENTS_PER_REPLICATION,
            "num_runs": num_runs,
            "results_folder": str(results_folder),
            "save_combined_csv": False,
            "log_every_iterations": 1,
            "distance_mode": "uniform_1km",
            "max_distance_km": 1.0,
            "phased_step_minutes": 0.5,
            "max_alert_minutes": 10.0,
        }

    print(f"Running mode={args.mode} env={env} -> {out_file}")
    df = run_experiment_grid(**kw)
    df.to_csv(out_file, index=False)
    print(f"Saved {len(df):,} rows to {out_file}")


if __name__ == "__main__":
    main()
