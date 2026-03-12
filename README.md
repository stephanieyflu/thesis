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
├── dashboard_app.py           # optional Streamlit dashboard
└── results/
    ├── combined_results_*.csv         # single-run or interim outputs
    └── combined_results_grid_*.csv    # full experiment grid outputs
```

### Parameters

### Simulation Parameters

| Parameter                          | Symbol / Code                      | Units          | Distribution / Values                                                                                   | Notes                                                                                  |
|------------------------------------|------------------------------------|----------------|---------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Simulation horizon                 | `SIM_DAYS`                         | days           | Default: `365`                                                                                          | Number of days simulated per run.                                                     |
| Monte Carlo runs                   | `SIM_RUNS`                         | –              | Default: `50`                                                                                           | Repetitions per scenario cell (env × density × EMS × speed × acceptance).            |
| Event rate                         | `lambda_event` in `ENVIRONMENTS`   | events / hour  | Urban: `8/24` (≈8/day), Rural: `2/24` (≈2/day)                                                         | Event times follow a Poisson process; interarrival \(\Delta t \sim \text{Exp}(\lambda_E)\). |
| Interarrival time                  | –                                  | hours          | \(\Delta t \sim \text{Exponential}(1/\lambda_E)\)                                                      | Converted to minutes inside the simulation.                                           |
| Distance to event                  | `distance_mean`, `distance_std`    | km             | Urban: Gamma(mean=1.5, std=0.7), Rural: Gamma(mean=3, std=1.5)                                         | Drawn per responder–event from Gamma calibrated to mean and std (positive, skewed).   |
| Travel speed                       | `speed_mean`, `speed_std`          | km / hour      | Urban: N(6, 1.5), Rural: N(5, 1), truncated at 1                                                       | Sampled then converted to km/min when computing travel time.                          |
| Number of responders               | `NUM_RESPONDERS`                   | count          | Default baseline: `30`                                                                                  | Overridden in experiment grid via `densities`.                                        |
| Responder type mix (urban)        | `RESPONDER_TYPE_MIX["urban"]`      | fractions      | `none`: 0.2, `cpr`: 0.5, `professional`: 0.3                                                           | Fractions of untrained, CPR‑trained, and professional responders.                     |
| Responder type mix (rural)        | `RESPONDER_TYPE_MIX["rural"]`      | fractions      | `none`: 0.4, `cpr`: 0.5, `professional`: 0.1                                                           | Same categories, different mix.                                                       |
| Acceptance probability (none)     | `acceptance_prob` (type=none)      | –              | \(p_i \sim \text{Uniform}(0.05, 0.15)\)                                                                | Per responder, sampled once at creation.                                              |
| Acceptance probability (CPR)      | `acceptance_prob` (type=cpr)       | –              | \(p_i \sim \text{Uniform}(0.10, 0.30)\)                                                                |                                                                                       |
| Acceptance probability (prof.)    | `acceptance_prob` (type=professional) | –           | \(p_i \sim \text{Uniform}(0.30, 0.50)\)                                                                |                                                                                       |
| Response delay                    | `RESPONSE_DELAY_MEAN/STD`          | minutes        | \(\tau_i \sim \max(0, N(3, 2))\)                                                                       | Time between receiving alert and starting to move.                                    |
| Travel time                       | `Responder.travel_time`            | minutes        | \(T_i = d_i / v_i\), with \(d_i\) in km and \(v_i\) in km/min                                          | Total arrival: \(A_i = \tau_i + T_i\).                                                |
| Rest / recovery time              | `REST_MEAN/STD`                    | minutes        | \(t_{\text{rest}} \sim \max(0, N(60, 30))\)                                                           | After a response, responders are unavailable for travel time + rest.                  |
| Ambulance response time           | `AMBULANCE_MEAN/STD`               | minutes        | \(t_{\text{EMS}} \sim \max(0, N(8, 2))\)                                                              | Can be overridden per EMS scenario in the experiment grid.                            |
| Critical time threshold           | `T_CRIT`                           | minutes        | Default: `6`                                                                                           | Event “success” if \(t_{\text{first}} \le T_{\text{crit}}\).                          |
| First intervention time           | `first_arrival_time`               | minutes        | \(t_{\text{first}} = \min(t_{\text{EMS}}, \min_i A_i)\)                                               | Earliest of ambulance or any accepting responder.                                     |
| Success indicator                 | `success`                          | 0/1            | `True` if `first_arrival_time <= T_CRIT`                                                              | Stored per event.                                                                     |
| Alerts per event                  | `num_alerted`                      | count          | Determined by policy; e.g. radius- or k‑nearest‑based                                                 | Includes both accepted and non‑accepted responders.                                   |
| Accepted responders               | `num_accepted`                     | count          | Number of alerted responders who accept and travel                                                    | Derived per event.                                                                    |
| Redundant responders              | `num_redundant`                    | count          | Responders arriving after the first arrival                                                           | Reflects inefficiency / over‑alerting.                                               |
| Policy: Mobile Lifesaver          | `"Mobile Lifesaver"`               | –              | Nearest 10 responders with `has_cpr_training=True`                                                    | AED leg ignored in this implementation (CPR‑only).                                    |
| Policy: PulsePoint / myResponder  | `"PulsePoint"`, `"myResponder"`    | –              | All available responders within 0.4 km                                                                | No skill requirement.                                                                 |
| Policy: Hartslagnu                | `"Hartslagnu"`                     | –              | CPR‑capable within 0.75 km, then sequential alerts until 5 accepts                                   | Uses `alert_until_accepts`.                                                           |
| Policy: Momentum                  | `"Momentum"`                       | –              | CPR‑capable within radius \(=\min(0.1 \times t_{\text{EMS,pred}}, 2.0)\) km (default \(t_{\text{EMS,pred}}=6\)) | Ambulance‑time–based radius.                                                         |
| Policy: GoodSAM                   | `"GoodSAM"`                        | –              | Stage 1: 3 nearest CPR‑capable within 0.3 km; if none accept, Stage 2: CPR‑capable within 3.0 km until 1 accept | Two‑stage dynamic policy.                                                             |
| Baseline policy: EMS‑only         | `"EMS only"`                       | –              | No responders alerted                                                                                  | Outcome driven purely by EMS time.                                                    |
| Baseline policy: Random           | `"Random"`                         | –              | 10 random available responders (no radius or skill constraints)                                       | Simple non‑spatial baseline.                                                          |
| Simulation grid: environments     | `environments` in `run_experiment_grid` | –       | Default: `["urban", "rural"]`                                                                         | Scenario dimension.                                                                   |
| Simulation grid: densities        | `densities`                        | responders     | e.g. `{"low": 10, "medium": 30, "high": 60}`                                                          | Scenario dimension for responder density.                                             |
| Simulation grid: EMS scenarios    | `ems_scenarios`                    | minutes        | e.g. `"fast_ems": {mean: 6, std: 1.5}, "baseline": {8,2}, "slow_ems": {12,3}`                        | Overrides `AMBULANCE_MEAN/STD`.                                                       |
| Simulation grid: speed scenarios  | `speed_scenarios`                  | factor         | e.g. `"slow": 0.75`, `"baseline": 1.0`, `"fast": 1.25`                                                | Multiplies both `speed_mean` and `speed_std`.                                         |
| Simulation grid: acceptance scenarios | `acceptance_scenarios`          | –              | Per-type ranges, e.g. `"baseline"` vs `"low_accept"` vs `"high_accept"` for (none/cpr/professional)   | Varies responder acceptance probabilities across scenarios.                            |
| Events per day                    | `num_events_per_day`               | events / day   | Default in grid: `2` (can be changed)                                                                 | Used with `SIM_DAYS` to determine total events.                                       |
| Monte Carlo seed                  | `seed`                             | –              | Deterministic per (env, density, EMS, speed, acceptance, run)                                         | Stored in output; ensures full reproducibility of each run.                           |