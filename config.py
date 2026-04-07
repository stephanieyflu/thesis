import math

SIM_DAYS = 365
SIM_RUNS = 100
# Fixed OHCA count per Monte Carlo replication (annual workload; aligns with van den Berg et al.-style fixed N).
TOTAL_EVENTS_PER_REPLICATION = 1000

# ---------------------------------------------------------------------------
# Environment archetypes (stylized; not calibrated to one jurisdiction).
#
# - Total events per run: TOTAL_EVENTS_PER_REPLICATION independent OHCA replications
#   (no Poisson interarrival between incidents).
# - Distances: shorter typical urban responder--event distances vs rural.
# - Travel speed: literature-consistent *relative* pattern — slower effective
#   movement in dense urban settings (~1.8 m/s) vs faster unconstrained rural
#   movement (~2.3 m/s), expressed in km/h for the simulation.
# - EMS: lognormal times with marginal means ~10 / ~15 min; std matches thesis presets when overridden.
# ---------------------------------------------------------------------------
ENVIRONMENTS = {
    "urban": {
        "distance_mean": 1.5,
        "distance_std": 0.7,
        "speed_mean": 6.5,  # ~1.8 m/s
        "speed_std": 1.2,
        "ambulance_mean": 10.0,
        "ambulance_std": 3.0,
    },
    "rural": {
        "distance_mean": 3.0,
        "distance_std": 1.5,
        "speed_mean": 8.3,  # ~2.3 m/s
        "speed_std": 1.0,
        "ambulance_mean": 15.0,
        "ambulance_std": 5.0,
    },
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

# Mobilization delay after accepting an alert (minutes in the simulator).
# LogNormal(mu, sigma) on the delay in seconds (median = exp(mu) = 60 s), then divided by 60.
RESPONSE_DELAY_LOGNORMAL_MU = math.log(60.0)
RESPONSE_DELAY_LOGNORMAL_SIGMA = 0.5

REST_MEAN = 60
REST_STD = 30

# Legacy aliases: urban EMS baseline (prefer ENVIRONMENTS[env]["ambulance_*"]).
AMBULANCE_MEAN = ENVIRONMENTS["urban"]["ambulance_mean"]
AMBULANCE_STD = ENVIRONMENTS["urban"]["ambulance_std"]

POLICIES = ["static", "dynamic"]

T_CRIT = 6

# ---------------------------------------------------------------------------
# Thesis / analysis alignment (legacy CSV adjustment)
# ---------------------------------------------------------------------------
# Archived event-level CSVs may have been produced when the simulator added a
# stochastic view/decision delay to arrival times. The thesis reports metrics
# after subtracting E[that delay] from volunteer arrival times when enabled.
# Set False when using original simulator outputs that already include this delay.
THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY = False
LEGACY_VIEW_DECISION_DELAY_MU_LN = math.log(0.8)
LEGACY_VIEW_DECISION_DELAY_SIGMA_LN = 0.9


def legacy_view_decision_delay_mean_minutes() -> float:
    """E[D] for D ~ LogNormal(mu_ln, sigma_ln) on the delay in minutes."""
    return float(
        math.exp(
            LEGACY_VIEW_DECISION_DELAY_MU_LN
            + 0.5 * LEGACY_VIEW_DECISION_DELAY_SIGMA_LN**2
        )
    )
