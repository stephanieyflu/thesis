import numpy as np
import pandas as pd
from responder import Responder
from event import OHCAEvent
from policies import static_policy, dynamic_policy
from utils import generate_interarrival_time, sample_distance, sample_speed
from config import *

def run_simulation(sim_days=SIM_DAYS, policy_name='static', env_name='urban'):
    env = ENVIRONMENTS[env_name]
    responders = [Responder(i, ACCEPTANCE_PROB) for i in range(NUM_RESPONDERS)]
    current_time = 0
    events = []
    
    while current_time < sim_days*24:  # in hours
        interarrival = generate_interarrival_time(env['lambda_event'])
        current_time += interarrival
        event = OHCAEvent(current_time, location=None)
        
        # Determine alerts
        if policy_name == 'static':
            alerted = static_policy(responders, num_alerts=5, current_time=current_time)
        elif policy_name == 'dynamic':
            alerted = dynamic_policy(responders, env, target_accepts=2, current_time=current_time)
        else:
            raise ValueError("Unknown policy")
        
        event.responders_alerted = [r.id for r in alerted]
        
        # Compute responder arrival times
        arrival_times = []
        for r in alerted:
            if r.decide_to_accept():
                dist = sample_distance(env)
                speed = sample_speed(env)
                t_travel = dist / (speed/60)  # convert km/h to km/min
                t_delay = max(0, np.random.normal(RESPONSE_DELAY_MEAN, RESPONSE_DELAY_STD))
                t_arrival = t_delay + t_travel
                arrival_times.append(t_arrival)
                r.assign_task(current_time*60, t_arrival)  # current_time in hours -> minutes
        
        # Ambulance arrival
        t_ambulance = max(0, np.random.normal(AMBULANCE_MEAN, AMBULANCE_STD))
        all_arrivals = arrival_times + [t_ambulance]
        
        if all_arrivals:
            t_first = min(all_arrivals)
        else:
            t_first = t_ambulance
        
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
