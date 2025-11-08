import numpy as np
from config import ENVIRONMENTS, SIM_RUNS
from environment import run_environment
from policies import get_policy
from analysis import summarize, plot_comparison

def main():
    policies = ["PolicyA", "PolicyB", "PolicyC", "Dynamic"]
    results_summary = {}

    for env_name, config in ENVIRONMENTS.items():
        print(f"\n=== Environment: {env_name.upper()} ===")
        env_summary = {}
        for pname in policies:
            policy = get_policy(pname)
            all_results = [run_environment(env_name, config, policy) for _ in range(SIM_RUNS)]
            summary = summarize(all_results)
            env_summary[pname] = summary
            print(f"{pname}: Avg={summary['avg_response_time']:.2f} min, "
                  f"Success={summary['success_rate']*100:.1f}%, "
                  f"SD={summary['std_response_time']:.2f}")
        results_summary[env_name] = env_summary
        plot_comparison(env_summary)

if __name__ == "__main__":
    main()