import numpy as np

from .config import REST_MEAN, REST_STD


class Responder:
    def __init__(
        self,
        id,
        acceptance_prob,
        has_cpr_training=False,
        has_aed_access=False,
        is_professional=False,
    ):
        self.id = id
        self.acceptance_prob = acceptance_prob
        self.busy_until = 0
        self.has_cpr_training = has_cpr_training
        self.has_aed_access = has_aed_access
        self.is_professional = is_professional

    def is_available(self, current_time):
        return current_time >= self.busy_until

    def decide_to_accept(self):
        return np.random.rand() < self.acceptance_prob

    def travel_time(self, distance, speed):
        return distance / speed

    def assign_task(self, start_time, travel_time=0):
        rest_time = max(0, np.random.normal(REST_MEAN, REST_STD))
        self.busy_until = start_time + travel_time + rest_time
