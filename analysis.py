# analysis.py
import numpy as np
import matplotlib.pyplot as plt

def summarize(results_list):
    avg_times = [np.mean(r["response_times"]) for r in results_list]
    success_rates = [np.mean(r["successes"]) for r in results_list]
    return {
        "avg_response_time": np.mean(avg_times),
        "std_response_time": np.std(avg_times),
        "success_rate": np.mean(success_rates),
    }

def plot_comparison(summary_data):
    labels = list(summary_data.keys())
    response_times = [summary_data[k]["avg_response_time"] for k in labels]
    success_rates = [summary_data[k]["success_rate"] * 100 for k in labels]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.bar(labels, response_times, alpha=0.6, label="Avg Response Time (min)")
    ax1.set_ylabel("Avg Response Time (min)")
    ax1.set_xlabel("Policy")

    ax2 = ax1.twinx()
    ax2.plot(labels, success_rates, color="orange", marker="o", label="Success Rate (%)")
    ax2.set_ylabel("Success Rate (%)")

    fig.suptitle("Policy Performance Comparison")
    fig.tight_layout()
    plt.show()
