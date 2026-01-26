import numpy as np
from config import RESPONSE_DELAY_MEAN, RESPONSE_DELAY_STD, REST_MEAN, REST_STD

class Responder:
    def __init__(self, id, acceptance_prob):
        self.id = id
        self.acceptance_prob = acceptance_prob
        self.busy_until = 0  # minutes since simulation start

    def is_available(self, current_time):
        return current_time >= self.busy_until

    def decide_to_accept(self):
        return np.random.rand() < self.acceptance_prob

    def travel_time(self, distance, speed):
        """Compute travel time in minutes (distance in km, speed in km/min)"""
        return distance / speed

    def assign_task(self, start_time, travel_time=0):
        """Mark responder as busy including travel + rest time"""
        rest_time = max(0, np.random.normal(REST_MEAN, REST_STD))
        self.busy_until = start_time + travel_time + rest_time
