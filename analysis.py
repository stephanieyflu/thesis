import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set(style="whitegrid")

def summarize_results(df):
    """Compute summary statistics for first arrival time and success rate."""
    summary = {
        'avg_first_arrival': df['first_arrival_time'].mean(),
        'median_first_arrival': df['first_arrival_time'].median(),
        'std_first_arrival': df['first_arrival_time'].std(),
        'success_rate': df['success'].mean(),
        'avg_num_alerts': df['num_alerted'].mean(),
        'max_num_alerts': df['num_alerted'].max()
    }
    return summary

def plot_first_arrival_distribution(df, title="First Arrival Time Distribution"):
    """Plot histogram of first arrival times."""
    plt.figure(figsize=(8,5))
    sns.histplot(df['first_arrival_time'], bins=30, kde=True)
    plt.xlabel("First Arrival Time (minutes)")
    plt.ylabel("Frequency")
    plt.title(title)
    plt.tight_layout()
    plt.show()

def plot_success_rate_over_threshold(df, thresholds=None):
    """Plot success rate as a function of time threshold"""
    if thresholds is None:
        thresholds = range(1, 16)  # 1 to 15 minutes
    
    rates = []
    for t in thresholds:
        success_rate = (df['first_arrival_time'] <= t).mean()
        rates.append(success_rate)
    
    plt.figure(figsize=(8,5))
    sns.lineplot(x=thresholds, y=rates, marker="o")
    plt.xlabel("Time Threshold (minutes)")
    plt.ylabel("Success Rate")
    plt.title("Success Rate vs Time Threshold")
    plt.ylim(0, 1.05)
    plt.tight_layout()
    plt.show()

def plot_alerts_distribution(df, title="Number of Alerts per Event"):
    """Plot number of responders alerted per event"""
    plt.figure(figsize=(8,5))
    sns.histplot(df['num_alerted'], bins=20, kde=False)
    plt.xlabel("Number of Responders Alerted")
    plt.ylabel("Frequency")
    plt.title(title)
    plt.tight_layout()
    plt.show()
