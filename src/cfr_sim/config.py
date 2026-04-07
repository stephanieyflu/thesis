import math

SIM_DAYS = 365
SIM_RUNS = 100
TOTAL_EVENTS_PER_REPLICATION = 1000

ENVIRONMENTS = {
    "urban": {
        "distance_mean": 1.5,
        "distance_std": 0.7,
        "speed_mean": 6.5,
        "speed_std": 1.2,
        "ambulance_mean": 10.0,
        "ambulance_std": 3.0,
    },
    "rural": {
        "distance_mean": 3.0,
        "distance_std": 1.5,
        "speed_mean": 8.3,
        "speed_std": 1.0,
        "ambulance_mean": 15.0,
        "ambulance_std": 5.0,
    },
}

RESPONDER_TYPE_MIX = {
    "urban": {"none": 0.0, "cpr": 1.0, "professional": 0.0},
    "rural": {"none": 0.0, "cpr": 1.0, "professional": 0.0},
}

NUM_RESPONDERS = 30
ACCEPTANCE_PROB = 0.4
RESPONSE_DELAY_LOGNORMAL_MU = math.log(60.0)
RESPONSE_DELAY_LOGNORMAL_SIGMA = 0.5
REST_MEAN = 60
REST_STD = 30
AMBULANCE_MEAN = ENVIRONMENTS["urban"]["ambulance_mean"]
AMBULANCE_STD = ENVIRONMENTS["urban"]["ambulance_std"]
POLICIES = ["static", "dynamic"]
T_CRIT = 6

THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY = False
LEGACY_VIEW_DECISION_DELAY_MU_LN = math.log(0.8)
LEGACY_VIEW_DECISION_DELAY_SIGMA_LN = 0.9


def legacy_view_decision_delay_mean_minutes() -> float:
    return float(
        math.exp(
            LEGACY_VIEW_DECISION_DELAY_MU_LN
            + 0.5 * LEGACY_VIEW_DECISION_DELAY_SIGMA_LN**2
        )
    )
