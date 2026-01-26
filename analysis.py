import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set(style="whitegrid")

def summarize_results(df):
    summary = {
        'avg_first_arrival': df['first_arrival_time'].mean(),
        'median_first_arrival': df['first_arrival_time'].median(),
        'std_first_arrival': df['first_arrival_time'].std(),
        'success_rate': df['success'].mean(),
        'avg_num_alerts': df['num_alerted'].mean(),
        'max_num_alerts': df['num_alerted'].max()
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
