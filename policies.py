import numpy as np

def static_policy(responders, num_alerts, current_time):
    """Alert a fixed number of available responders randomly"""
    available = [r for r in responders if r.is_available(current_time)]
    return np.random.choice(available, min(num_alerts, len(available)), replace=False)

def dynamic_policy(responders, env, target_accepts, current_time):
    """Alert in batches until target accepts is met"""
    accepted = 0
    alerted = []
    available = [r for r in responders if r.is_available(current_time)]
    np.random.shuffle(available)
    
    for r in available:
        alerted.append(r)
        if r.decide_to_accept():
            accepted += 1
        if accepted >= target_accepts:
            break
    return alerted
