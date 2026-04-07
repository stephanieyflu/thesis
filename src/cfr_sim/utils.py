import math

import numpy as np
from scipy.stats import truncnorm

from .config import RESPONSE_DELAY_LOGNORMAL_MU, RESPONSE_DELAY_LOGNORMAL_SIGMA

# Speed (km/h): Normal(mu, sigma) truncated below this minimum (same as previous max(1, ...) behaviour).
SPEED_TRUNC_LOWER_KMH = 1.0
def generate_interarrival_time(lambda_event):
    return np.random.exponential(1/lambda_event)

def sample_distance(env):
    """
    Sample a non-negative, right-skewed distance using a Gamma distribution
    calibrated to the environment's mean and std.
    """
    mean = env['distance_mean']
    std = env['distance_std']
    # shape-scale parameterization: mean = k*theta, var = k*theta^2
    k = (mean / std) ** 2
    theta = (std ** 2) / mean
    return np.random.gamma(shape=k, scale=theta)

def lognormal_mu_sigma_from_mean_std(mean: float, std: float) -> tuple[float, float]:
    """
    For X ~ LogNormal with E[X]=mean and SD[X]=std (both on the natural scale),
    return (mu, sigma) such that np.random.lognormal(mu, sigma) has those moments.
    """
    mean = float(mean)
    std = float(std)
    if mean <= 0:
        raise ValueError("mean must be positive")
    if std <= 0:
        raise ValueError("std must be positive")
    sigma_ln = math.sqrt(math.log(1.0 + (std / mean) ** 2))
    mu_ln = math.log(mean) - 0.5 * sigma_ln * sigma_ln
    return mu_ln, sigma_ln


def sample_ambulance_time_minutes(mean: float, std: float) -> float:
    """
    Ambulance arrival time (minutes): lognormal with marginal mean ``mean`` and std ``std``.
    If std == 0, returns ``mean``.
    """
    mean = float(mean)
    std = float(std)
    if mean <= 0:
        raise ValueError("ambulance mean must be positive")
    if std <= 0:
        return mean
    mu_ln, sigma_ln = lognormal_mu_sigma_from_mean_std(mean, std)
    return float(np.random.lognormal(mu_ln, sigma_ln))


def sample_speed(env):
    """Draw travel speed (km/h) from Normal(mu, sigma) truncated below ``SPEED_TRUNC_LOWER_KMH``."""
    mu = float(env["speed_mean"])
    sigma = float(env["speed_std"])
    if sigma <= 0.0:
        return max(SPEED_TRUNC_LOWER_KMH, mu)
    a = (SPEED_TRUNC_LOWER_KMH - mu) / sigma
    b = np.inf
    return float(truncnorm.rvs(a, b, loc=mu, scale=sigma))


def sample_response_delay_minutes():
    """LogNormal(ln(60), 0.5) in seconds, median 60 s; return minutes for the DES."""
    sec = float(np.random.lognormal(RESPONSE_DELAY_LOGNORMAL_MU, RESPONSE_DELAY_LOGNORMAL_SIGMA))
    return sec / 60.0


def mean_response_delay_minutes():
    """E[delay] for the same lognormal in seconds, converted to minutes (for average_conditions traces)."""
    mean_sec = math.exp(RESPONSE_DELAY_LOGNORMAL_MU + 0.5 * RESPONSE_DELAY_LOGNORMAL_SIGMA**2)
    return mean_sec / 60.0


def apply_thesis_retroactive_time_adjustment(df, subtract_mean_minutes: float | None = None):
    """
    Adjust event-level rows so volunteer arrival times no longer include the legacy
    mean view/decision delay (subtractive adjustment on first volunteer arrival,
    then recompute first arrival and CFR-before-EMS).

    Does not change num_alerted / num_accepted (those reflect the original run).
    Controlled globally by ``THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY`` in
    ``config`` when ``subtract_mean_minutes`` is None.
    """
    import pandas as pd

    from .config import (
        THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY,
        legacy_view_decision_delay_mean_minutes,
    )

    if subtract_mean_minutes is None:
        if not THESIS_RETROACTIVE_SUBTRACT_LEGACY_DECISION_DELAY:
            return df
        subtract_mean_minutes = legacy_view_decision_delay_mean_minutes()

    if subtract_mean_minutes <= 0:
        return df

    need = {"ambulance_time", "first_volunteer_arrival", "first_arrival_time"}
    if not need.issubset(df.columns):
        return df

    chunk = df.copy()
    fv = pd.to_numeric(chunk["first_volunteer_arrival"], errors="coerce")
    amb = pd.to_numeric(chunk["ambulance_time"], errors="coerce")

    fv_adj = fv - float(subtract_mean_minutes)
    fv_adj = fv_adj.where(np.isfinite(fv_adj), np.nan)
    fv_adj = fv_adj.clip(lower=0.0)

    first_cf = np.where(np.isfinite(fv_adj), np.minimum(fv_adj, amb), amb)

    chunk["first_volunteer_arrival"] = fv_adj.astype(np.float64)
    chunk["first_arrival_time"] = first_cf.astype(np.float64)
    chunk["cfr_beats_ems"] = (
        (np.isfinite(fv_adj) & np.isfinite(amb) & (fv_adj < amb)).astype(np.float64)
    )
    if "success" in chunk.columns:
        from .config import T_CRIT

        chunk["success"] = chunk["first_arrival_time"] <= float(T_CRIT)
    for t in range(5, 11):
        col = f"coverage_{t}"
        if col in chunk.columns:
            chunk[col] = (chunk["first_arrival_time"] <= float(t)).astype(np.float64)
    return chunk
