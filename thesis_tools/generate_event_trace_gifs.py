"""
Generate a small set of event-trace GIFs for the thesis animation style.

This is intentionally parameterized so the generated GIFs match your experiment
cells (env, density, EMS preset, acceptance tier, responder count).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_experiment_grid_constants() -> Any:
    from src.cfr_sim import experiment_grid as mod

    return mod


@dataclass(frozen=True)
class TraceScenario:
    env_name: str
    density_label: str
    acceptance_label: str
    ems_preset: str
    policy_names: list[str]
    run_id: int
    output_dir: Path


def _compute_trace_seed_for_slice(mod: Any, env_name: str, density_label: str, acceptance_label: str, run_id: int) -> int:
    """
    Match the seeding scheme in `main.run_experiment_grid()` for the typical slice run:
      - environments=[env_name]
      - densities_by_env includes only `density_label`
      - ems_scenarios has only one key (fixed)
      - speed_scenarios has only "baseline"
    """
    base_seed = 123456

    env_index = 0
    density_index = 0
    ems_index = 0
    speed_index = 0

    acceptance_keys = list(mod.THESIS_ACCEPTANCE_SCENARIOS.keys())
    if acceptance_label not in mod.THESIS_ACCEPTANCE_SCENARIOS:
        raise ValueError(f"Unknown acceptance label: {acceptance_label}. Valid: {acceptance_keys}")
    acc_index = acceptance_keys.index(acceptance_label)

    # Mirrors main.run_experiment_grid():
    # seed = base_seed + 10_000*env_index + 1_000*density_index + 100*ems_index + 10*speed_index + acc_index + run_id
    return int(base_seed + 10_000 * env_index + 1_000 * density_index + 100 * ems_index + 10 * speed_index + acc_index + run_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=["urban", "rural"], required=True)
    parser.add_argument("--density", required=True)
    parser.add_argument("--acceptance", required=True)
    parser.add_argument("--ems-preset", required=True, choices=["5_10", "10_15", "15_20"])
    parser.add_argument(
        "--policy",
        action="append",
        required=True,
        help="May be repeated. Example: --policy \"Mobile Lifesaver\" --policy GoodSAM",
    )
    parser.add_argument("--run-id", type=int, default=1, help="Which Monte Carlo run-id seed to visualize.")
    parser.add_argument("--output-dir", type=Path, default=Path("results/gifs"))
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--num-frames", type=int, default=60)
    parser.add_argument("--interval-ms", type=int, default=100)
    args = parser.parse_args()

    # Ensure repo root is importable.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    mod = _load_experiment_grid_constants()

    # Validate density label against chosen environment.
    dens_map = mod.THESIS_DENSITIES_BY_ENV[args.env]
    if args.density not in dens_map:
        raise ValueError(f"Unknown density label {args.density!r} for env {args.env!r}. Valid: {list(dens_map.keys())}")

    num_responders = int(dens_map[args.density])

    acceptance_cfg = mod.THESIS_ACCEPTANCE_SCENARIOS[args.acceptance]
    ems_cfg = mod.THESIS_EMS_PRESETS[args.ems_preset][args.env]
    amb_mean = float(ems_cfg["mean"])
    amb_std = float(ems_cfg["std"])

    seed = _compute_trace_seed_for_slice(
        mod=mod,
        env_name=args.env,
        density_label=args.density,
        acceptance_label=args.acceptance,
        run_id=int(args.run_id),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    from src.cfr_sim.simulation import run_single_event_trace
    from src.cfr_sim.analysis import animate_event_trace

    for policy_name in args.policy:
        trace = run_single_event_trace(
            policy_name=policy_name,
            env_name=args.env,
            num_responders=num_responders,
            env_overrides=None,
            ambulance_mean=amb_mean,
            ambulance_std=amb_std,
            acceptance_cfg=acceptance_cfg,
            seed=seed,
            # We keep the schematic-view parameters at their defaults
            # so GIFs share the same look-and-feel across policies.
        )

        out_name = (
            f"trace_{policy_name.replace(' ', '_')}_{args.env}_{args.density}"
            f"_ems{args.ems_preset}_{args.acceptance}_run{args.run_id}.gif"
        )
        save_path = args.output_dir / out_name

        animate_event_trace(
            trace,
            interval_ms=int(args.interval_ms),
            num_frames=int(args.num_frames),
            save_path=str(save_path),
            dpi=int(args.dpi),
            fps=int(args.fps),
            show=False,
        )

        print(f"Saved GIF: {save_path}")


if __name__ == "__main__":
    main()

