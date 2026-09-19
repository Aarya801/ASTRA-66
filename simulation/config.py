"""Loads and validates simulation/sim_config.json (non-propulsion simulation settings)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_CONFIG_FILE = os.path.join(HERE, "sim_config.json")

_RANGES = {
    ("launch_site", "site_elevation_m"): (-500.0, 5000.0),
    ("launch_site", "temp_offset_K"): (-60.0, 60.0),
    ("aerodynamics", "surface_roughness_m"): (0.0, 1e-3),
    ("aerodynamics", "protuberance_fraction"): (0.0, 1.0),
    ("integration", "dt_burn_s"): (1e-5, 0.01),
    ("integration", "dt_coast_s"): (1e-5, 0.05),
    ("integration", "dt_descent_s"): (1e-4, 0.5),
    ("integration", "t_max_s"): (10.0, 3600.0),
}


def load_sim_config(path=SIM_CONFIG_FILE):
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    errs = []
    for (sec, key), (lo, hi) in _RANGES.items():
        v = cfg.get(sec, {}).get(key)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
            errs.append(f"{sec}.{key} = {v!r} (allowed {lo}..{hi})")
    rl = cfg.get("rail", {}).get("length_m")
    if rl is not None and (not isinstance(rl, (int, float)) or not 0.1 <= rl <= 20.0):
        errs.append(f"rail.length_m = {rl!r} (null or 0.1..20 m)")
    if errs:
        raise ValueError("simulation/sim_config.json invalid: " + "; ".join(errs))
    return cfg
