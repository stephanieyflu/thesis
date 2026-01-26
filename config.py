SIM_DAYS = 365
SIM_RUNS = 50

ENVIRONMENTS = {
    'urban': {
        'lambda_event': 10/24, # events per hour
        'distance_mean': 2, # km
        'distance_std': 1,
        'speed_mean': 40, # km/h
        'speed_std': 10
    },
    'rural': {
        'lambda_event': 2/24,
        'distance_mean': 5,
        'distance_std': 2,
        'speed_mean': 50,
        'speed_std': 15
    }
}

NUM_RESPONDERS = 50
ACCEPTANCE_PROB = 0.5
RESPONSE_DELAY_MEAN = 2 # minutes
RESPONSE_DELAY_STD = 1
REST_MEAN = 30 # minutes
REST_STD = 10

AMBULANCE_MEAN = 8 # minutes
AMBULANCE_STD = 2

POLICIES = ['static', 'dynamic'] # examples

T_CRIT = 5 # minutes
