import numpy as np

#----- simulation parameters -----#
SIM_DAYS = 365
SIM_RUNS = 100 # number of monte carlo runs per policy
RESPONDERS = 20
CRITICAL_TIME = 5 # minutes to be considered a successful response

#----- environment definitions -----#
ENVIRONMENTS = {
    'urban': {
        'LAMBDA': 10/24, # number of events per day (poisson parameter)
        'DISTANCE_SCALE': 1, # avg 1 km away
        'RESPONDER_SPEED': (40, 10), # mean, sd dev 
    },
    'rural': {
        'LAMBDA': 2/24,
        'DISTANCE_SCALE': 5,
        'RESPONDER_SPEED': (50, 15),
    },
}

#----- fatigue parameters -----#
REST_TIME_MEAN = 30 # minutes of rest after responding
REST_TIME_SD = 10