"""ASTRA-66 one-degree-of-freedom vertical flight simulation and results pipeline.

    python simulation/flight_simulation.py

Model (point mass, vertical, non-rotating flat Earth, no wind):
    m(t) dv/dt = T(t) - D - m g ,   D = 1/2 rho(h) v|v| Cd(M, Re) A_ref ,   dh/dt = v
    m(t) = m_airframe + m_motor(t)            (motor.py: impulse-proportional propellant use)
Phases: pad (T <= m g) -> rail (guided, until the aft button leaves the rail) -> powered -> coast ->
apogee -> descent under the main parachute (idealised: full inflation at apogee) -> landing.
Integration: classical 4th-order Runge-Kutta, dt = 1 ms while thrusting, 5 ms coasting, 20 ms on the chute.

WITH THE PLACEHOLDER TEST INPUT THE TRAJECTORY IS ILLUSTRATIVE ONLY -- it verifies the software and shows
sensitivities, it is not a performance prediction for any real motor.
"""
import csv
import datetime
import json
import math
import os
import sys
from dataclasses import dataclass, asdict, field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "analysis"))

import analysis as A  # noqa: E402
import atmosphere as ATM  # noqa: E402
import config as CFG  # noqa: E402
import aerodynamics as AERO  # noqa: E402
import mass_properties as MP  # noqa: E402
import motor as MOT  # noqa: E402
import stability as STAB  # noqa: E402

G = ATM.G0
RESULTS = os.path.join(HERE, "results")
PLOTS = os.path.join(HERE, "plots")
SC = CFG.load_sim_config()
_RAIL = SC["rail"]["length_m"] if SC["rail"]["length_m"] is not None else A.RAIL_L


@dataclass
class SimConfig:
    rail_length_m: float = _RAIL                                   # USER: sim_config.json or analysis RAIL_L
    site_elevation_m: float = SC["launch_site"]["site_elevation_m"]   # USER: sim_config.json
    temp_offset_K: float = SC["launch_site"]["temp_offset_K"]         # USER: sim_config.json
    cd_scale: float = 1.0                      # sensitivity multiplier on the drag build-up
    density_scale: float = 1.0                 # sensitivity multiplier on air density
    mass_scale: float = 1.0                    # sensitivity multiplier on airframe (non-motor) mass
    payload_g: float = 0.0                     # extra payload at the payload-bay centre
    cg_shift_mm: float = 0.0                   # airframe CG shift (affects stability only in 1-DOF)
    deploy: str = "apogee"                     # "apogee" (idealised) | "none" (ballistic, for timing table)
    remove: tuple = ()                         # mass items removed (e.g. low-cost build)
    dt_burn: float = SC["integration"]["dt_burn_s"]
    dt_coast: float = SC["integration"]["dt_coast_s"]
    dt_descent: float = SC["integration"]["dt_descent_s"]
    t_max: float = SC["integration"]["t_max_s"]
    label: str = "baseline"


def validate_config(cfg):
    """Reject physically meaningless settings instead of silently simulating them."""
    guide = (A.X["end"] - A.X["rb_aft"]) / 1000.0
    errs = []
    if not cfg.rail_length_m > guide:
        errs.append(f"rail_length_m {cfg.rail_length_m} must exceed the aft-button-to-tail distance {guide:.3f} m")
    for n in ("cd_scale", "density_scale", "mass_scale"):
        if not getattr(cfg, n) > 0:
            errs.append(f"{n} must be > 0")
    if cfg.payload_g < 0:
        errs.append("payload_g must be >= 0")
    if not -500 <= cfg.site_elevation_m <= 5000:
        errs.append("site_elevation_m outside -500..5000 m")
    if not -60 <= cfg.temp_offset_K <= 60:
        errs.append("temp_offset_K outside -60..60 K")
    if not abs(cfg.cg_shift_mm) <= 200:
        errs.append("cg_shift_mm outside +/-200 mm")
    if min(cfg.dt_burn, cfg.dt_coast, cfg.dt_descent) <= 0:
        errs.append("time steps must be > 0")
    if cfg.deploy not in ("apogee", "none"):
        errs.append("deploy must be 'apogee' or 'none'")
    if errs:
        raise ValueError("invalid SimConfig: " + "; ".join(errs))


def rk4_step(f, t, y, dt):
    k1 = f(t, y)
    k2 = f(t + dt / 2, [y[i] + dt / 2 * k1[i] for i in range(len(y))])
    k3 = f(t + dt / 2, [y[i] + dt / 2 * k2[i] for i in range(len(y))])
    k4 = f(t + dt, [y[i] + dt * k3[i] for i in range(len(y))])
    return [y[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(len(y))]


def simulate(cfg=None, motor=None, drag=True):
    cfg = cfg or SimConfig()
    validate_config(cfg)
    motor = motor or MOT.load_motor()
    veh = MP.Vehicle(cfg.mass_scale, cfg.payload_g, cg_shift_mm=cfg.cg_shift_mm, remove=cfg.remove)
    rail_travel = cfg.rail_length_m - (A.X["end"] - A.X["rb_aft"]) / 1000.0
    chute_cda = A.CHUTE_CD * math.pi * (A.CHUTE_D / 2000.0) ** 2
    cp = STAB.cp_from_cad(MP.audit_cached())["cp"]
    d_mm = A.BODY_OD

    def air(h):
        s = ATM.isa(cfg.site_elevation_m + h, cfg.temp_offset_K)
        s["rho"] *= cfg.density_scale
        s["nu"] = s["mu"] / s["rho"]
        return s

    state = dict(phase="pad")

    def forces(t, h, v):
        m = veh.mass_kg(motor.mass_kg(t))
        T = motor.thrust(t)
        s = air(h)
        mach = abs(v) / s["a"]
        re = abs(v) * AERO.L / s["nu"]
        if state["phase"] == "descent":
            cd = 0.0
            Dm = 0.5 * s["rho"] * v * abs(v) * chute_cda
        else:
            cd = AERO.drag_coefficient(mach, re, T > 0)["total"] * cfg.cd_scale if drag else 0.0
            Dm = 0.5 * s["rho"] * v * abs(v) * cd * AERO.A_REF
        return m, T, Dm, cd, mach, s

    def f(t, y):
        h, v = y
        m, T, Dm, *_ = forces(t, h, v)
        return [v, (T - Dm) / m - G]

    t, y = 0.0, [0.0, 0.0]
    rows, ev = [], {}

    def record(t, y):
        m, T, Dm, cd, mach, s = forces(t, y[0], y[1])
        a = 0.0 if state["phase"] == "pad" else (T - Dm) / m - G
        rows.append(dict(t=t, h=y[0], v=y[1], a=a, m=m, T=T, D=Dm, cd=cd, mach=mach, q=0.5 * s["rho"] * y[1] ** 2,
                         cg=veh.cg_mm(motor.mass_kg(t)), sm=STAB.margin(cp, veh.cg_mm(motor.mass_kg(t)), d_mm), phase=state["phase"]))

    record(t, y)
    while t < cfg.t_max:
        ph = state["phase"]
        if ph == "pad":
            dt = cfg.dt_burn
            t += dt
            m = veh.mass_kg(motor.mass_kg(t))
            if motor.thrust(t) > m * G:
                state["phase"] = "rail"
                ev["liftoff"] = dict(t=t, T_over_W=motor.thrust(t) / (m * G))
            record(t, y)
            if t > motor.burn_time:
                raise RuntimeError("thrust never exceeds weight: no liftoff")
            continue
        dt = cfg.dt_burn if t < motor.burn_time else (cfg.dt_descent if ph == "descent" else cfg.dt_coast)
        if t < motor.burn_time < t + dt:
            dt = motor.burn_time - t
        y_new = rk4_step(f, t, y, dt)
        t_new = t + dt
        if ph == "rail" and y_new[0] >= rail_travel:
            fr = (rail_travel - y[0]) / (y_new[0] - y[0])
            ev["rail_exit"] = dict(t=t + fr * dt, h=rail_travel, v=y[1] + fr * (y_new[1] - y[1]),
                                   sm=STAB.margin(cp, veh.cg_mm(motor.mass_kg(t + fr * dt)), d_mm))
            state["phase"] = "powered" if t_new < motor.burn_time else "coast"
        if ph in ("rail", "powered") and t_new >= motor.burn_time - 1e-12 and "burnout" not in ev:
            ev["burnout"] = dict(t=t_new, h=y_new[0], v=y_new[1])
            if state["phase"] == "powered":
                state["phase"] = "coast"
        if state["phase"] in ("coast", "powered") and y[1] > 0 >= y_new[1]:
            fr = y[1] / (y[1] - y_new[1])
            ev["apogee"] = dict(t=t + fr * dt, h=y[0] + fr * (y_new[0] - y[0]))
            if cfg.deploy == "apogee":
                state["phase"] = "descent"
            else:
                state["phase"] = "ballistic"
        t, y = t_new, y_new
        if "apogee" in ev and y[0] <= 0:
            fr = rows[-1]["h"] / (rows[-1]["h"] - y[0]) if rows[-1]["h"] != y[0] else 1.0
            ev["landing"] = dict(t=rows[-1]["t"] + fr * (t - rows[-1]["t"]), v=rows[-1]["v"] + fr * (y[1] - rows[-1]["v"]))
            y = [0.0, y[1]]
            record(t, y)
            break
        record(t, y)
    return dict(cfg=asdict(cfg), rows=rows, events=ev, motor=motor.describe(), vehicle=dict(airframe_g=veh.air_g, airframe_cg_mm=veh.air_x,
                                                                                         motor_x_mm=veh.motor_x), cp_mm=cp, rail_travel_m=rail_travel)


def summarize(run):
    rows, ev = run["rows"], run["events"]
    up = [r for r in rows if r["phase"] in ("rail", "powered", "coast")]
    vmax = max(up, key=lambda r: r["v"])
    amax = max(up, key=lambda r: r["a"])
    qmax = max(up, key=lambda r: r["q"])
    powered = [r for r in rows if r["phase"] in ("rail", "powered")]
    desc = [r for r in rows if r["phase"] == "descent"]
    return dict(
        apogee_m=ev["apogee"]["h"], t_apogee_s=ev["apogee"]["t"], v_max_mps=vmax["v"], t_v_max_s=vmax["t"], mach_max=vmax["mach"],
        a_max_g=amax["a"] / G, q_max_Pa=qmax["q"], cd_at_v_max=vmax["cd"], t_liftoff_s=ev["liftoff"]["t"],
        peak_T_over_W=run["motor"]["peak_thrust_N"] / (rows[0]["m"] * G), average_T_over_W=run["motor"]["average_thrust_N"] / (rows[0]["m"] * G),
        rail_exit_v_mps=ev["rail_exit"]["v"], t_rail_exit_s=ev["rail_exit"]["t"], sm_rail_exit=ev["rail_exit"]["sm"],
        t_burnout_s=ev["burnout"]["t"], h_burnout_m=ev["burnout"]["h"], v_burnout_mps=ev["burnout"]["v"],
        coast_to_apogee_s=ev["apogee"]["t"] - ev["burnout"]["t"],
        sm_liftoff=rows[0]["sm"], sm_min_powered=min(r["sm"] for r in powered), sm_burnout=[r for r in rows if r["t"] >= ev["burnout"]["t"]][0]["sm"],
        mass_liftoff_g=rows[0]["m"] * 1000, mass_burnout_g=[r for r in rows if r["t"] >= ev["burnout"]["t"]][0]["m"] * 1000,
        descent_rate_mps=abs(desc[-1]["v"]) if desc else None, t_landing_s=ev.get("landing", {}).get("t"),
        descent_time_s=(ev["landing"]["t"] - ev["apogee"]["t"]) if "landing" in ev else None,
    )


def envelope_checks(s):
    return [
        dict(item="Rail-exit velocity >= 15 m/s (guideline)", value=s["rail_exit_v_mps"], ok=s["rail_exit_v_mps"] >= 15.0),
        dict(item=f"Max velocity <= {A.V_MAX:.0f} m/s (airframe design limit)", value=s["v_max_mps"], ok=s["v_max_mps"] <= A.V_MAX),
        dict(item=f"Max axial acceleration <= {A.N_AX:.0f} g (design load factor)", value=s["a_max_g"], ok=s["a_max_g"] <= A.N_AX),
        dict(item="Mach < 0.3 (incompressible assumptions valid)", value=s["mach_max"], ok=s["mach_max"] < 0.3),
        dict(item="Descent rate 4.5-6.0 m/s (package target)", value=s["descent_rate_mps"], ok=s["descent_rate_mps"] is not None and 4.5 <= s["descent_rate_mps"] <= 6.0),
    ]


def ejection_timing(ballistic, t_apogee):
    """Speed if the recovery event occurs dt seconds from apogee (ballistic trajectory, no chute)."""
    rows = ballistic["rows"]
    out = []
    for dt in (-3, -2, -1, 0, 1, 2, 3):
        tt = t_apogee + dt
        r = min(rows, key=lambda r: abs(r["t"] - tt))
        out.append(dict(offset_s=dt, speed_mps=abs(r["v"]), altitude_m=r["h"]))
    return out


def write_trajectory(run, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "altitude_m", "velocity_mps", "accel_mps2", "mass_kg", "thrust_N", "drag_N", "cd", "mach", "q_Pa", "cg_mm", "static_margin_cal", "phase"])
        for r in run["rows"]:
            w.writerow([f"{r['t']:.4f}", f"{r['h']:.3f}", f"{r['v']:.3f}", f"{r['a']:.3f}", f"{r['m']:.5f}", f"{r['T']:.2f}", f"{r['D']:.3f}",
                        f"{r['cd']:.4f}", f"{r['mach']:.4f}", f"{r['q']:.1f}", f"{r['cg']:.2f}", f"{r['sm']:.4f}", r["phase"]])


def main():
    import report
    import sensitivity
    import verification
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(PLOTS, exist_ok=True)
    motor = MOT.load_motor()
    audit = MP.audit_cached()
    base = simulate(SimConfig(), motor)
    ballistic = simulate(SimConfig(deploy="none", label="ballistic"), motor)
    s = summarize(base)
    write_trajectory(base, os.path.join(RESULTS, "trajectory_baseline.csv"))
    sens = sensitivity.run_all(motor)
    verif = verification.run_all()
    ctx = dict(date=datetime.date.today().isoformat(), audit=audit, motor=motor.describe(), motor_status=A.MOTOR_STATUS, base=base, summary=s,
               envelope=envelope_checks(s), timing=ejection_timing(ballistic, s["t_apogee_s"]), sens=sens, verification=verif,
               aero=AERO.geometry(), cfg=asdict(SimConfig()))
    files = report.write_all(ctx)
    ok_verif = all(v["ok"] for v in verif)
    print(f"apogee {s['apogee_m']:.1f} m (PLACEHOLDER TEST INPUT)  v_max {s['v_max_mps']:.1f} m/s  a_max {s['a_max_g']:.1f} g  "
          f"rail exit {s['rail_exit_v_mps']:.1f} m/s  SM rail {s['sm_rail_exit']:.2f} cal  descent {s['descent_rate_mps']:.2f} m/s")
    print(f"verification {sum(v['ok'] for v in verif)}/{len(verif)} passed; files written: {len(files)}")
    return 0 if ok_verif else 1


if __name__ == "__main__":
    sys.exit(main())
