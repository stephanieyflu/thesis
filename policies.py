import numpy as np

def nearest_responders(responders, current_time, k=None, radius=None):
    available = [r for r in responders if r.is_available(current_time)]

    if radius is not None:
        available = [r for r in available if r.distance_to_event <= radius]

    available.sort(key=lambda r: r.distance_to_event)

    if k is None:
        return available
    
    return available[:k]

def alert_until_accepts(responders, current_time, target_accepts):
    alerted = []
    accepts = 0

    for r in responders:
        alerted.append(r)
        if r.decide_to_accept():
            accepts += 1
        if accepts >= target_accepts:
            break

    return alerted

def mobile_lifesaver_policy(responders, current_time):
    # cpr_group = [r for r in responders if r.has_cpr_training]
    # aed_group = [r for r in responders if r.has_aed_access]

    # cpr_alerted = nearest_responders(cpr_group, current_time, k=10)
    # aed_alerted = nearest_responders(aed_group, current_time, k=10)

    # # remove duplicates
    # alerted = {r.id: r for r in cpr_alerted + aed_alerted}
    # return list(alerted.values())

    cpr_group = [r for r in responders if r.has_cpr_training]
    return nearest_responders(cpr_group, current_time, k=10)

def pulsepoint_policy(responders, current_time):
    return nearest_responders(
        responders,
        current_time,
        radius=0.4
    )

def hartslagnu_policy(responders, current_time):
    # Hartslagnu: CPR-capable responders within 750m, cancel after 5 accepts.
    cpr_group = [r for r in responders if r.has_cpr_training]
    nearby = nearest_responders(
        cpr_group,
        current_time,
        radius=0.75
    )

    return alert_until_accepts(
        nearby,
        current_time,
        target_accepts=5
    )

def momentum_policy(responders, current_time, predicted_ambulance_time=6):
    radius = min(0.1 * predicted_ambulance_time, 2.0) # radius is a function of the predicted ambulance time
    cpr_group = [r for r in responders if r.has_cpr_training] # cpr-trained responders
    return nearest_responders(
        cpr_group,
        current_time,
        radius=radius
    )

def goodsam_policy(responders, current_time):
    cpr_group = [r for r in responders if r.has_cpr_training]
    stage1 = nearest_responders(
        cpr_group,
        current_time,
        k=3,
        radius=0.3
    )

    if any(r.decide_to_accept() for r in stage1):
        return stage1

    expanded = nearest_responders(
        cpr_group,
        current_time,
        radius=3.0
    )

    return alert_until_accepts(
        expanded,
        current_time,
        target_accepts=1
    )


def ems_only_policy(responders, current_time):
    """
    EMS-only baseline: do not alert any responders.
    """
    return []


def random_policy(responders, current_time, k=10):
    """
    Random baseline: alert k available responders chosen uniformly at random, ignoring distance and skill.
    """
    available = [r for r in responders if r.is_available(current_time)]
    if not available:
        return []
    return list(np.random.choice(available, size=min(k, len(available)), replace=False))

CFR_POLICIES = {
    # alert the nearest 10 responders to perform cpr and some other 10 responders to retrieve aeds (cpr training)
    "Mobile Lifesaver": mobile_lifesaver_policy,

    # alert all responders within 400m (no requirement)
    "PulsePoint": pulsepoint_policy,

    # alert all responders within 400m (no requirement)
    "myResponder": pulsepoint_policy,

    # alert all responders within 750m, cancel other alerts when 5 positive responses are received (cpr training)
    "Hartslagnu": hartslagnu_policy,

    # alert all responders within a radius calculated from the predicted ambulance response time (cpr training)
    "Momentum": momentum_policy,

    # alert the nearest 3 responders within 300m, then dynamically alert more responders over time if no response is received (profession id/cpr training)
    "GoodSAM": goodsam_policy,

    # baselines
    "EMS only": ems_only_policy,
    "Random": random_policy,
}

# demo CFR policies
# CFR_POLICIES = {
#     # small, local team
#     "Local Small": lambda r, t: system_policy(r, t, max_responders=5, radius=0.4),

#     # medium team within a moderate radius
#     "Local Medium": lambda r, t: system_policy(r, t, max_responders=15, radius=1.0),

#     # large crowd coverage
#     "Wide Large": lambda r, t: system_policy(r, t, max_responders=None, radius=3.0),

#     # small group active only during the day
#     "Daytime Small": lambda r, t: system_policy(r, t, max_responders=5, radius=0.4, active_hours=(6,22)),

#     # dynamic: alert responders until target accepts is met
#     "Dynamic Medium": lambda r, t: dynamic_policy(
#         responders=[res for res in r if res.is_available(t)],
#         target_accepts=5,
#         current_time=t
#     ),

#     # random medium team, no radius restriction
#     "Random Medium": lambda r, t: system_policy(r, t, max_responders=15, radius=None),
# }

#----------------------#
#----- deprecated -----#
#----------------------#

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
    """Generic system policy supporting radius, active hours, and uncapped responders."""
    hour = (current_time // 60) % 24
    if hour < active_hours[0] or hour > active_hours[1]:
        return []

    available = [r for r in responders if r.is_available(current_time)]

    if radius is not None:
        available = [
            r for r in available
            if getattr(r, 'distance_to_event', 0) <= radius
        ]

    if not available:
        return []

    if max_responders is None:
        selected = available
    else:
        selected = np.random.choice(
            available,
            size=min(max_responders, len(available)),
            replace=False
        )

    return list(selected)