import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime
from policies import CFR_POLICIES
from simulation import run_simulation_batch
from analysis import summarize_results, plot_first_arrival_distribution, plot_alerts_distribution, plot_success_rate_over_threshold, dashboard_of_dashboards
from config import SIM_DAYS, NUM_RESPONDERS, SIM_RUNS, ENVIRONMENTS, AMBULANCE_MEAN, AMBULANCE_STD

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
    ems_scenarios=None,
    speed_scenarios=None,
    acceptance_scenarios=None,
    num_events_per_day=2,
    sim_days=SIM_DAYS,
    num_runs=SIM_RUNS,
    results_folder="results",
):
    """
    Run a policy x environment x responder-density x Monte Carlo grid and return a single combined DataFrame.

    - environments: list like ['urban', 'rural']
    - densities: dict label -> num_responders, e.g. {'low': 10, 'medium': 30, 'high': 60}
    - ems_scenarios: dict label -> {'mean': ..., 'std': ...}
    - speed_scenarios: dict label -> {'factor': ...} scaling speed_mean/speed_std
    - acceptance_scenarios: dict label -> per-type acceptance ranges
    - num_runs: Monte Carlo runs per scenario cell
    """
    if environments is None:
        environments = ["urban", "rural"]

    if densities is None:
        densities = {
            "low": 10,
            "medium": NUM_RESPONDERS,
            "high": 2 * NUM_RESPONDERS,
        }

    if ems_scenarios is None:
        ems_scenarios = {
            "baseline": {"mean": AMBULANCE_MEAN, "std": AMBULANCE_STD},
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
    all_results = []

    # Precompute index maps for deterministic seeding
    env_index = {name: idx for idx, name in enumerate(environments)}
    density_index = {label: idx for idx, label in enumerate(densities.keys())}
    ems_index = {label: idx for idx, label in enumerate(ems_scenarios.keys())}
    speed_index = {label: idx for idx, label in enumerate(speed_scenarios.keys())}
    acc_index = {label: idx for idx, label in enumerate(acceptance_scenarios.keys())}
    base_seed = 123456

    for env_name in environments:
        base_env = ENVIRONMENTS[env_name]
        for density_label, n_resp in densities.items():
            for ems_label, ems_cfg in ems_scenarios.items():
                for speed_label, speed_cfg in speed_scenarios.items():
                    for acc_label, acc_cfg in acceptance_scenarios.items():
                        # Build environment overrides for this scenario (e.g., faster/slower travel).
                        factor = speed_cfg.get("factor", 1.0)
                        env_overrides = {
                            "speed_mean": base_env["speed_mean"] * factor,
                            "speed_std": base_env["speed_std"] * factor,
                        }
                        amb_mean = ems_cfg["mean"]
                        amb_std = ems_cfg["std"]

                        for run_id in range(1, num_runs + 1):
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
                            print(
                                f"\n=== Env: {env_name} | Density: {density_label} ({n_resp}) | "
                                f"EMS: {ems_label} (μ={amb_mean}, σ={amb_std}) | "
                                f"Speed: {speed_label} (x{factor}) | "
                                f"Accept: {acc_label} | Run: {run_id}/{num_runs} | Seed: {seed} ==="
                            )
                            dfs = run_simulation_batch(
                                all_policies.keys(),
                                env_name=env_name,
                                sim_days=sim_days,
                                num_responders=n_resp,
                                num_events_per_day=num_events_per_day,
                                env_overrides=env_overrides,
                                ambulance_mean=amb_mean,
                                ambulance_std=amb_std,
                                acceptance_cfg=acc_cfg,
                                seed=seed,
                            )

                            for policy_name, df in dfs.items():
                                df = df.copy()
                                df["environment"] = env_name
                                df["policy"] = policy_name
                                df["density_label"] = density_label
                                df["num_responders"] = n_resp
                                df["ems_label"] = ems_label
                                df["ambulance_mean"] = amb_mean
                                df["ambulance_std"] = amb_std
                                df["speed_label"] = speed_label
                                df["speed_mean"] = env_overrides["speed_mean"]
                                df["speed_std"] = env_overrides["speed_std"]
                                df["acceptance_label"] = acc_label
                                df["run_id"] = run_id
                                df["seed"] = seed
                                all_results.append(df)

    combined_df = pd.concat(all_results, ignore_index=True)

    os.makedirs(results_folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_filename = os.path.join(results_folder, f"combined_results_grid_{timestamp}.csv")
    combined_df.to_csv(combined_filename, index=False)
    print(f"\nSaved grid results to {combined_filename}")

    return combined_df

def dashboard_of_dashboards_demo(combined_df, title="", save=True, results_folder="results"):
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
    # default grid:
    # - environments: urban vs rural
    # - responder density: low / medium / high
    # - Monte Carlo repetitions: SIM_RUNS from config.py
    combined_df = run_experiment_grid()

    # Print summaries by environment, density level, EMS, speed, acceptance scenario, and policy
    for (env, density, ems_label, speed_label, acc_label, policy), group in combined_df.groupby(
        ["environment", "density_label", "ems_label", "speed_label", "acceptance_label", "policy"]
    ):
        print(f"\n--- {env} | {density} | EMS={ems_label} | Speed={speed_label} | Accept={acc_label} | {policy} ---")
        print(summarize_results(group))

    # example dashboard over all scenario
    dashboard_of_dashboards_demo(combined_df)

if __name__ == "__main__":
    main()
