import numpy as np
import pandas as pd
from responder import Responder
from policies import CFR_POLICIES, static_policy, dynamic_policy
from config import (
    ENVIRONMENTS,
    NUM_RESPONDERS,
    TOTAL_EVENTS_PER_REPLICATION,
    T_CRIT,
    AMBULANCE_MEAN,
    AMBULANCE_STD,
    RESPONDER_TYPE_MIX,
)
from utils import (
    mean_response_delay_minutes,
    sample_ambulance_time_minutes,
    sample_distance,
    sample_response_delay_minutes,
    sample_speed,
)


def create_responders(num_responders, env_name, acceptance_cfg=None):
    """
    Create a heterogeneous responder pool with three types:
    - none: no formal training
    - cpr: CPR-trained volunteer
    - professional: professional responder (CPR + AED)
    """
    mix = RESPONDER_TYPE_MIX.get(env_name, RESPONDER_TYPE_MIX["urban"])

    count_none = int(num_responders * mix["none"])
    count_cpr = int(num_responders * mix["cpr"])
    count_prof = num_responders - count_none - count_cpr

    # default acceptance ranges by type
    default_acc = {
        "none": (0.05, 0.15),
        "cpr": (0.10, 0.30),
        "professional": (0.30, 0.50),
    }
    if acceptance_cfg is None:
        acceptance_cfg = default_acc
    else:
        # fill in any missing types from defaults
        cfg = default_acc.copy()
        cfg.update(acceptance_cfg)
        acceptance_cfg = cfg

    responders = []
    id_counter = 0

    # no training
    for _ in range(count_none):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["none"]),
                has_cpr_training=False,
                has_aed_access=False,
                is_professional=False,
            )
        )
        id_counter += 1

    # CPR-trained volunteers
    for _ in range(count_cpr):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["cpr"]),
                has_cpr_training=True,
                has_aed_access=False,
                is_professional=False,
            )
        )
        id_counter += 1

    # professionals (CPR + AED)
    for _ in range(count_prof):
        responders.append(
            Responder(
                id=id_counter,
                acceptance_prob=np.random.uniform(*acceptance_cfg["professional"]),
                has_cpr_training=True,
                has_aed_access=True,
                is_professional=True,
            )
        )
        id_counter += 1

    return responders


def run_simulation(
    policy_name="static",
    env_name="urban",
    num_responders=NUM_RESPONDERS,
    total_events=TOTAL_EVENTS_PER_REPLICATION,
    env_overrides=None,
    ambulance_mean=None,
    ambulance_std=None,
    acceptance_cfg=None,
    seed=None,
    distance_mode="uniform_1km",
    max_distance_km=1.0,
    phased_step_minutes=0.5,
    max_alert_minutes=10.0,
    return_event_level=True,
):
    """
    Core DES for a single (environment, policy) configuration.

    Each of ``total_events`` OHCA incidents is simulated independently (fresh responder
    availability at t=0); there is no Poisson process of arrests across time.

    Optional sensitivity hooks:
    - env_overrides: dict of keys to override in ENVIRONMENTS[env_name]
                     e.g. {'speed_mean': 8, 'speed_std': 2}
    - ambulance_mean / ambulance_std: target marginal mean and std (minutes) for EMS time;
      draws are lognormal with those moments (see ``sample_ambulance_time_minutes`` in ``utils``).
    - total_events: number of OHCA events per replication (default TOTAL_EVENTS_PER_REPLICATION).
    - return_event_level: when False, return one run-level summary dict instead of
      an event-level DataFrame (much smaller/faster for grid sweeps).
    """
    if seed is not None:
        np.random.seed(seed)

    env_config = ENVIRONMENTS[env_name].copy()
    if env_overrides:
        env_config.update(env_overrides)

    if ambulance_mean is None:
        amb_mean = env_config.get("ambulance_mean", AMBULANCE_MEAN)
    else:
        amb_mean = ambulance_mean
    if ambulance_std is None:
        amb_std = env_config.get("ambulance_std", AMBULANCE_STD)
    else:
        amb_std = ambulance_std
    responders = create_responders(
        num_responders=num_responders,
        env_name=env_name,
        acceptance_cfg=acceptance_cfg,
    )
    first_arrival_arr = np.empty(total_events, dtype=float)
    success_arr = np.empty(total_events, dtype=bool)
    coverage5_arr = np.empty(total_events, dtype=bool)
    num_alerted_arr = np.empty(total_events, dtype=np.int32)
    num_accepted_arr = np.empty(total_events, dtype=np.int32)
    num_redundant_arr = np.empty(total_events, dtype=np.int32)
    num_within_1km_arr = np.empty(total_events, dtype=np.int32)
    ambulance_time_arr = np.empty(total_events, dtype=float)
    first_volunteer_arr = np.full(total_events, np.nan, dtype=float)
    cfr_beats_ems_arr = np.empty(total_events, dtype=bool)
    # Independent incident replications (fixed N): each OHCA starts at t=0 with a fresh
    # responder pool; no Poisson interarrival or cross-incident busy state (cf. van den Berg et al.).
    for event_idx in range(total_events):
        current_time = 0.0
        for r in responders:
            r.busy_until = 0.0

        def sample_event_distance():
            if distance_mode == "uniform_1km":
                # Uniform points over disk area: sample U ~ Unif(0,1) and set radius r = R*sqrt(U).
                # (Using r = R*U would make the *radius* uniform on [0,R], which clusters too many
                # points toward the center relative to area-uniform sampling.)
                return float(max_distance_km * np.sqrt(np.random.rand()))
            return float(sample_distance(env_config))

        for r in responders:
            r.distance_to_event = sample_event_distance()

        # Per-event acceptance cache:
        # a responder gets one acceptance realization for this event, reused
        # both inside policy logic and when deciding who actually travels.
        acceptance = {}
        decision_delay = {}
        original_deciders = {}

        def get_decision(r_obj):
            rid = r_obj.id
            if rid in acceptance:
                return decision_delay[rid], acceptance[rid]

            # No separate view/decision delay in arrival timing; acceptance uses base p only.
            d = 0.0
            a = bool(np.random.rand() < float(r_obj.acceptance_prob))
            decision_delay[rid] = d
            acceptance[rid] = a
            return d, a

        for r in responders:
            original_deciders[r.id] = r.decide_to_accept

            def _decide_to_accept_cached(_r=r):
                _, v = get_decision(_r)
                return v

            r.decide_to_accept = _decide_to_accept_cached

        phased_policy = policy_name in {"GoodSAM", "Hartslagnu"}

        def dispatch_goodsam_phased():
            cpr_group = [r for r in responders if r.has_cpr_training and r.is_available(current_time)]
            cpr_group.sort(key=lambda r: r.distance_to_event)

            stage1 = [r for r in cpr_group if r.distance_to_event <= 0.3][:3]
            alerted = list(stage1)

            def accepts_by_time(candidates, t_now):
                count = 0
                for rr in candidates:
                    d, a = get_decision(rr)
                    if a and d <= t_now:
                        count += 1
                return count

            # If any stage-1 accept arrives before first lag interval, stop.
            if accepts_by_time(stage1, phased_step_minutes) >= 1:
                return alerted

            expanded = [r for r in cpr_group if r.distance_to_event <= 3.0 and r.id not in {x.id for x in stage1}]
            idx = 0
            t_send = phased_step_minutes
            while t_send <= max_alert_minutes and idx < len(expanded):
                batch = expanded[idx: idx + 3]
                alerted.extend(batch)
                if accepts_by_time(alerted, t_send) >= 1:
                    break
                idx += 3
                t_send += phased_step_minutes
            return alerted

        def dispatch_hartslagnu_phased():
            cpr_group = [r for r in responders if r.has_cpr_training and r.is_available(current_time)]
            nearby = [r for r in cpr_group if r.distance_to_event <= 0.75]
            nearby.sort(key=lambda r: r.distance_to_event)

            alerted = []
            t_send = 0.0
            i = 0
            while t_send <= max_alert_minutes and i < len(nearby):
                alerted.append(nearby[i])
                i += 1
                t_send += phased_step_minutes
                accepts = 0
                for rr in alerted:
                    d, a = get_decision(rr)
                    if a and d <= t_send:
                        accepts += 1
                if accepts >= 5:
                    break
            return alerted

        if policy_name in ['static', 'dynamic']:
            if policy_name == 'static':
                alerted = static_policy(responders, num_alerts=5, current_time=current_time)
            else:
                alerted = dynamic_policy(responders, target_accepts=2, current_time=current_time)

            # ensure acceptance is materialized for alerted responders
            for r in alerted:
                acceptance[r.id] = r.decide_to_accept()
                decision_delay.setdefault(r.id, get_decision(r)[0])
        elif policy_name == "GoodSAM":
            alerted = dispatch_goodsam_phased()
            for r in alerted:
                d, a = get_decision(r)
                decision_delay[r.id] = d
                acceptance[r.id] = a
        elif policy_name == "Hartslagnu":
            alerted = dispatch_hartslagnu_phased()
            for r in alerted:
                d, a = get_decision(r)
                decision_delay[r.id] = d
                acceptance[r.id] = a
        else:
            policy_func = CFR_POLICIES.get(policy_name)
            if policy_func is None:
                raise ValueError(f"Unknown policy: {policy_name}")
            alerted = policy_func(responders, current_time)

            # ensure acceptance is materialized for alerted responders
            for r in alerted:
                acceptance[r.id] = r.decide_to_accept()
                decision_delay.setdefault(r.id, get_decision(r)[0])

        num_alerted_arr[event_idx] = len(alerted)
        num_within_1km_arr[event_idx] = sum(
            1 for r in responders if r.is_available(current_time) and r.distance_to_event <= 1.0
        )

        responder_arrivals = []  # (responder_id, arrival_time)
        for r in alerted:
            d_decision = float(decision_delay.get(r.id, 0.0))
            accepted_now = bool(acceptance.get(r.id, False))
            if phased_policy and d_decision > max_alert_minutes:
                accepted_now = False
            if accepted_now:
                dist = r.distance_to_event
                speed = sample_speed(env_config) / 60  # km/min
                travel_time = r.travel_time(dist, speed)
                response_delay = sample_response_delay_minutes()
                t_arrival = d_decision + travel_time + response_delay
                responder_arrivals.append((r.id, t_arrival))
                r.assign_task(current_time, t_arrival)

        # restore original acceptance behavior before next event
        for r in responders:
            r.decide_to_accept = original_deciders[r.id]

        t_ambulance = sample_ambulance_time_minutes(amb_mean, amb_std)
        all_arrival_times = [t for _, t in responder_arrivals] + [t_ambulance]

        t_first = min(all_arrival_times)
        redundant_responders = [
            r_id for r_id, t in responder_arrivals
            if t > t_first
        ]
        first_arrival_arr[event_idx] = t_first
        success_arr[event_idx] = t_first <= T_CRIT
        coverage5_arr[event_idx] = t_first <= 5
        num_accepted_arr[event_idx] = len(responder_arrivals)
        num_redundant_arr[event_idx] = len(redundant_responders)
        ambulance_time_arr[event_idx] = t_ambulance
        if responder_arrivals:
            t_vol = min(t for _, t in responder_arrivals)
            first_volunteer_arr[event_idx] = t_vol
            cfr_beats_ems_arr[event_idx] = bool(t_vol < t_ambulance)
        else:
            cfr_beats_ems_arr[event_idx] = False

    if return_event_level:
        df = pd.DataFrame(
            {
                "first_arrival_time": first_arrival_arr,
                "success": success_arr,
                "coverage_5": coverage5_arr,
                "num_alerted": num_alerted_arr,
                "num_accepted": num_accepted_arr,
                "num_redundant": num_redundant_arr,
                "num_within_1km": num_within_1km_arr,
                "ambulance_time": ambulance_time_arr,
                "first_volunteer_arrival": first_volunteer_arr,
                "cfr_beats_ems": cfr_beats_ems_arr,
            }
        )
        return df

    first_arrival = first_arrival_arr
    num_alerted = num_alerted_arr.astype(float, copy=False)
    num_accepted = num_accepted_arr.astype(float, copy=False)
    num_redundant = num_redundant_arr.astype(float, copy=False)
    cfr_beats_ems = cfr_beats_ems_arr.astype(float, copy=False)
    first_vol = first_volunteer_arr
    finite_fv = np.isfinite(first_vol)

    out = {
        "first_arrival_time": float(first_arrival.mean()),
        "num_redundant": float(num_redundant.mean()),
        "num_alerted": float(num_alerted.mean()),
        "num_accepted": float(num_accepted.mean()),
        "cfr_beats_ems": float(cfr_beats_ems.mean()),
        "first_volunteer_arrival": float(first_vol[finite_fv].mean()) if finite_fv.any() else np.nan,
    }
    for t in range(5, 11):
        out[f"coverage_{t}"] = float((first_arrival <= float(t)).mean())
    return out


def run_simulation_batch(
    policies,
    env_name="urban",
    num_responders=NUM_RESPONDERS,
    total_events=TOTAL_EVENTS_PER_REPLICATION,
    env_overrides=None,
    ambulance_mean=None,
    ambulance_std=None,
    acceptance_cfg=None,
    seed=None,
    distance_mode="uniform_1km",
    max_distance_km=1.0,
    phased_step_minutes=0.5,
    max_alert_minutes=10.0,
    verbose=True,
    return_event_level=True,
):
    dfs = {}
    for policy_name in policies:
        if verbose:
            print(f"Running simulation: {policy_name} in {env_name} environment...")
        df = run_simulation(
            policy_name=policy_name,
            env_name=env_name,
            num_responders=num_responders,
            total_events=total_events,
            env_overrides=env_overrides,
            ambulance_mean=ambulance_mean,
            ambulance_std=ambulance_std,
            acceptance_cfg=acceptance_cfg,
            seed=seed,
            distance_mode=distance_mode,
            max_distance_km=max_distance_km,
            phased_step_minutes=phased_step_minutes,
            max_alert_minutes=max_alert_minutes,
            return_event_level=return_event_level,
        )
        dfs[policy_name] = df
    return dfs


def run_single_event_trace(
    policy_name="static",
    env_name="urban",
    num_responders=NUM_RESPONDERS,
    env_overrides=None,
    ambulance_mean=None,
    ambulance_std=None,
    acceptance_cfg=None,
    seed=None,
    num_alerts_static=5,
    dynamic_target_accepts=2,
    angle_model="uniform",
    angle_mean=0.0,
    angle_std=1.0,
    average_conditions=False,
    distance_mode="uniform_1km",
    max_distance_km=1.0,
    phased_step_minutes=0.5,
    max_alert_minutes=10.0,
):
    """
    Run a single event and return a trace suitable for animation.

    Notes:
    - Times are *relative to the event start* (t=0 at the moment the event happens).
    - Responder positions are synthesized from sampled distances + a deterministic angle.
    """
    if seed is not None:
        np.random.seed(seed)

    env_config = ENVIRONMENTS[env_name].copy()
    if env_overrides:
        env_config.update(env_overrides)

    if ambulance_mean is None:
        amb_mean = env_config.get("ambulance_mean", AMBULANCE_MEAN)
    else:
        amb_mean = ambulance_mean
    if ambulance_std is None:
        amb_std = env_config.get("ambulance_std", AMBULANCE_STD)
    else:
        amb_std = ambulance_std

    responders = create_responders(
        num_responders=num_responders,
        env_name=env_name,
        acceptance_cfg=acceptance_cfg,
    )

    def sample_event_distance():
        if distance_mode == "uniform_1km":
            # Uniform points over disk area: sample U ~ Unif(0,1) and set radius r = R*sqrt(U).
            # (Using r = R*U would make the *radius* uniform on [0,R], which clusters too many
            # points toward the center relative to area-uniform sampling.)
            return float(max_distance_km * np.sqrt(np.random.rand()))
        return float(sample_distance(env_config))

    # Assign distances to this event.
    for r in responders:
        r.distance_to_event = sample_event_distance()

    # Decision timing + acceptance (matches `run_simulation`): no separate view/decision delay;
    # acceptance uses base probability only.
    decision_delay: dict[int, float] = {}
    acceptance: dict[int, bool] = {}

    def get_decision(r_obj):
        rid = r_obj.id
        if rid in acceptance:
            return decision_delay[rid], acceptance[rid]

        d = 0.0
        a = bool(np.random.rand() < float(r_obj.acceptance_prob))

        decision_delay[rid] = d
        acceptance[rid] = a
        return d, a

    # Cache so policies that call `decide_to_accept()` internally
    # (e.g. dynamic policy / PulsePoint_and_myResponder selection logic) see consistent results.
    for r in responders:
        def _decide_to_accept_cached(_r=r):
            _, v = get_decision(_r)
            return v

        r.decide_to_accept = _decide_to_accept_cached

    current_time = 0.0  # event-relative time for policy logic
    phased_policy = policy_name in {"GoodSAM", "Hartslagnu"}

    def dispatch_goodsam_phased():
        # Stage-1: nearest CPR responders within 300m (up to 3). If any accepts
        # before the first lag interval, stop; otherwise progressively alert
        # batches of 3 from a wider radius.
        cpr_group = [r for r in responders if r.has_cpr_training and r.is_available(current_time)]
        cpr_group.sort(key=lambda r: r.distance_to_event)

        stage1 = [r for r in cpr_group if r.distance_to_event <= 0.3][:3]
        alerted = list(stage1)

        def accepts_by_time(candidates, t_now):
            count = 0
            for rr in candidates:
                d, a = get_decision(rr)
                if a and d <= t_now:
                    count += 1
            return count

        # If any stage-1 accept arrives before the first lag interval, stop.
        if accepts_by_time(stage1, phased_step_minutes) >= 1:
            return alerted

        expanded = [r for r in cpr_group if r.distance_to_event <= 3.0 and r.id not in {x.id for x in stage1}]
        idx = 0
        t_send = phased_step_minutes
        while t_send <= max_alert_minutes and idx < len(expanded):
            batch = expanded[idx : idx + 3]
            alerted.extend(batch)
            if accepts_by_time(alerted, t_send) >= 1:
                break
            idx += 3
            t_send += phased_step_minutes
        return alerted

    def dispatch_hartslagnu_phased():
        # CPR-capable within 750m, sequential alerts every `phased_step_minutes`
        # until 5 accepts occur by the current send time (or we hit max radius/time).
        cpr_group = [r for r in responders if r.has_cpr_training and r.is_available(current_time)]
        nearby = [r for r in cpr_group if r.distance_to_event <= 0.75]
        nearby.sort(key=lambda r: r.distance_to_event)

        alerted = []
        t_send = 0.0
        i = 0
        while t_send <= max_alert_minutes and i < len(nearby):
            alerted.append(nearby[i])
            i += 1
            t_send += phased_step_minutes

            accepts = 0
            for rr in alerted:
                d, a = get_decision(rr)
                if a and d <= t_send:
                    accepts += 1
            if accepts >= 5:
                break
        return alerted

    # Decide which responders are alerted.
    if policy_name in ["static", "dynamic"]:
        if policy_name == "static":
            alerted = static_policy(responders, num_alerts=num_alerts_static, current_time=current_time)
        else:
            alerted = dynamic_policy(
                responders,
                target_accepts=dynamic_target_accepts,
                current_time=current_time,
            )
    elif policy_name == "GoodSAM":
        alerted = dispatch_goodsam_phased()
    elif policy_name == "Hartslagnu":
        alerted = dispatch_hartslagnu_phased()
    else:
        policy_func = CFR_POLICIES.get(policy_name)
        if policy_func is None:
            raise ValueError(f"Unknown policy: {policy_name}")
        alerted = policy_func(responders, current_time)

    alerted_ids = {r.id for r in alerted}

    # Ambulance response time is relative to event start.
    if average_conditions:
        t_ambulance = max(0.0, float(amb_mean))
    else:
        t_ambulance = float(sample_ambulance_time_minutes(amb_mean, amb_std))

    # Pre-sample distances so we can also derive a plausible ambulance start radius.
    distances = np.array([float(r.distance_to_event) for r in responders], dtype=float)

    # Ambulance schematic placement (start somewhere around the event, move straight to origin).
    amb_start_r = float(np.mean(distances)) * 1.2 if distances.size else 1.0
    amb_start_r = max(amb_start_r, 0.5)

    amb_angle_rng = np.random.default_rng(0 if seed is None else int(seed) + 999_001)
    if angle_model == "uniform" or angle_model == "random":
        amb_angle = float(amb_angle_rng.uniform(0.0, 2 * np.pi))
    elif angle_model == "gaussian":
        # Wrapped normal on [0, 2pi) via modulo.
        amb_angle = float((amb_angle_rng.normal(loc=angle_mean, scale=angle_std) % (2 * np.pi)))
    elif angle_model == "exponential":
        # Bias angles near 0 then wrap around; not physically perfect, but a useful "skewed" option.
        theta = float(amb_angle_rng.exponential(scale=max(angle_std, 1e-6)))
        amb_angle = float(theta % (2 * np.pi))
    else:
        raise ValueError(f"Unknown angle_model: {angle_model}")

    ambulance_start_x = amb_start_r * float(np.cos(amb_angle))
    ambulance_start_y = amb_start_r * float(np.sin(amb_angle))

    responder_traces = []
    accepted_arrival_times = []

    # Materialize acceptance + decision delay for all alerted responders so arrival
    # times match the same conditional logic used in `run_simulation`.
    for r in alerted:
        get_decision(r)

    base_seed = 0 if seed is None else seed
    for r in responders:
        dist = float(r.distance_to_event)
        # Deterministic angle per responder id (stable given the same seed).
        angle_rng = np.random.default_rng(base_seed + int(r.id) * 100_003)
        if angle_model == "uniform" or angle_model == "random":
            angle = float(angle_rng.uniform(0.0, 2 * np.pi))
        elif angle_model == "gaussian":
            # Wrapped normal on [0, 2pi) via modulo.
            angle = float((angle_rng.normal(loc=angle_mean, scale=angle_std) % (2 * np.pi)))
        elif angle_model == "exponential":
            theta = float(angle_rng.exponential(scale=max(angle_std, 1e-6)))
            angle = float(theta % (2 * np.pi))
        else:
            raise ValueError(f"Unknown angle_model: {angle_model}")

        alerted_flag = r.id in alerted_ids
        accepted_flag = False
        arrival_time = None
        start_move_time = None
        speed = None
        travel_time = None

        if alerted_flag:
            d_decision = float(decision_delay.get(r.id, 0.0))
            accepted_now = bool(acceptance.get(r.id, False))

            # GoodSAM/Hartslagnu: if a responder's accept happens after their phased
            # alerting window, treat it as "not accepted now".
            if phased_policy and d_decision > max_alert_minutes:
                accepted_now = False

            accepted_flag = accepted_now

            if accepted_flag:
                if average_conditions:
                    speed = float(env_config["speed_mean"]) / 60.0  # km/min
                else:
                    speed = sample_speed(env_config) / 60.0  # km/min
                travel_time = float(r.travel_time(dist, speed))

                # Delay between acceptance and being ready to act (matches simulator).
                if average_conditions:
                    response_delay = float(mean_response_delay_minutes())
                else:
                    response_delay = sample_response_delay_minutes()

                # Simulator total arrival is:
                #   t_arrival = d_decision + travel_time + response_delay
                arrival_time = float(d_decision + travel_time + response_delay)

                # For the animation, start movement after d_decision + response_delay,
                # so movement duration visually matches travel_time.
                start_move_time = float(d_decision + response_delay)

                accepted_arrival_times.append(arrival_time)

        responder_traces.append(
            {
                "id": int(r.id),
                "alerted": alerted_flag,
                "accepted": accepted_flag,
                "distance": dist,
                "angle": angle,
                "start_move_time": start_move_time,
                "arrival_time": arrival_time,
                "speed_km_per_min": speed,
                "travel_time_min": travel_time,
            }
        )

    t_first = min([t_ambulance] + accepted_arrival_times)
    success = t_first <= T_CRIT
    responder_first = any(abs(t - t_first) < 1e-9 for t in accepted_arrival_times)
    ambulance_first = abs(t_ambulance - t_first) < 1e-9
    if responder_first and ambulance_first:
        first_source = "tie"
    elif responder_first:
        first_source = "responder"
    else:
        first_source = "ambulance"

    redundant_arrivals = int(sum(1 for t in accepted_arrival_times if t > t_first))

    return {
        "policy": policy_name,
        "environment": env_name,
        "num_responders": int(num_responders),
        "t_first": float(t_first),
        "t_ambulance": float(t_ambulance),
        "success": bool(success),
        "first_source": first_source,
        "redundant_arrivals": redundant_arrivals,
        "ambulance_start_x": float(ambulance_start_x),
        "ambulance_start_y": float(ambulance_start_y),
        "responders": responder_traces,
    }
