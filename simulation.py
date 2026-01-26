import numpy as np
import pandas as pd
from responder import Responder
from event import OHCAEvent
from policies import CFR_POLICIES, static_policy, dynamic_policy
from config import ENVIRONMENTS, NUM_RESPONDERS, T_CRIT, RESPONSE_DELAY_MEAN, RESPONSE_DELAY_STD, AMBULANCE_MEAN, AMBULANCE_STD, SIM_DAYS

# ------------------------
# Utility functions
# ------------------------
def generate_interarrival_time(lambda_event):
    """Exponential interarrival times in hours"""
    return np.random.exponential(1 / lambda_event)

def sample_distance(env):
    """Sample travel distance from environment distribution (km)"""
    return max(0, np.random.normal(env['distance_mean'], env['distance_std']))

def sample_speed(env):
    """Sample travel speed (km/h)"""
    return max(1, np.random.normal(env['speed_mean'], env['speed_std']))

# ------------------------
# Core simulation
# ------------------------
def run_simulation(sim_days=SIM_DAYS, policy_name='static', env_name='urban', num_responders=NUM_RESPONDERS, num_events_per_day=1):
    """
    Run a DES simulation for a given policy and environment.
    
    Returns:
        DataFrame with first arrival times, success, and number of responders alerted
    """
    env_config = ENVIRONMENTS[env_name]
    responders = [Responder(i, acceptance_prob=0.5 + 0.4*np.random.rand()) for i in range(num_responders)]
    
    events = []
    total_events = sim_days * num_events_per_day
    current_time = 0  # in minutes

    for _ in range(total_events):
        # Interarrival time in hours -> convert to minutes
        interarrival_hours = generate_interarrival_time(env_config['lambda_event'])
        current_time += interarrival_hours * 60

        event = OHCAEvent(event_time=current_time, location=None)

        # Assign random distance for each responder
        for r in responders:
            r.distance_to_event = sample_distance(env_config)

        # Select policy
        if policy_name in ['static', 'dynamic']:
            if policy_name == 'static':
                alerted = static_policy(responders, num_alerts=5, current_time=current_time)
            else:
                alerted = dynamic_policy(responders, target_accepts=2, current_time=current_time)
        else:
            policy_func = CFR_POLICIES.get(policy_name)
            if policy_func is None:
                raise ValueError(f"Unknown policy: {policy_name}")
            alerted = policy_func(responders, current_time)

        event.responders_alerted = [r.id for r in alerted]

        # Compute arrival times
        arrival_times = []
        for r in alerted:
            if r.decide_to_accept():
                dist = r.distance_to_event
                speed = sample_speed(env_config) / 60  # km/min
                travel_time = r.travel_time(dist, speed)
                # Add response delay
                response_delay = max(0, np.random.normal(RESPONSE_DELAY_MEAN, RESPONSE_DELAY_STD))
                t_arrival = travel_time + response_delay
                arrival_times.append(t_arrival)
                r.assign_task(current_time, t_arrival)
            else:
                arrival_times.append(np.inf)  # did not accept

        # Ambulance arrival
        t_ambulance = max(0, np.random.normal(AMBULANCE_MEAN, AMBULANCE_STD))
        all_arrivals = arrival_times + [t_ambulance]

        # Determine first arrival & success
        t_first = min(all_arrivals)
        event.first_arrival_time = t_first
        event.success = t_first <= T_CRIT
        events.append(event)

    # Aggregate results
    df = pd.DataFrame({
        'first_arrival_time': [e.first_arrival_time for e in events],
        'success': [e.success for e in events],
        'num_alerted': [len(e.responders_alerted) for e in events]
    })
    return df

# ------------------------
# Batch simulation for multiple policies
# ------------------------
def run_simulation_batch(policies, env_name='urban', sim_days=SIM_DAYS, num_responders=NUM_RESPONDERS, num_events_per_day=1):
    """
    Run all policies in a dictionary and return DataFrames.
    """
    dfs = {}
    for policy_name in policies:
        print(f"Running simulation: {policy_name} in {env_name} environment...")
        df = run_simulation(sim_days=sim_days, policy_name=policy_name, env_name=env_name,
                            num_responders=num_responders, num_events_per_day=num_events_per_day)
        dfs[policy_name] = df
    return dfs
