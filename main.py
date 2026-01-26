import numpy as np
import pandas as pd
import os
from datetime import datetime
from responder import Responder
from policies import CFR_POLICIES
from simulation import run_simulation_batch
from analysis import summarize_results, dashboard_of_dashboards
from config import SIM_DAYS, NUM_RESPONDERS

def create_responders(num_responders=NUM_RESPONDERS, acceptance_prob_range=(0.5, 0.9)):
    responders = []
    for i in range(num_responders):
        prob = np.random.uniform(*acceptance_prob_range)
        responders.append(Responder(id=i, acceptance_prob=prob))
    return responders

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

    for env_name, group in combined_df.groupby('environment'):
        dfs_env = {policy: group[group['policy']==policy].drop(columns=['environment', 'policy'])
                   for policy in group['policy'].unique()}
        print(f"\n=== Dashboard for {env_name} environment ===")
        dashboard_of_dashboards(dfs_env, title=f"{env_name.capitalize()} Environment")


if __name__ == "__main__":
    main()
