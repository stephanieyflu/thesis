SIM_DAYS = 365
SIM_RUNS = 100

ENVIRONMENTS = {
    'urban': {
        'lambda_event': 8/24,
        'distance_mean': 1.5,
        'distance_std': 0.7,
        'speed_mean': 6,
        'speed_std': 1.5
    },
    'rural': {
        'lambda_event': 2/24,
        'distance_mean': 3,
        'distance_std': 1.5,
        'speed_mean': 5,
        'speed_std': 1
    }
}

RESPONDER_TYPE_MIX = {
    "urban": {
        "none": 0.0,
        "cpr": 1.0,
        "professional": 0.0,
    },
    "rural": {
        "none": 0.0,
        "cpr": 1.0,
        "professional": 0.0,
    },
}

NUM_RESPONDERS = 30
ACCEPTANCE_PROB = 0.4
RESPONSE_DELAY_MEAN = 3
RESPONSE_DELAY_STD = 2

REST_MEAN = 60
REST_STD = 30

AMBULANCE_MEAN = 8
AMBULANCE_STD = 2

POLICIES = ['static', 'dynamic']

T_CRIT = 6
