import numpy as np
import simpy
from responders import random_distance, travel_time, responder_busy
from policies import determine_alerts
from config import CRITICAL_TIME

def exponential_time(rate):
    return np.random.exponential(1 / rate) * 60  # minutes

def cardiac_event(env, responders, env_name, config, policy, results):
    """
    Generate random cardiac events
    """
    event_id = 0
    while True:
        yield env.timeout(exponential_time(config["EVENT_RATE"]))
        event_id += 1
        env.process(handle_event(env, event_id, responders, env_name, config, policy, results))

def handle_event(env, event_id, responders, env_name, config, policy, results):
    available = [r for r in responders if not r["busy"]]
    if not available:
        return

    num_to_alert = determine_alerts(policy, env_name, len(available))
    selected = np.random.choice(available, size=num_to_alert, replace=False)

    # travel times for responders
    travel_times = [
        travel_time(random_distance(config["DISTANCE_SCALE"]),
                    *config["RESPONDER_SPEED"]) for _ in selected
    ]
    arrival_time = min(travel_times)

    # mark responders as busy
    for r, t in zip(selected, travel_times):
        env.process(responder_busy(env, r, t))

    success = arrival_time <= CRITICAL_TIME
    results["response_times"].append(arrival_time)
    results["successes"].append(success)
