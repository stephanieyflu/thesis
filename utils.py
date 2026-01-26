import numpy as np

def generate_interarrival_time(lambda_event):
    """Exponential interarrival times in hours"""
    return np.random.exponential(1/lambda_event)

def sample_distance(env):
    """Sample travel distance from environment distribution"""
    return max(0, np.random.normal(env['distance_mean'], env['distance_std']))

def sample_speed(env):
    """Sample speed from environment distribution (km/h)"""
    return max(1, np.random.normal(env['speed_mean'], env['speed_std']))
