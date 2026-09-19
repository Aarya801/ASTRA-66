"""Controlled one-at-a-time sensitivity study of NON-propulsion parameters.

Varied: airframe mass, payload mass, airframe CG location, drag-coefficient scale, air density
(scale factor, site elevation and ISA temperature offset), and the low-cost build (camera/GPS removed).
The motor input is held fixed at whatever simulation/motor_config.json names (currently the PLACEHOLDER
TEST INPUT), so absolute values are illustrative; the DELTAS show which assumptions matter.
"""
import flight_simulation as FS
import mass_properties as MP

DEFAULTS = dict(mass_scale=1.0, payload_g=0, cg_shift_mm=0, cd_scale=1.0, density_scale=1.0, site_elevation_m=0, temp_offset_K=0,
                rail_length_m=FS.A.RAIL_L)
METRICS = ("apogee_m", "v_max_mps", "a_max_g", "rail_exit_v_mps", "sm_liftoff", "sm_rail_exit", "sm_burnout", "descent_rate_mps", "t_apogee_s")

GROUPS = [
    ("Airframe mass", "mass_scale", [0.8, 0.9, 1.0, 1.1, 1.2], "x", "all non-motor mass scaled, CG unchanged"),
    ("Payload mass", "payload_g", [0, 50, 100, 150, 200, 300], "g", "added at the payload-bay centre (STA %.0f)" % MP.PAYLOAD_X),
    ("Airframe CG shift", "cg_shift_mm", [-30, -20, -10, 0, 10, 20, 30], "mm", "+ = aft; trajectory unchanged in 1-DOF"),
    ("Drag coefficient", "cd_scale", [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3], "x", "multiplier on the build-up Cd"),
    ("Air density", "density_scale", [0.90, 0.95, 1.0, 1.05, 1.10], "x", "multiplier on ISA density"),
    ("Site elevation", "site_elevation_m", [0, 500, 1000, 1500, 2000], "m", "ISA standard day"),
    ("ISA temperature offset", "temp_offset_K", [-15, 0, 15, 30], "K", "sea-level site"),
    ("Launch rail length", "rail_length_m", [1.0, 1.5, 2.0, 2.5, 3.0], "m", "range equipment; affects rail-exit speed only"),
]


def run_one(motor, **kw):
    run = FS.simulate(FS.SimConfig(**kw), motor)
    s = FS.summarize(run)
    return {k: s[k] for k in METRICS}


def run_all(motor):
    base = run_one(motor)
    out = dict(baseline=base, groups=[])
    for name, param, values, unit, note in GROUPS:
        rows = []
        for val in values:
            res = base if val == DEFAULTS[param] else run_one(motor, **{param: val})
            rows.append(dict(value=val, **res))
        out["groups"].append(dict(name=name, param=param, unit=unit, note=note, rows=rows))
    lc = run_one(motor, remove=MP.LOW_COST_REMOVED)
    out["low_cost"] = dict(removed=list(MP.LOW_COST_REMOVED), **lc)
    grid = []
    for dT in (-15, 0, 15):
        for elev in (0, 500, 1000, 1500, 2000):
            grid.append(dict(dT=dT, elev=elev, apogee_m=run_one(motor, site_elevation_m=elev, temp_offset_K=dT)["apogee_m"]))
    out["elev_temp_grid"] = grid
    return out
