import pandas as pd
from simulation import run_simulation
from config import SIM_RUNS, POLICIES, ENVIRONMENTS
from analysis import summarize_results, plot_first_arrival_distribution, plot_success_rate_over_threshold, plot_alerts_distribution

def monte_carlo(policy, env):
    results = []
    for _ in range(SIM_RUNS):
        df = run_simulation(policy_name=policy, env_name=env)
        results.append(df)
    combined = pd.concat(results, ignore_index=True)
    summary = {
        'policy': policy,
        'env': env,
        'avg_first_arrival': combined['first_arrival_time'].mean(),
        'success_rate': combined['success'].mean(),
        'avg_alerts': combined['num_alerted'].mean()
    }
    return combined, summary

if __name__ == "__main__":
    all_summaries = []
    all_dataframes = {}
    
    for policy in POLICIES:
        for env in ENVIRONMENTS:
            df, summary = monte_carlo(policy, env)
            all_summaries.append(summary)
            all_dataframes[f"{policy}_{env}"] = df
    
    # Save aggregated summaries
    df_summary = pd.DataFrame(all_summaries)
    df_summary.to_csv('results/output_summary.csv', index=False)
    print(df_summary)
    
    # Optional analysis for one policy/environment
    show_analysis = True
    if show_analysis:
        # Example: static policy in urban environment
        df_example = all_dataframes['static_urban']
        print("Detailed summary:", summarize_results(df_example))
        plot_first_arrival_distribution(df_example, title="Static Policy - Urban")
        plot_success_rate_over_threshold(df_example)
        plot_alerts_distribution(df_example)
