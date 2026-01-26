import numpy as np

def static_policy(responders, num_alerts, current_time):
    """Alert a fixed number of available responders randomly"""
    available = [r for r in responders if r.is_available(current_time)]
    if not available:
        return []
    return np.random.choice(available, min(num_alerts, len(available)), replace=False)

def dynamic_policy(responders, target_accepts, current_time):
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

def system_policy(responders, current_time, max_responders=20, radius=None, active_hours=(0,24)):
    """Generic system policy supporting radius and active hours"""
    hour = (current_time // 60) % 24 # convert minutes to hour
    if hour < active_hours[0] or hour > active_hours[1]:
        return []

    available = [r for r in responders if r.is_available(current_time)]
    if radius is not None:
        available = [r for r in available if getattr(r, 'distance_to_event', 0) <= radius]

    if not available:
        return []

    return list(np.random.choice(available, min(max_responders, len(available)), replace=False))

CFR_POLICIES = {
    "Moment": lambda r, t: system_policy(r, t, max_responders=50, radius=None, active_hours=(0,24)),
    "AED-Alert": lambda r, t: system_policy(r, t, max_responders=20, radius=10),
    "HartslagNu": lambda r, t: system_policy(r, t, max_responders=30, radius=10, active_hours=(0,24)),
    "Mobile Lifesaver": lambda r, t: system_policy(r, t, max_responders=3, radius=12, active_hours=(6,23)),
    "PulsePoint": lambda r, t: system_policy(r, t, max_responders=25, radius=4),
    "FirstAED": lambda r, t: sorted([res for res in r if res.is_available(t)], key=lambda x: getattr(x,'distance_to_event',0))[:5],
    "Good Samaritan": lambda r, t: system_policy(r, t, max_responders=15, radius=4, active_hours=(6,22)),
    "GoodSAM": lambda r, t: system_policy(r, t, max_responders=20, radius=3),
    "DAE RespondER": lambda r, t: system_policy(r, t, max_responders=50, radius=50),
    "Mobile Rescuers": lambda r, t: system_policy(r, t, max_responders=30),
    "myResponder": lambda r, t: system_policy(r, t, max_responders=15, radius=4),
    "GoodSAM-Alt": lambda r, t: system_policy(r, t, max_responders=15, radius=3),
}
