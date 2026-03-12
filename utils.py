import numpy as np

def generate_interarrival_time(lambda_event):
    return np.random.exponential(1/lambda_event)

def sample_distance(env):
    """
    Sample a non-negative, right-skewed distance using a Gamma distribution
    calibrated to the environment's mean and std.
    """
    mean = env['distance_mean']
    std = env['distance_std']
    # shape-scale parameterization: mean = k*theta, var = k*theta^2
    k = (mean / std) ** 2
    theta = (std ** 2) / mean
    return np.random.gamma(shape=k, scale=theta)

def sample_speed(env):
    return max(1, np.random.normal(env['speed_mean'], env['speed_std']))
