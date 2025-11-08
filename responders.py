import numpy as np
import simpy
from config import REST_TIME_MEAN, REST_TIME_SD

def travel_time(distance_km, speed_mean, speed_sd):
    """
    Calculate travel time in minutes based on random speed
    """
    speed = np.clip(np.random.normal(speed_mean, speed_sd), 10, 120)
    return (distance_km / speed) * 60

def random_distance(scale):
    """
    Generate randomized exponential distance (km)
    """
    return np.random.exponential(scale=scale)

def responder_busy(env, responder, duration):
    """
    Compute responder fatigue metrics
    """
    responder["busy"] = True
    yield env.timeout(duration)
    
    # add fatigue rest period
    rest_time = np.clip(np.random.normal(REST_TIME_MEAN, REST_TIME_SD), 5, 60)
    yield env.timeout(rest_time)
    responder["busy"] = False