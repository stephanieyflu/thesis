import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set(style="whitegrid")


def _mean_ci(series):
    """
    Compute mean and 95% confidence interval (normal approximation).
    """
    m = series.mean()
    n = len(series)
    if n <= 1:
        return m, m, m
    se = series.std(ddof=1) / np.sqrt(n)
    half = 1.96 * se
    return m, m - half, m + half


def summarize_results(df):
    """
    Summarize performance metrics.

    If a 'run_id' column is present, compute means and 95% CIs across runs.
    Otherwise, report simple event-level means.
    """
    if "run_id" in df.columns:
        per_run = (
            df.groupby("run_id")
            .agg(
                first_arrival_mean=("first_arrival_time", "mean"),
                success_rate=("success", "mean"),
                alerts_mean=("num_alerted", "mean"),
            )
            .reset_index()
        )

        fa_mean, fa_lo, fa_hi = _mean_ci(per_run["first_arrival_mean"])
        sr_mean, sr_lo, sr_hi = _mean_ci(per_run["success_rate"])
        al_mean, al_lo, al_hi = _mean_ci(per_run["alerts_mean"])

        summary = {
            "avg_first_arrival": fa_mean,
            "avg_first_arrival_ci": (fa_lo, fa_hi),
            "success_rate": sr_mean,
            "success_rate_ci": (sr_lo, sr_hi),
            "avg_num_alerts": al_mean,
            "avg_num_alerts_ci": (al_lo, al_hi),
            "max_num_alerts": df["num_alerted"].max(),
        }
    else:
        summary = {
            "avg_first_arrival": df["first_arrival_time"].mean(),
            "median_first_arrival": df["first_arrival_time"].median(),
            "std_first_arrival": df["first_arrival_time"].std(),
            "success_rate": df["success"].mean(),
            "avg_num_alerts": df["num_alerted"].mean(),
            "max_num_alerts": df["num_alerted"].max(),
        }

    return summary

def plot_first_arrival_distribution(df, ax=None, label=None):
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.kdeplot(df['first_arrival_time'], fill=True, alpha=0.3, ax=ax, label=label)
    ax.set_xlabel("First Arrival Time (minutes)")
    ax.set_ylabel("Density")
    ax.set_title("First Arrival Time Distribution")

def plot_success_rate_over_threshold(df, thresholds=None, ax=None, label=None):
    if thresholds is None:
        thresholds = range(1, 16)
    rates = [(df['first_arrival_time'] <= t).mean() for t in thresholds]
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.lineplot(x=thresholds, y=rates, marker="o", ax=ax, label=label)
    ax.set_xlabel("Time Threshold (minutes)")
    ax.set_ylabel("Success Rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Success Rate vs Time Threshold")

def plot_alerts_distribution(df, ax=None, label=None):
    if ax is None:
        plt.figure(figsize=(8,5))
        ax = plt.gca()
    sns.histplot(df['num_alerted'], bins=20, kde=False, ax=ax, label=label)
    ax.set_xlabel("Number of Responders Alerted")
    ax.set_ylabel("Frequency")
    ax.set_title("Number of Responders Alerted per Event")

def dashboard_of_dashboards(dfs_dict, title=None):
    fig, axes = plt.subplots(3, 1, figsize=(14, 16), constrained_layout=False)
    plt.subplots_adjust(hspace=0.45, right=0.8)

    for key, df in dfs_dict.items():
        plot_first_arrival_distribution(df, ax=axes[0], label=key)
    axes[0].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    for key, df in dfs_dict.items():
        plot_success_rate_over_threshold(df, ax=axes[1], label=key)
    axes[1].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    for key, df in dfs_dict.items():
        plot_alerts_distribution(df, ax=axes[2], label=key)
    axes[2].legend(loc='center left', bbox_to_anchor=(1, 0.5))

    if title:
        fig.suptitle(title, fontsize=18, y=0.95)

    plt.show()
