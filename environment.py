import simpy
from events import cardiac_event
from config import SIM_DAYS, NUM_RESPONDERS

def run_environment(env_name, config, policy):
    env = simpy.Environment()
    responders = [{"id": i, "busy": False} for i in range(NUM_RESPONDERS)]
    results = {"response_times": [], "successes": []}

    env.process(cardiac_event(env, responders, env_name, config, policy, results))
    env.run(until=SIM_DAYS * 24 * 60)  # minutes in a year
    return results