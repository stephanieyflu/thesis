import numpy as np


def nearest_responders(responders, current_time, k=None, radius=None):
    available = [r for r in responders if r.is_available(current_time)]
    if radius is not None:
        available = [r for r in available if r.distance_to_event <= radius]
    available.sort(key=lambda r: r.distance_to_event)
    return available if k is None else available[:k]


def alert_until_accepts(responders, current_time, target_accepts):
    alerted, accepts = [], 0
    for r in responders:
        alerted.append(r)
        if r.decide_to_accept():
            accepts += 1
        if accepts >= target_accepts:
            break
    return alerted


def mobile_lifesaver_policy(responders, current_time):
    cpr_group = [r for r in responders if r.has_cpr_training]
    return nearest_responders(cpr_group, current_time, k=10)


def pulsepoint_policy(responders, current_time):
    return nearest_responders(responders, current_time, radius=0.4)


def hartslagnu_policy(responders, current_time):
    cpr_group = [r for r in responders if r.has_cpr_training]
    nearby = nearest_responders(cpr_group, current_time, radius=0.75)
    return alert_until_accepts(nearby, current_time, target_accepts=5)


def momentum_policy(responders, current_time, predicted_ambulance_time=6):
    radius = min(0.1 * predicted_ambulance_time, 2.0)
    cpr_group = [r for r in responders if r.has_cpr_training]
    return nearest_responders(cpr_group, current_time, radius=radius)


def heartrunner_policy(responders, current_time):
    cpr_group = [r for r in responders if r.has_cpr_training]
    return nearest_responders(cpr_group, current_time, k=30, radius=1.3)


def goodsam_policy(responders, current_time):
    cpr_group = [r for r in responders if r.has_cpr_training]
    stage1 = nearest_responders(cpr_group, current_time, k=3, radius=0.3)
    if any(r.decide_to_accept() for r in stage1):
        return stage1
    expanded = nearest_responders(cpr_group, current_time, radius=3.0)
    return alert_until_accepts(expanded, current_time, target_accepts=1)


def ems_only_policy(responders, current_time):
    return []


def random_policy(responders, current_time, k=10):
    available = [r for r in responders if r.is_available(current_time)]
    if not available:
        return []
    return list(np.random.choice(available, size=min(k, len(available)), replace=False))


CFR_POLICIES = {
    "Mobile Lifesaver": mobile_lifesaver_policy,
    "PulsePoint_and_myResponder": pulsepoint_policy,
    "Hartslagnu": hartslagnu_policy,
    "Momentum": momentum_policy,
    "HeartRunner": heartrunner_policy,
    "GoodSAM": goodsam_policy,
    "EMS only": ems_only_policy,
    "Random": random_policy,
}


def static_policy(responders, num_alerts, current_time):
    available = [r for r in responders if r.is_available(current_time)]
    if not available:
        return []
    return np.random.choice(available, min(num_alerts, len(available)), replace=False)


def dynamic_policy(responders, target_accepts, current_time):
    accepted, alerted = 0, []
    available = [r for r in responders if r.is_available(current_time)]
    np.random.shuffle(available)
    for r in available:
        alerted.append(r)
        if r.decide_to_accept():
            accepted += 1
        if accepted >= target_accepts:
            break
    return alerted
