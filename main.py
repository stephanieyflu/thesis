import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime
from responder import Responder
from policies import CFR_POLICIES
from simulation import run_simulation_batch
from analysis import summarize_results, plot_first_arrival_distribution, plot_alerts_distribution, plot_success_rate_over_threshold, dashboard_of_dashboards
from config import SIM_DAYS, NUM_RESPONDERS

# sns.set(style="whitegrid")

plt.rcParams.update({
    # --- FONT SETUP ---
    "text.usetex": False,                 
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],       
    "mathtext.fontset": "cm",             

    # --- SIZE AND DPI ---
    "figure.dpi": 300,

    # --- AXES & GRID ---
    "axes.linewidth": 1.0,
    "axes.grid": True,
    "grid.color": "#cccccc",
    "grid.linewidth": 0.7,
    "grid.alpha": 0.6,
    "grid.linestyle": "-",

    # --- TICKS ---
    "xtick.major.size": 6,
    "ytick.major.size": 6,
    "xtick.direction": "inout",
    "ytick.direction": "inout",

    # --- LINES ---
    "lines.linewidth": 2.0,
    "lines.markersize": 6,

    # --- BACKGROUND ---
    "axes.facecolor": "white",
})

colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52",
          "#8172B2", "#937860", "#DA8BC3"]

def create_responders(num_responders=NUM_RESPONDERS, acceptance_prob_range=(0.5, 0.9)):
    responders = []
    for i in range(num_responders):
        prob = np.random.uniform(*acceptance_prob_range)
        responders.append(Responder(id=i, acceptance_prob=prob))
    return responders

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
    responders = create_responders(NUM_RESPONDERS)

    environments = ['urban', 'rural']
    all_policies = {**CFR_POLICIES}

    combined_results = []

    for env_name in environments:
        print(f"\n=== Running environment: {env_name} ===")
        dfs = run_simulation_batch(all_policies.keys(), env_name=env_name,
                                   sim_days=SIM_DAYS,
                                   num_responders=NUM_RESPONDERS,
                                   num_events_per_day=2)

        for policy_name, df in dfs.items():
            df['environment'] = env_name
            df['policy'] = policy_name
            combined_results.append(df)

    combined_df = pd.concat(combined_results, ignore_index=True)

    for (env, policy), group in combined_df.groupby(['environment', 'policy']):
        print(f"\n--- {env} | {policy} ---")
        print(summarize_results(group))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_folder = "results"
    os.makedirs(results_folder, exist_ok=True)
    combined_filename = os.path.join(results_folder, f"combined_results_{timestamp}.csv")
    combined_df.to_csv(combined_filename, index=False)
    print(f"\nSaved all results to {combined_filename}")

    # for env_name, group in combined_df.groupby('environment'):
    #     dfs_env = {policy: group[group['policy']==policy].drop(columns=['environment', 'policy'])
    #                for policy in group['policy'].unique()}
    #     print(f"\n=== Dashboard for {env_name} environment ===")
    #     dashboard_of_dashboards(dfs_env, title=f"{env_name.capitalize()} Environment")

    dashboard_of_dashboards_demo(combined_df)

if __name__ == "__main__":
    main()
