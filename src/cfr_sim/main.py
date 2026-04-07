import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
from typing import Any, AbstractSet, Dict, Optional

from .policies import CFR_POLICIES
from .simulation import run_simulation_batch
from .analysis import summarize_results, plot_first_arrival_distribution, plot_alerts_distribution, plot_success_rate_over_threshold, dashboard_of_dashboards
from .config import NUM_RESPONDERS, SIM_RUNS, TOTAL_EVENTS_PER_REPLICATION, ENVIRONMENTS


def _resolve_ems_cfg(ems_cfg: Dict[str, Any], env_name: str, base_env: Dict[str, Any]):
    """
    Resolve ambulance mean/std for this environment (marginal moments for lognormal EMS times).

    Supports:
    - Per-environment nested dicts: {'urban': {'mean': 10, 'std': 1.5}, 'rural': {...}}
    - Offset from env baseline: {'offset': d} or per-env {'urban': {'offset': d, 'std': ...}}
    - Explicit global mean/std: {'mean': ..., 'std': ...}
    - Env defaults: {'mean': None, 'std': None}
    """
    if env_name in ems_cfg and isinstance(ems_cfg[env_name], dict):
        sub = ems_cfg[env_name]
        if "offset" in sub:
            amb_mean = base_env["ambulance_mean"] + sub["offset"]
            amb_std = sub["std"] if sub.get("std") is not None else base_env["ambulance_std"]
            return amb_mean, amb_std
        if sub.get("mean") is not None or sub.get("std") is not None:
            amb_mean = sub["mean"] if sub.get("mean") is not None else base_env["ambulance_mean"]
            amb_std = sub["std"] if sub.get("std") is not None else base_env["ambulance_std"]
            return amb_mean, amb_std
    if "offset" in ems_cfg:
        amb_mean = base_env["ambulance_mean"] + ems_cfg["offset"]
        amb_std = (
            ems_cfg["std"]
            if ems_cfg.get("std") is not None
            else base_env["ambulance_std"]
        )
        return amb_mean, amb_std
    if ems_cfg.get("mean") is None and ems_cfg.get("std") is None:
        return base_env["ambulance_mean"], base_env["ambulance_std"]
    return ems_cfg["mean"], ems_cfg["std"]

try:
    import seaborn as sns
except ModuleNotFoundError:
    sns = None

# sns.set(style="whitegrid")

# for LaTeX-style plots
plt.rcParams.update({
    "text.usetex": False,                 
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],       
    "mathtext.fontset": "cm",             

    "figure.dpi": 300,

    "axes.linewidth": 1.0,
    "axes.grid": True,
    "grid.color": "#cccccc",
    "grid.linewidth": 0.7,
    "grid.alpha": 0.6,
    "grid.linestyle": "-",

    "xtick.major.size": 6,
    "ytick.major.size": 6,
    "xtick.direction": "inout",
    "ytick.direction": "inout",

    "lines.linewidth": 2.0,
    "lines.markersize": 6,

    "axes.facecolor": "white",
})

colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52",
          "#8172B2", "#937860", "#DA8BC3"]


def run_experiment_grid(
    environments=None,
    densities=None,
    densities_by_env: Optional[Dict[str, Dict[str, int]]] = None,
    ems_scenarios=None,
    speed_scenarios=None,
    acceptance_scenarios=None,
    total_events=TOTAL_EVENTS_PER_REPLICATION,
    num_runs=SIM_RUNS,
    results_folder="results",
    distance_mode="uniform_1km",
    max_distance_km=1.0,
    phased_step_minutes=0.5,
    max_alert_minutes=10.0,
    save_combined_csv=True,
    log_every_iterations=1,
    exclude_policies: AbstractSet[str] = frozenset({"Random"}),
    event_level_output=True,
):
    """
    Run a policy x environment x responder-density x Monte Carlo grid and return a single combined DataFrame.

    - exclude_policies: policy names not to simulate. Default ``frozenset({'Random'})`` skips the Random baseline.
      Pass ``frozenset()`` to run every policy including Random.

    - environments: list like ['urban', 'rural']
    - densities: dict label -> num_responders (same counts for every environment)
    - densities_by_env: optional dict env_name -> {label -> num_responders}; if set, overrides ``densities``
    - ems_scenarios: dict label -> per-scenario EMS config. Each value may be:
      {'mean': ..., 'std': ...} (absolute minutes),
      {'offset': d} (minutes added to that environment's baseline mean),
      {'mean': None, 'std': None} to use ENVIRONMENTS[env] ambulance_mean/std, or
      {'urban': {'mean': ..., 'std': ...}, 'rural': {...}} for per-environment absolute EMS
    - speed_scenarios: dict label -> {'factor': ...} scaling speed_mean/speed_std
    - acceptance_scenarios: dict label -> per-type acceptance ranges
    - total_events: OHCA events per replication (default from config, typically 1000)
    - num_runs: Monte Carlo runs per scenario cell
    - event_level_output: when True (default), keep event-level rows.
      Set False for run-level rows only (much smaller/faster).
    """
    if environments is None:
        environments = ["urban", "rural"]

    if densities_by_env is not None:
        density_labels = list(next(iter(densities_by_env.values())).keys())
        for env_name in environments:
            if env_name not in densities_by_env:
                raise ValueError(f"densities_by_env missing key {env_name!r}")
            if set(densities_by_env[env_name].keys()) != set(density_labels):
                raise ValueError("densities_by_env must use the same density labels for each environment")
    else:
        if densities is None:
            densities = {
                "low": 10,
                "medium": NUM_RESPONDERS,
                "high": 2 * NUM_RESPONDERS,
            }
        density_labels = list(densities.keys())

    if ems_scenarios is None:
        # None -> use literature-aligned EMS for each environment (config.ENVIRONMENTS).
        ems_scenarios = {
            "baseline": {"mean": None, "std": None},
        }

    if speed_scenarios is None:
        speed_scenarios = {
            "baseline": {"factor": 1.0},
        }

    if acceptance_scenarios is None:
        acceptance_scenarios = {
            "baseline": {
                "none": (0.05, 0.15),
                "cpr": (0.10, 0.30),
                "professional": (0.30, 0.50),
            },
        }

    all_policies = {**CFR_POLICIES}
    _excluded = frozenset(exclude_policies)
    policy_names = tuple(p for p in all_policies if p not in _excluded)
    if not policy_names:
        raise ValueError("No policies left to run after exclude_policies.")
    # Event-level output can produce tens of millions of rows and dominate runtime with I/O.
    _concat_batch = 256
    _pending: list[pd.DataFrame] = []
    _chunks: list[pd.DataFrame] = []

    total_iterations = (
        len(environments)
        * len(density_labels)
        * len(ems_scenarios)
        * len(speed_scenarios)
        * len(acceptance_scenarios)
        * num_runs
    )
    completed_iterations = 0

    # Precompute index maps for deterministic seeding
    env_index = {name: idx for idx, name in enumerate(environments)}
    density_index = {label: idx for idx, label in enumerate(density_labels)}
    ems_index = {label: idx for idx, label in enumerate(ems_scenarios.keys())}
    speed_index = {label: idx for idx, label in enumerate(speed_scenarios.keys())}
    acc_index = {label: idx for idx, label in enumerate(acceptance_scenarios.keys())}
    base_seed = 123456

    for env_name in environments:
        base_env = ENVIRONMENTS[env_name]
        for density_label in density_labels:
            if densities_by_env is not None:
                n_resp = densities_by_env[env_name][density_label]
            else:
                n_resp = densities[density_label]
            for ems_label, ems_cfg in ems_scenarios.items():
                for speed_label, speed_cfg in speed_scenarios.items():
                    for acc_label, acc_cfg in acceptance_scenarios.items():
                        # Build environment overrides for this scenario (e.g., faster/slower travel).
                        factor = speed_cfg.get("factor", 1.0)
                        env_overrides = {
                            "speed_mean": base_env["speed_mean"] * factor,
                            "speed_std": base_env["speed_std"] * factor,
                        }
                        amb_mean, amb_std = _resolve_ems_cfg(ems_cfg, env_name, base_env)

                        for run_id in range(1, num_runs + 1):
                            completed_iterations += 1
                            remaining_iterations = total_iterations - completed_iterations
                            # Deterministic seed per scenario cell and run
                            seed = (
                                base_seed
                                + 10_000 * env_index[env_name]
                                + 1_000 * density_index[density_label]
                                + 100 * ems_index[ems_label]
                                + 10 * speed_index[speed_label]
                                + acc_index[acc_label]
                                + run_id
                            )
                            should_log = (
                                log_every_iterations <= 1
                                or completed_iterations % log_every_iterations == 0
                                or completed_iterations == 1
                                or completed_iterations == total_iterations
                            )
                            if should_log:
                                print(
                                    f"\n[{completed_iterations}/{total_iterations}] "
                                    f"(remaining: {remaining_iterations}) "
                                    f"=== Env: {env_name} | Density: {density_label} ({n_resp}) | "
                                    f"EMS: {ems_label} (mu={amb_mean}, sigma={amb_std}) | "
                                    f"Speed: {speed_label} (x{factor}) | "
                                    f"Accept: {acc_label} | Run: {run_id}/{num_runs} | Seed: {seed} ==="
                                )
                            dfs = run_simulation_batch(
                                policy_names,
                                env_name=env_name,
                                num_responders=n_resp,
                                total_events=total_events,
                                env_overrides=env_overrides,
                                ambulance_mean=amb_mean,
                                ambulance_std=amb_std,
                                acceptance_cfg=acc_cfg,
                                seed=seed,
                                distance_mode=distance_mode,
                                max_distance_km=max_distance_km,
                                phased_step_minutes=phased_step_minutes,
                                max_alert_minutes=max_alert_minutes,
                                verbose=False,
                                return_event_level=event_level_output,
                            )

                            for policy_name, payload in dfs.items():
                                base_meta = {
                                    "environment": env_name,
                                    "policy": policy_name,
                                    "density_label": density_label,
                                    "num_responders": n_resp,
                                    "ems_label": ems_label,
                                    "ambulance_mean": amb_mean,
                                    "ambulance_std": amb_std,
                                    "speed_label": speed_label,
                                    "speed_mean": env_overrides["speed_mean"],
                                    "speed_std": env_overrides["speed_std"],
                                    "acceptance_label": acc_label,
                                    "run_id": run_id,
                                    "seed": seed,
                                }
                                if event_level_output:
                                    df = payload
                                    for k, v in base_meta.items():
                                        df[k] = v
                                    _pending.append(df)
                                else:
                                    row = {**base_meta, **payload}
                                    _pending.append(pd.DataFrame([row]))

                                if len(_pending) >= _concat_batch:
                                    _chunks.append(pd.concat(_pending, ignore_index=True))
                                    _pending.clear()

    if _pending:
        _chunks.append(pd.concat(_pending, ignore_index=True))
    combined_df = pd.concat(_chunks, ignore_index=True)

    if save_combined_csv:
        os.makedirs(results_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_filename = os.path.join(results_folder, f"combined_results_grid_{timestamp}.csv")
        combined_df.to_csv(combined_filename, index=False)
        print(f"\nSaved grid results to {combined_filename}")

    return combined_df

def dashboard_of_dashboards_demo(combined_df, title="", save=True, results_folder="results"):
    if sns is None:
        raise RuntimeError("dashboard_of_dashboards_demo requires seaborn. Install it with `pip install seaborn`.")
    environments = combined_df['environment'].unique()
    policies = combined_df['policy'].unique()

    max_alerts = combined_df['num_alerted'].max()
    alert_bins = np.arange(0, max_alerts + 2) - 0.5

    fig, axes = plt.subplots(3, 2, figsize=(14, 14), sharey='row')
    plt.subplots_adjust(wspace=0.15, hspace=0.35)

    for col, env_name in enumerate(environments):
        env_df = combined_df[combined_df['environment'] == env_name]
        dfs_env = {policy: env_df[env_df['policy'] == policy].drop(columns=['environment','policy']) 
                   for policy in policies}

        for policy, df in dfs_env.items():
            plot_first_arrival_distribution(df, ax=axes[0, col], label=policy)
            plot_success_rate_over_threshold(df, ax=axes[1, col], label=policy)
            sns.histplot(df['num_alerted'], bins=alert_bins, kde=False, ax=axes[2, col], label=policy)
            axes[2, col].set_xlabel("Number of Responders Alerted")
            axes[2, col].set_ylabel("Frequency")

        axes[0, col].set_title(f"{env_name.capitalize()} - First Arrival")
        axes[1, col].set_title(f"{env_name.capitalize()} - Success Rate")
        axes[2, col].set_title(f"{env_name.capitalize()} - Alerts")

        for ax_row in axes[:, col]:
            if ax_row.get_legend() is not None:
                ax_row.get_legend().remove()

    for row in range(3):
        handles, labels = axes[row, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='upper right',
                   bbox_to_anchor=(1.02, 0.885-row*0.281),
                   ncol=1, fontsize=9, title=None)

    fig.suptitle(title, fontsize=18, y=0.96)

    if save:
        os.makedirs(results_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(results_folder, f"side_by_side_dashboard_{timestamp}.png")
        fig.savefig(filename, bbox_inches='tight', dpi=300)
        print(f"Saved figure to {filename}")

    plt.show()
    return fig

def main():
    # Primary thesis grid (60 cells × SIM_RUNS × policies; EMS fixed per env): see experiment_grid.py
    from .experiment_grid import THESIS_RESULTS_SUBDIR, run_thesis_main_grid

    combined_df = run_thesis_main_grid()
    from .utils import apply_thesis_retroactive_time_adjustment

    combined_df = apply_thesis_retroactive_time_adjustment(combined_df)

    # Print summaries by environment, density level, EMS, speed, acceptance scenario, and policy
    for (env, density, ems_label, speed_label, acc_label, policy), group in combined_df.groupby(
        ["environment", "density_label", "ems_label", "speed_label", "acceptance_label", "policy"]
    ):
        print(f"\n--- {env} | {density} | EMS={ems_label} | Speed={speed_label} | Accept={acc_label} | {policy} ---")
        print(summarize_results(group))

    dashboard_of_dashboards_demo(combined_df, results_folder=THESIS_RESULTS_SUBDIR)

if __name__ == "__main__":
    main()
