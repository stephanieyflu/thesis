import numpy as np
import pandas as pd
from responder import Responder
from event import OHCAEvent
from policies import CFR_POLICIES, static_policy, dynamic_policy
from config import (
    ENVIRONMENTS,
    NUM_RESPONDERS,
    T_CRIT,
    RESPONSE_DELAY_MEAN,
    RESPONSE_DELAY_STD,
    AMBULANCE_MEAN,
    AMBULANCE_STD,
    SIM_DAYS,
    RESPONDER_TYPE_MIX,
)
from utils import generate_interarrival_time, sample_distance, sample_speed


def create_responders(num_responders, env_name, acceptance_cfg=None):
    """
    Create a heterogeneous responder pool with three types:
    - none: no formal training
    - cpr: CPR-trained volunteer
    - professional: professional responder (CPR + AED)
    """
    mix = RESPONDER_TYPE_MIX.get(env_name, RESPONDER_TYPE_MIX["urban"])

    count_none = int(num_responders * mix["none"])
    count_cpr = int(num_responders * mix["cpr"])
    count_prof = num_responders - count_none - count_cpr

    # default acceptance ranges by type
    default_acc = {
        "none": (0.05, 0.15),
        "cpr": (0.10, 0.30),
        "professional": (0.30, 0.50),
    }
    if acceptance_cfg is None:
        acceptance_cfg = default_acc
    else:
        # fill in any missing types from defaults
        cfg = default_acc.copy()
        cfg.update(acceptance_cfg)
        acceptance_cfg = cfg

    responders = []
    id_counter = 0

    # no training
    for _ in range(count_none):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["none"]),
                has_cpr_training=False,
                has_aed_access=False,
                is_professional=False,
            )
        )
        id_counter += 1

    # CPR-trained volunteers
    for _ in range(count_cpr):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["cpr"]),
                has_cpr_training=True,
                has_aed_access=False,
                is_professional=False,
            )
        )
        id_counter += 1

    # professionals (CPR + AED)
    for _ in range(count_prof):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["professional"]),
                has_cpr_training=True,
                has_aed_access=True,
                is_professional=True,
            )
        )
        id_counter += 1

    return responders


def run_simulation(
    sim_days=SIM_DAYS,
    policy_name="static",
    env_name="urban",
    num_responders=NUM_RESPONDERS,
    num_events_per_day=1,
    env_overrides=None,
    ambulance_mean=None,
    ambulance_std=None,
    acceptance_cfg=None,
    seed=None,
):
    """
    Core DES for a single (environment, policy) configuration.

    Optional sensitivity hooks:
    - env_overrides: dict of keys to override in ENVIRONMENTS[env_name]
                     e.g. {'speed_mean': 8, 'speed_std': 2}
    - ambulance_mean / ambulance_std: override EMS response distribution
    """
    if seed is not None:
        np.random.seed(seed)

    env_config = ENVIRONMENTS[env_name].copy()
    if env_overrides:
        env_config.update(env_overrides)

    amb_mean = AMBULANCE_MEAN if ambulance_mean is None else ambulance_mean
    amb_std = AMBULANCE_STD if ambulance_std is None else ambulance_std
    responders = create_responders(
        num_responders=num_responders,
        env_name=env_name,
        acceptance_cfg=acceptance_cfg,
    )
    events = []
    total_events = sim_days * num_events_per_day
    current_time = 0 # in minutes

    for _ in range(total_events):
        interarrival_hours = generate_interarrival_time(env_config['lambda_event'])
        current_time += interarrival_hours * 60

        event = OHCAEvent(event_time=current_time, location=None)

        for r in responders:
            r.distance_to_event = sample_distance(env_config)

        # record acceptance decisions for each alerted responder
        acceptance = {}

        if policy_name in ['static', 'dynamic']:
            if policy_name == 'static':
                alerted = static_policy(responders, num_alerts=5, current_time=current_time)
            else:
                alerted = dynamic_policy(responders, target_accepts=2, current_time=current_time)

            # static/dynamic policies do not return acceptances explicitly,
            # so we sample acceptance here for bookkeeping
            for r in alerted:
                acceptance[r.id] = r.decide_to_accept()
        else:
            policy_func = CFR_POLICIES.get(policy_name)
            if policy_func is None:
                raise ValueError(f"Unknown policy: {policy_name}")
            alerted = policy_func(responders, current_time)

            for r in alerted:  # a responder can only accept an event once
                acceptance[r.id] = r.decide_to_accept()

        event.responders_alerted = [r.id for r in alerted]

        responder_arrivals = []  # (responder_id, arrival_time)
        for r in alerted:
            if acceptance.get(r.id, False):
                dist = r.distance_to_event
                speed = sample_speed(env_config) / 60  # km/min
                travel_time = r.travel_time(dist, speed)
                response_delay = max(0, np.random.normal(RESPONSE_DELAY_MEAN, RESPONSE_DELAY_STD))
                t_arrival = travel_time + response_delay
                responder_arrivals.append((r.id, t_arrival))
                r.assign_task(current_time, t_arrival)

        t_ambulance = max(0, np.random.normal(amb_mean, amb_std))
        all_arrival_times = [t for _, t in responder_arrivals] + [t_ambulance]

        t_first = min(all_arrival_times)
        redundant_responders = [
            r_id for r_id, t in responder_arrivals
            if t > t_first
        ]
        event.responder_arrivals = responder_arrivals
        event.redundant_responders = redundant_responders
        event.first_arrival_time = t_first
        event.success = t_first <= T_CRIT
        event.num_accepted = len(responder_arrivals)
        event.num_redundant = len(redundant_responders)
        events.append(event)

    df = pd.DataFrame(
        {
            "first_arrival_time": [e.first_arrival_time for e in events],
            "success": [e.success for e in events],
            "num_alerted": [len(e.responders_alerted) for e in events],
            "num_accepted": [e.num_accepted for e in events],
            "num_redundant": [e.num_redundant for e in events],
        }
    )
    return df


def run_simulation_batch(
    policies,
    env_name="urban",
    sim_days=SIM_DAYS,
    num_responders=NUM_RESPONDERS,
    num_events_per_day=1,
    env_overrides=None,
    ambulance_mean=None,
    ambulance_std=None,
    acceptance_cfg=None,
    seed=None,
):
    dfs = {}
    for policy_name in policies:
        print(f"Running simulation: {policy_name} in {env_name} environment...")
        df = run_simulation(
            sim_days=sim_days,
            policy_name=policy_name,
            env_name=env_name,
            num_responders=num_responders,
            num_events_per_day=num_events_per_day,
            env_overrides=env_overrides,
            ambulance_mean=ambulance_mean,
            ambulance_std=ambulance_std,
            acceptance_cfg=acceptance_cfg,
            seed=seed,
        )
        dfs[policy_name] = df
    return dfs
