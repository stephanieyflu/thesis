def get_policy(name):
    """
    Return alert policy configuration
    """
    if name == "PolicyA":
        return {"type": "static", "num_alerts": 1}
    elif name == "PolicyB":
        return {"type": "static", "num_alerts": 3}
    elif name == "PolicyC":
        return {"type": "static", "num_alerts": 5}
    elif name == "Dynamic":
        # adjust based on population density or event rate
        return {"type": "dynamic"}
    else:
        raise ValueError(f"Unknown policy: {name}")

def determine_alerts(policy, env_name, num_available):
    """
    Decide how many responders to alert
    """
    if policy["type"] == "static":
        return min(policy["num_alerts"], num_available)
    elif policy["type"] == "dynamic":
        # example heuristic: alert more responders in rural (sparser) areas
        if env_name == "urban":
            return min(2, num_available)
        else:
            return min(5, num_available)