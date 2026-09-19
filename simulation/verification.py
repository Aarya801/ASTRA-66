"""Numerical verification of the simulation code against closed-form solutions and independent calculations.

Each check returns dict(check, expected, computed, tolerance, ok, method).
"""
import math

import aerodynamics as AERO
import atmosphere as ATM
import flight_simulation as FS
import mass_properties as MP
import motor as MOT
import stability as STAB

A = FS.A
G = ATM.G0


def _chk(name, expected, computed, tol, method, rel=True):
    err = abs(computed - expected) / abs(expected) if rel and expected else abs(computed - expected)
    return dict(check=name, expected=expected, computed=computed, tolerance=(f"{tol * 100:.2g} %" if rel else f"{tol:g}"),
                ok=err <= tol, method=method)


def run_all():
    out = []
    # 1-3 atmosphere against ISO 2533 table values
    out.append(_chk("ISA density at 0 m [kg/m3]", 1.2250, ATM.isa(0)["rho"], 5e-4, "ISO 2533 table"))
    out.append(_chk("ISA density at 11 000 m [kg/m3]", 0.36392, ATM.isa(11000)["rho"], 1e-3, "ISO 2533 table"))
    out.append(_chk("ISA speed of sound at 0 m [m/s]", 340.294, ATM.isa(0)["a"], 1e-4, "ISO 2533 table"))
    # 4-5 motor interface
    m = MOT.load_motor()
    n = 20000
    num = sum(m.thrust((i + 0.5) * m.burn_time / n) for i in range(n)) * m.burn_time / n
    out.append(_chk("Thrust-curve impulse, midpoint quadrature vs piecewise-analytic [N s]", m.total_impulse, num, 1e-4, "20 000-panel midpoint rule"))
    out.append(_chk("Motor mass after burnout [g]", (m.total_mass - m.prop_mass) * 1000, m.mass_kg(m.burn_time + 1) * 1000, 1e-9, "m_total - m_prop"))
    # 6-7 integrator: constant thrust, constant mass, no drag -> closed form
    T0, tb = 60.0, 2.0
    tm = MOT.Motor([(0.0, T0), (tb, T0), (tb + 1e-6, 0.0)], total_mass_kg=0.110, prop_mass_kg=0.0, name="VERIFY-CONST")
    run = FS.simulate(FS.SimConfig(deploy="none"), tm, drag=False)
    veh = MP.Vehicle()
    mass = veh.mass_kg(0.110)
    t0 = run["events"]["liftoff"]["t"]
    acc = T0 / mass - G
    hb = 0.5 * acc * (tb - t0) ** 2
    vb = acc * (tb - t0)
    out.append(_chk("Burnout altitude, constant thrust & mass, no drag [m]", hb, run["events"]["burnout"]["h"], 1e-3, "h = a t^2 / 2"))
    out.append(_chk("Apogee, same case [m]", hb + vb ** 2 / (2 * G), run["events"]["apogee"]["h"], 1e-3, "h_b + v_b^2 / 2g"))
    # 8 terminal descent under the main parachute
    base = FS.simulate(FS.SimConfig(), m)
    mb = base["rows"][-1]["m"]
    vt = math.sqrt(2 * mb * G / (ATM.isa(0)["rho"] * A.CHUTE_CD * math.pi * (A.CHUTE_D / 2000) ** 2))
    out.append(_chk("Landing descent rate vs terminal velocity [m/s]", vt, abs(base["events"]["landing"]["v"]), 5e-3, "v_t = sqrt(2 m g / (rho Cd A))"))
    # 9 time-step convergence
    fine = FS.simulate(FS.SimConfig(dt_burn=0.0005, dt_coast=0.0025, dt_descent=0.01), m)
    out.append(_chk("Apogee time-step convergence (dt halved)", base["events"]["apogee"]["h"], fine["events"]["apogee"]["h"], 1e-3, "RK4, dt vs dt/2"))
    # 10-11 mass properties and CP against the analysis / CAD
    R = A.run()
    v0 = MP.Vehicle()
    out.append(_chk("Liftoff mass: simulation vehicle vs analysis.py [g]", R["M0"], v0.mass_kg(A.MOTOR_M0 / 1000) * 1000, 1e-6, "same CAD-derived items"))
    out.append(_chk("Liftoff CG: simulation vehicle vs analysis.py [mm]", R["cg0"], v0.cg_mm(A.MOTOR_M0 / 1000), 1e-6, "same CAD-derived items"))
    cad_cp = STAB.cp_from_cad(MP.audit_cached())["cp"]
    out.append(_chk("CP: independent Barrowman on CAD-measured geometry vs analysis.py [mm]", R["bw"]["xcp"], cad_cp, 0.05, "re-implemented equations", rel=False))
    # 12 drag plausibility (band is an assumption, not a truth)
    s = ATM.isa(0)
    cd = AERO.drag_coefficient(50 / s["a"], 50 * AERO.L / s["nu"], False)["total"]
    out.append(dict(check="Build-up Cd at 50 m/s coasting within 0.35-0.75 (plausibility band for similar model rockets, ASSUMPTION)",
                    expected="0.35-0.75", computed=cd, tolerance="band", ok=0.35 <= cd <= 0.75, method="component build-up"))
    return out


if __name__ == "__main__":
    for c in run_all():
        print(("PASS " if c["ok"] else "FAIL ") + c["check"], c["expected"], round(c["computed"], 6) if isinstance(c["computed"], float) else c["computed"])
