import simpy

from .config import NUM_RESPONDERS, SIM_DAYS
from .event import OHCAEvent


def run_environment(env_name, config, policy):
    env = simpy.Environment()
    responders = [{"id": i, "busy": False} for i in range(NUM_RESPONDERS)]
    results = {"response_times": [], "successes": []}
    _ = OHCAEvent  # preserve exported symbol usage in this module
    env.run(until=SIM_DAYS * 24 * 60)
    return results
