
**Mostly yes**, if you describe the scope honestly—but the graphs are **meaningful for counterfactual comparison of policies under your stated assumptions**, not as calibrated predictions for a real system.

**What is sound and coherent**

- **Estimand**: Policies are compared holding your coded rules (nearest- *k*, radii, stages, etc.) and **stylized** urban/rural environments fixed. Results **follow** from that design: faster first arrival, higher coverage at \(T\), tradeoffs with redundancy/alerts, and “CFR vs EMS” under **your** EMS time model.
- **Experimental logic**: Factorial sweeps (density, acceptance, travel friction) map clearly to **sensitivity** of rankings and magnitudes. Fixed EMS per env with a separate slower-EMS batch is a clean **what-if** on ambulance context.
- **Outputs**: ECDFs, threshold coverage, heatmaps, and race-style metrics align with **time-to-first-qualified-arrival** and **load** framing; cross-EMS overlays match the **two calibration** story if labels match the sim batches.

**Where interpretation must stay careful (methodology vs claims)**

- **Archetypes, not a site**: Distances, speeds, and responder counts are **regimes**, not estimated from one network—avoid “our city” language unless you add calibration.
- **No congestion / no multi-incident coupling**: Results are **per-incident**; spillovers and simultaneous calls are outside the model.
- **Success vs reporting**: If the text stresses coverage at 5–10 min but `T_CRIT` or “success” elsewhere uses a single cutoff, **align the narrative** to one primary outcome family (time / coverage curves vs binary success).
- **Clinical endpoints**: First arrival and P(CFR before EMS) are **process** proxies; clinical impact needs explicit limitation or a separate evidence chain.

**Bottom line**

For a thesis, the methodology is **defensible as a transparent policy simulator + sensitivity analysis**; **results follow from it** for relative policy performance under those assumptions. **Meaningfulness** for readers depends on clear statements of **what is varied, what is fixed, and what is not modeled**—then the graphs support **ranking and robustness**, not universal real-world performance without that framing.

# thesis

### Getting Started

Create a virtual environment

    python -m venv .venv-thesis

Activate your virtual environment

    source .venv/Scripts/activate

Install requirements

    pip install -r requirements.txt

### Folder Structure

```
thesis/
│
├── README.md                  # project documentation
├── requirements.txt           # python dependencies
├── main.py                    # entry point to run simulations
├── config.py                  # simulation parameters
├── event.py                   # OHCA event class
├── responder.py               # responder agent class
├── policies.py                # alert policy definitions
├── simulation.py              # core DES logic
├── utils.py                   # helper functions for random sampling and travel times
├── analysis.py                # summary statistics and plotting
└── results/
    ├── combined_results_*.csv         # single-run or interim outputs
    └── combined_results_grid_*.csv    # full experiment grid outputs
```

### Parameters

### Simulation Parameters

| Parameter                          | Symbol / Code                      | Units          | Distribution / Values                                                                                   | Notes                                                                                  |
|------------------------------------|------------------------------------|----------------|---------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Simulation horizon (auxiliary)     | `SIM_DAYS`                         | days           | Default: `365`                                                                                          | Used by some utilities; main DES workload is `TOTAL_EVENTS_PER_REPLICATION`.          |
| OHCA workload per replication      | `TOTAL_EVENTS_PER_REPLICATION`     | count          | Default: `1000`                                                                                         | Fixed incidents per Monte Carlo run (not `SIM_DAYS` × daily rate).                    |
| Monte Carlo runs                   | `SIM_RUNS`                         | –              | Default: `100`                                                                                          | Repetitions per scenario cell (env × density × EMS × speed × acceptance).            |
| Between-incident arrivals         | —                                  | —              | Not modeled                                                                                            | Independent OHCA replications at fixed $N$; no Poisson process in `run_simulation`.   |
| Interarrival time                  | –                                  | hours          | $\Delta t \sim \text{Exponential}(1/\lambda_E)$                                                       | Converted to minutes inside the simulation.                                           |
| Distance to event                  | `distance_mode`, `max_distance_km` | km             | Default: uniform radius in a disk of radius `max_distance_km` (typically 1); $r=R\sqrt{U}$, $U\sim\mathrm{Unif}(0,1)$ | Per responder–event; pool size comes from scenario density (`num_responders`).       |
| Travel speed                       | `speed_mean`, `speed_std`          | km / hour      | Truncated normal: $N(\mu,\sigma^2)$ with $\mu,\sigma$ from `ENVIRONMENTS`, lower bound 1 km/h (`scipy.stats.truncnorm`) | Sampled then converted to km/min when computing travel time.                          |
| Number of responders               | `NUM_RESPONDERS`                   | count          | Default baseline: `30`                                                                                  | Overridden in experiment grid via `densities`.                                        |
| Responder type mix (urban)        | `RESPONDER_TYPE_MIX["urban"]`      | fractions      | `none`: 0.0, `cpr`: 1.0, `professional`: 0.0                                                           | All responders CPR‑trained (mix currently neutral; kept for future tweaks).           |
| Responder type mix (rural)        | `RESPONDER_TYPE_MIX["rural"]`      | fractions      | `none`: 0.0, `cpr`: 1.0, `professional`: 0.0                                                           | Same as urban; responder mix does not affect results for now.                         |
| Acceptance probability (none)     | `acceptance_prob` (type=none)      | –              | $p_i \sim \text{Uniform}(0.05, 0.15)$                                                                 | Per responder, sampled once at creation.                                              |
| Acceptance probability (CPR)      | `acceptance_prob` (type=cpr)       | –              | $p_i \sim \text{Uniform}(0.10, 0.30)$                                                                 |                                                                                       |
| Acceptance probability (prof.)    | `acceptance_prob` (type=professional) | –           | $p_i \sim \text{Uniform}(0.30, 0.50)$                                                                 |                                                                                       |
| Response delay                    | `RESPONSE_DELAY_LOGNORMAL_*`       | minutes        | LogNormal($\ln 60$, $0.5$) in **seconds** (median 60 s), then $\div 60$ for minutes                     | Mobilization delay after accept (before travel).                                      |
| Travel time                       | `Responder.travel_time`            | minutes        | $T_i = d_i / v_i$, with $d_i$ in km and $v_i$ in km/min                                              | Total arrival: $A_i = \tau_i + T_i$.                                                 |
| Rest / recovery time              | `REST_MEAN/STD`                    | minutes        | $t_{\text{rest}} \sim \max(0, N(60, 30))$                                                            | After a response, responders are unavailable for travel time + rest.                  |
| Ambulance response time           | `AMBULANCE_MEAN/STD`               | minutes        | LogNormal with marginal mean/std $(m,s)$; presets use urban $s\in\{2,3,4\}$, rural $s\in\{3,5,6\}$ paired with $5/10$, $10/15$, $15/20$ means | See `utils.sample_ambulance_time_minutes`.                                            |
| Critical time threshold           | `T_CRIT`                           | minutes        | Default: `6`                                                                                           | Event “success” if $t_{\text{first}} \le T_{\text{crit}}$.                           |
| First intervention time           | `first_arrival_time`               | minutes        | $t_{\text{first}} = \min(t_{\text{EMS}}, \min_i A_i)$                                                | Earliest of ambulance or any accepting responder.                                     |
| Success indicator                 | `success`                          | 0/1            | `True` if `first_arrival_time <= T_CRIT`                                                              | Stored per event.                                                                     |
| Alerts per event                  | `num_alerted`                      | count          | Determined by policy; e.g. radius- or k‑nearest‑based                                                 | Includes both accepted and non‑accepted responders.                                   |
| Accepted responders               | `num_accepted`                     | count          | Number of alerted responders who accept and travel                                                    | Derived per event.                                                                    |
| Redundant responders              | `num_redundant`                    | count          | Responders arriving after the first arrival                                                           | Reflects inefficiency / over‑alerting.                                               |
| Policy: Mobile Lifesaver          | `"Mobile Lifesaver"`               | –              | Nearest 10 responders with `has_cpr_training=True`                                                    | AED leg ignored in this implementation (CPR‑only).                                    |
| Policy: PulsePoint / myResponder  | `"PulsePoint_and_myResponder"`     | –              | All available responders within 0.4 km (same rule as both apps)                                       | No skill requirement.                                                                 |
| Policy: Hartslagnu                | `"Hartslagnu"`                     | –              | CPR‑capable within 0.75 km, then sequential alerts until 5 accepts                                   | Uses `alert_until_accepts`.                                                           |
| Policy: Momentum                  | `"Momentum"`                       | –              | CPR‑capable within radius $=\min(0.1 \times t_{\text{EMS,pred}}, 2.0)$ km (default $t_{\text{EMS,pred}}=6$) | Ambulance‑time–based radius.                                                         |
| Policy: HeartRunner               | `"HeartRunner"`                    | –              | Nearest 30 CPR‑capable within 1.3 km (closest first)                                                  | Stylized rule for Denmark-style app dispatch.                                         |
| Policy: GoodSAM                   | `"GoodSAM"`                        | –              | Stage 1: 3 nearest CPR‑capable within 0.3 km; if none accept, Stage 2: CPR‑capable within 3.0 km until 1 accept | Two‑stage dynamic policy.                                                             |
| Baseline policy: EMS‑only         | `"EMS only"`                       | –              | No responders alerted                                                                                  | Outcome driven purely by EMS time.                                                    |
| Baseline policy: Random           | `"Random"`                         | –              | 10 random available responders (no radius or skill constraints)                                       | Implemented, but excluded by default in `run_experiment_grid` (`exclude_policies`).  |
| Simulation grid: environments     | `environments` in `run_experiment_grid` | –       | Default: `["urban", "rural"]`                                                                         | Scenario dimension.                                                                   |
| Simulation grid: densities        | `densities`                        | responders     | e.g. `{"low": 10, "medium": 30, "high": 60}`                                                          | Scenario dimension for responder density.                                             |
| Simulation grid: EMS scenarios    | `ems_scenarios`                    | minutes        | Thesis presets: 5/10, 10/15, 15/20 means with std pairs (urban: 2/3/4, rural: 3/5/6)                | Interpreted as marginal moments for lognormal EMS draws.                              |
| Simulation grid: speed scenarios  | `speed_scenarios`                  | factor         | e.g. `"slow": 0.75`, `"baseline": 1.0`, `"fast": 1.25`                                                | Multiplies both `speed_mean` and `speed_std`.                                         |
| Simulation grid: acceptance scenarios | `acceptance_scenarios`          | –              | Per-type ranges, e.g. `"baseline"` vs `"low_accept"` vs `"high_accept"` for (none/cpr/professional)   | Varies responder acceptance probabilities across scenarios.                            |
| Events per replication            | `total_events` in `run_experiment_grid` / `run_simulation` | count | Default: `TOTAL_EVENTS_PER_REPLICATION` (`1000`) | Independent incidents per run (no Poisson interarrival).                                |
| Monte Carlo seed                  | `seed`                             | –              | Deterministic per (env, density, EMS, speed, acceptance, run)                                         | Stored in output; ensures full reproducibility of each run.                           |