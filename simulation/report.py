"""Writes the simulation results: JSON summary, Markdown reports, CSV tables and SVG plots."""
import csv
import json
import math
import os

import aerodynamics as AERO
import atmosphere as ATM
import flight_simulation as FS
import mass_properties as MP
import plotting as PL
import stability as STAB

A = FS.A
HERE = FS.HERE
ROOT = FS.ROOT
RES, PLOTS = FS.RESULTS, FS.PLOTS
DOC = os.path.join(ROOT, "documentation")
BANNER = ("> **PLACEHOLDER TEST INPUT.** `simulation/motor_config.json` has `status: PLACEHOLDER`. The thrust curve is the synthetic signal "
          "`simulation/motors/PLACEHOLDER_TEST_INPUT.eng`: it is not a real motor, a product or performance data. Trajectory numbers here verify "
          "the software and show sensitivities only. They are **not predictions** and must not be used for flight planning. The design is **not "
          "flight certified**; a qualified mentor or institution must review it before any flight.\n")


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def f(v, n=1):
    return "—" if v is None else (f"{v:,.{n}f}" if isinstance(v, (int, float)) else str(v))


def ok(b):
    return "PASS" if b else "FAIL"


# ---------------------------------------------------------------------------------------------- plots
def make_plots(ctx):
    rows, ev, s = ctx["base"]["rows"], ctx["base"]["events"], ctx["summary"]
    ph = ctx["motor_status"] == "PLACEHOLDER"
    tag = " (PLACEHOLDER TEST INPUT: illustrative)" if ph else ""
    files = []

    def P(name):
        files.append(name)
        return os.path.join(PLOTS, name)
    t = [r["t"] for r in rows]
    vl = [(ev["burnout"]["t"], "burnout"), (ev["apogee"]["t"], "apogee")]
    PL.line_plot(P("altitude_vs_time.svg"), [dict(label="altitude", x=t, y=[r["h"] for r in rows])], "Time since ignition (s)", "Altitude above launch site (m)",
                 "Altitude vs time" + tag, "1-DOF vertical flight; main parachute idealised as fully open at apogee", vlines=vl,
                 points=[(ev["apogee"]["t"], ev["apogee"]["h"], f"apogee {ev['apogee']['h']:.0f} m")])
    PL.line_plot(P("velocity_vs_time.svg"), [dict(label="velocity", x=t, y=[r["v"] for r in rows])], "Time since ignition (s)", "Vertical velocity (m/s, + up)",
                 "Velocity vs time" + tag, f"Rail exit {s['rail_exit_v_mps']:.1f} m/s; descent {s['descent_rate_mps']:.2f} m/s", vlines=vl,
                 points=[(s["t_v_max_s"], s["v_max_mps"], f"max {s['v_max_mps']:.1f} m/s")])
    asc = [r for r in rows if r["t"] <= ev["apogee"]["t"] + 1]
    PL.line_plot(P("acceleration_vs_time.svg"), [dict(label="acceleration", x=[r["t"] for r in asc], y=[r["a"] / ATM.G0 for r in asc])], "Time since ignition (s)",
                 "Axial acceleration (g)", "Acceleration vs time (ascent)" + tag, "Net acceleration (thrust - drag - weight) / m, in standard g", vlines=vl)
    tb = ctx["motor"]["burn_time_s"]
    tt = [i * (tb + 0.3) / 400 for i in range(401)]
    import motor as MOT
    mot = MOT.load_motor()
    PL.line_plot(P("thrust_input_vs_time.svg"), [dict(label="thrust", x=tt, y=[mot.thrust(x) for x in tt])], "Time since ignition (s)", "Thrust (N)",
                 ("PLACEHOLDER TEST INPUT thrust signal: not a real motor" if ph else f"Thrust curve: {ctx['motor']['name']}"),
                 f"Read from {ctx['motor']['source']} (RASP format); the simulation accepts the certified motor's published file here")
    PL.line_plot(P("vehicle_mass_vs_time.svg"), [dict(label="mass", x=tt, y=[MP.Vehicle().mass_kg(mot.mass_kg(x)) * 1000 for x in tt])], "Time since ignition (s)",
                 "Vehicle mass (g)", "Vehicle mass during burn" + tag, "Airframe mass CAD-derived; motor mass from motor_config.json (placeholder)")
    PL.line_plot(P("static_margin_vs_time.svg"), [dict(label="static margin", x=[r["t"] for r in asc], y=[r["sm"] for r in asc])], "Time since ignition (s)",
                 "Static margin (calibres)", "Static margin vs time" + tag, "CG moves forward as propellant is used; CP fixed (subsonic Barrowman)",
                 bands=[(STAB.SM_MIN, STAB.SM_MAX, "target 1.5-3.0 cal (requirement)")], vlines=vl, ylim=(0, 4))
    mach = [0.02 + i * 0.28 / 40 for i in range(41)]
    s0 = ATM.isa(0)
    comps = [AERO.drag_coefficient(M, M * s0["a"] * AERO.L / s0["nu"], False) for M in mach]
    PL.line_plot(P("drag_coefficient_vs_mach.svg"), [dict(label="total (coasting)", x=mach, y=[c["total"] for c in comps]),
                                                    dict(label="skin friction", x=mach, y=[c["friction"] for c in comps], dash=True),
                                                    dict(label="base", x=mach, y=[c["base"] for c in comps], dash=True),
                                                    dict(label="fin pressure", x=mach, y=[c["fin_pressure"] for c in comps], dash=True)],
                 "Mach number", "Drag coefficient (ref. body area)", "Drag build-up vs Mach (ASSUMPTION model)",
                 "Sea-level ISA; Reynolds number from speed and body length; +8 % protuberance allowance in total", ylim=(0, 0.6))
    G = {g["name"]: g for g in ctx["sens"]["groups"]}

    def grp(name, key):
        g = G[name]
        return [r["value"] for r in g["rows"]], [r[key] for r in g["rows"]]
    x, y = grp("Drag coefficient", "apogee_m")
    PL.line_plot(P("apogee_vs_drag_scale.svg"), [dict(label="apogee", x=x, y=y, markers=True)], "Drag-coefficient multiplier (-)", "Apogee (m)",
                 "Apogee sensitivity to drag assumption" + tag, "Baseline = 1.0 x build-up Cd")
    x, y = grp("Airframe mass", "apogee_m")
    PL.line_plot(P("apogee_vs_airframe_mass.svg"), [dict(label="apogee", x=x, y=y, markers=True)], "Airframe mass multiplier (-)", "Apogee (m)",
                 "Apogee sensitivity to airframe mass" + tag, f"Baseline airframe (without motor) {ctx['base']['vehicle']['airframe_g']:.0f} g")
    x, y = grp("Payload mass", "apogee_m")
    PL.line_plot(P("apogee_vs_payload_mass.svg"), [dict(label="apogee", x=x, y=y, markers=True)], "Added payload mass (g)", "Apogee (m)",
                 "Apogee sensitivity to payload mass" + tag, "Payload added at the payload-bay centre")
    g = G["Payload mass"]
    PL.line_plot(P("static_margin_vs_payload_mass.svg"), [dict(label="liftoff", x=[r["value"] for r in g["rows"]], y=[r["sm_liftoff"] for r in g["rows"]], markers=True),
                                                         dict(label="rail exit", x=[r["value"] for r in g["rows"]], y=[r["sm_rail_exit"] for r in g["rows"]], markers=True),
                                                         dict(label="burnout", x=[r["value"] for r in g["rows"]], y=[r["sm_burnout"] for r in g["rows"]], markers=True, dash=True)],
                 "Added payload mass (g)", "Static margin (calibres)", "Static margin vs payload mass",
                 "Forward payload moves the CG forward and raises the margin", bands=[(STAB.SM_MIN, STAB.SM_MAX, "target 1.5-3.0 cal")], ylim=(0, 4))
    g = G["Airframe CG shift"]
    PL.line_plot(P("static_margin_vs_cg_shift.svg"), [dict(label="liftoff", x=[r["value"] for r in g["rows"]], y=[r["sm_liftoff"] for r in g["rows"]], markers=True),
                                                     dict(label="rail exit", x=[r["value"] for r in g["rows"]], y=[r["sm_rail_exit"] for r in g["rows"]], markers=True)],
                 "Airframe CG shift (mm, + = aft)", "Static margin (calibres)", "Static margin vs CG location error",
                 "Models build/measurement error in the airframe CG", bands=[(STAB.SM_MIN, STAB.SM_MAX, "target 1.5-3.0 cal")], ylim=(0, 4))
    grid = ctx["sens"]["elev_temp_grid"]
    PL.line_plot(P("apogee_vs_site_elevation.svg"), [dict(label=f"ISA {dT:+d} K", x=[r["elev"] for r in grid if r["dT"] == dT],
                                                         y=[r["apogee_m"] for r in grid if r["dT"] == dT], markers=True) for dT in (-15, 0, 15)],
                 "Launch-site elevation (m)", "Apogee above site (m)", "Apogee sensitivity to air density" + tag, "Density varied through site elevation and day temperature")
    g = G["Launch rail length"]
    PL.line_plot(P("rail_exit_velocity_vs_rail_length.svg"), [dict(label="rail-exit velocity", x=[r["value"] for r in g["rows"]], y=[r["rail_exit_v_mps"] for r in g["rows"]], markers=True)],
                 "Launch rail length (m)", "Rail-exit velocity (m/s)", "Rail-exit velocity vs rail length" + tag,
                 "Guidance lost when the aft rail button leaves the rail", bands=[(15.0, max(25.0, max(r["rail_exit_v_mps"] for r in g["rows"]) + 2), ">= 15 m/s guideline")], ylim=(0, max(25.0, max(r["rail_exit_v_mps"] for r in g["rows"]) + 2)))
    b = ctx["sens"]["baseline"]

    def ends(name, key, lo_note, hi_note):
        rr = G[name]["rows"]
        return dict(label=name, low=rr[0][key], high=rr[-1][key], low_note=lo_note, high_note=hi_note)
    PL.tornado(P("tornado_apogee.svg"), [ends("Airframe mass", "apogee_m", "x0.8", "x1.2"), ends("Payload mass", "apogee_m", "0 g", "+300 g"),
                                          ends("Drag coefficient", "apogee_m", "x0.7", "x1.3"), ends("Air density", "apogee_m", "x0.90", "x1.10"),
                                          ends("Site elevation", "apogee_m", "0 m", "2000 m"), ends("ISA temperature offset", "apogee_m", "-15 K", "+30 K")],
               b["apogee_m"], "Apogee (m)", "Apogee sensitivity (one-at-a-time)" + tag, "Bars span the tested range of each non-propulsion assumption")
    PL.tornado(P("tornado_static_margin.svg"), [ends("Airframe mass", "sm_rail_exit", "x0.8", "x1.2"), ends("Payload mass", "sm_rail_exit", "0 g", "+300 g"),
                                                 ends("Airframe CG shift", "sm_rail_exit", "-30 mm", "+30 mm")],
               b["sm_rail_exit"], "Static margin at rail exit (calibres)", "Rail-exit static-margin sensitivity",
               "Drag, density and temperature do not move CG or CP in this model")
    return files


def placeholder_dependency(ph):
    """Which results depend on placeholder propulsion data (motor_config.json / .eng)."""
    p = "DEPENDS ON PLACEHOLDER" if ph else "uses manufacturer data"
    return {
        "apogee, velocity, acceleration, dynamic pressure, burnout state, coast time, rail-exit speed": p + " (thrust curve, motor mass)",
        "static margin at liftoff / rail exit / burnout": p + " (motor mass and CG station)",
        "descent rate, descent time": p + " (burnout mass)",
        "burn-phase base drag": p + " (MMT_ID sets the exhaust-filled base area)",
        "no-motor static margin, airframe mass and CG": ("motor excluded, but includes the PLACEHOLDER retainer mass (RET_MASS) and the MMT, "
                                                         "retainer envelope and fin-tab depth sized from placeholder data") if ph else "manufacturer data",
        "CP (Barrowman on CAD geometry)": "independent of propulsion data",
        "drag build-up coefficients (coast)": "independent of propulsion data (ASSUMPTION model)",
        "sensitivity deltas": "trends are meaningful; absolute values " + ("DEPEND ON PLACEHOLDER" if ph else "use manufacturer data"),
    }


# ---------------------------------------------------------------------------------------------- reports
def write_all(ctx):
    os.makedirs(RES, exist_ok=True)
    os.makedirs(PLOTS, exist_ok=True)
    for fn in os.listdir(PLOTS):
        if fn.endswith(".svg"):
            os.remove(os.path.join(PLOTS, fn))
    plots = make_plots(ctx)
    s, a, ev = ctx["summary"], ctx["audit"], ctx["base"]["events"]
    ph = ctx["motor_status"] == "PLACEHOLDER"
    cad_cp = STAB.cp_from_cad(a)
    R_dry = MP.Vehicle()
    cg_nomotor = R_dry.air_x
    sm_nomotor = STAB.margin(cad_cp["cp"], cg_nomotor, a["body_od_mm"])
    req = STAB.check(s["sm_rail_exit"], s["sm_min_powered"], s["sm_liftoff"])
    lc = ctx["sens"]["low_cost"]
    v_lc = MP.Vehicle(remove=MP.LOW_COST_REMOVED)
    ballast_lc = STAB.ballast_for(STAB.SM_MIN, v_lc.cg_mm(A.MOTOR_M0 / 1000), v_lc.mass_kg(A.MOTOR_M0 / 1000) * 1000, cad_cp["cp"],
                                  a["body_od_mm"], A.X["sh_end"] - A.BALLAST_ROD_L / 2)

    # --- sensitivity CSV
    with open(os.path.join(RES, "sensitivity_table.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "parameter", "value", "unit"] + list(ctx["sens"]["baseline"].keys()))
        for g in ctx["sens"]["groups"]:
            for r in g["rows"]:
                w.writerow([g["name"], g["param"], r["value"], g["unit"]] + [f"{r[k]:.4f}" if isinstance(r[k], float) else r[k] for k in ctx["sens"]["baseline"]])

    # --- flight_summary.json
    summary = dict(
        project="ASTRA-66", generated=ctx["date"], model="1-DOF vertical point mass, RK4", cad_rev=a["cad_rev"],
        motor_data_status=ctx["motor_status"], trajectory_uses_placeholder_propulsion=ph, results_are_predictions=False, valid_for_flight_planning=False,
        disclaimer=("PLACEHOLDER TEST INPUT: illustrative software/sensitivity results only; not representative of any real motor. " if ph else
                    "1-DOF model estimates; validate against OpenRocket and flight data. ") +
                   "Draft student design, not flight certified; requires qualified mentor/range review.",
        placeholder_dependency=placeholder_dependency(ph),
        motor_input=ctx["motor"], vehicle=dict(liftoff_mass_g=s["mass_liftoff_g"], burnout_mass_g=s["mass_burnout_g"], airframe_mass_g=ctx["base"]["vehicle"]["airframe_g"],
                                             airframe_cg_mm=ctx["base"]["vehicle"]["airframe_cg_mm"], cp_mm=cad_cp["cp"], body_od_mm=a["body_od_mm"], length_mm=a["length_mm"]),
        aerodynamics=ctx["aero"], sim_config=ctx["cfg"], results=s, events=ev, envelope_checks=ctx["envelope"], ejection_timing=ctx["timing"],
        stability_requirements=req, verification=ctx["verification"], plots=[f"simulation/plots/{p}" for p in plots])
    with open(os.path.join(RES, "flight_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=float)

    # --- stability_report.md
    Sm = [BANNER if ph else "", "# ASTRA-66 stability report\n",
          f"Generated {ctx['date']} by `simulation/flight_simulation.py` from CAD rev {a['cad_rev']} ({a['cad_summary']['FAIL']} FAIL in CAD validation).\n",
          "Target range used below is an **engineering requirement** (1.5–3.0 calibres, from the package's operating envelope), not a flight approval.\n",
          "## 1. Centre of pressure\n",
          table(["Source", "CNα nose", "CNα fins", "CNα total /rad", "CP STA mm"], [
              ["Independent Barrowman on CAD-measured geometry (`stability.py`)", f(cad_cp["cn_nose"], 2), f(cad_cp["cn_fins"], 3), f(cad_cp["cn_alpha"], 3), f(cad_cp["cp"], 2)],
              ["`analysis.py` (design parameters)", "2.00", f(A.run()["bw"]["cn_f"], 3), f(A.run()["bw"]["cn"], 3), f(a["cp_mm"], 2)]]),
          f"\nCAD geometry used: nose {a['nose_len_mm']:.1f} mm; fins N={a['fin_n']}, root {a['fin_root_mm']:.1f}, tip {a['fin_tip_mm']:.1f}, "
          f"semispan {a['fin_semispan_mm']:.1f}, LE sweep {a['fin_sweep_mm']:.1f} mm; LE at STA {a['fin_le_mm']:.1f}; d = {a['body_od_mm']:.1f} mm.\n",
          "## 2. Centre of gravity and static margin\n",
          table(["Condition", "Mass g", "CG STA mm", "Static margin cal", "Data basis"], [
              ["No motor (airframe only)", f(R_dry.air_g), f(cg_nomotor), f(sm_nomotor, 2),
               "A×C airframe; motor excluded but includes placeholder retainer mass and MMT geometry" if ph else "A×C airframe"],
              ["Liftoff", f(s["mass_liftoff_g"]), f(ctx["base"]["rows"][0]["cg"]), f(s["sm_liftoff"], 2), "includes D placeholder motor" if ph else "manufacturer data"],
              [f"Rail exit (t = {s['t_rail_exit_s']:.2f} s)", "—", "—", f(s["sm_rail_exit"], 2), "placeholder" if ph else ""],
              ["Minimum during powered flight", "—", "—", f(s["sm_min_powered"], 2), "placeholder" if ph else ""],
              ["Burnout", f(s["mass_burnout_g"]), "—", f(s["sm_burnout"], 2), "placeholder" if ph else ""]]),
          "\n## 3. Requirement check\n",
          table(["ID", "Requirement", "Value cal", "Result"], [[r["id"], r["requirement"], f(r["value"], 2), ok(r["ok"]) + (" (placeholder motor)" if ph else "")] for r in req]),
          "\n## 4. Sensitivity of the margin\n"]
    G = {g["name"]: g for g in ctx["sens"]["groups"]}
    for name in ("Airframe mass", "Payload mass", "Airframe CG shift"):
        g = G[name]
        Sm.append(f"**{name}** ({g['note']})\n")
        Sm.append(table([f"{g['param']} [{g['unit']}]", "SM liftoff", "SM rail exit", "SM burnout", "REQ-STAB-1"],
                        [[r["value"], f(r["sm_liftoff"], 2), f(r["sm_rail_exit"], 2), f(r["sm_burnout"], 2), ok(STAB.SM_MIN <= r["sm_rail_exit"] <= STAB.SM_MAX)] for r in g["rows"]]))
        Sm.append("")
    Sm.append(f"**Low-cost build** (removes {', '.join(lc['removed'])}): SM liftoff {lc['sm_liftoff']:.2f}, rail exit {lc['sm_rail_exit']:.2f}, burnout {lc['sm_burnout']:.2f} cal. "
              f"Nose ballast needed to restore a 1.5 cal liftoff margin: {ballast_lc:.0f} g.\n")
    cg_lim = [r for r in G["Airframe CG shift"]["rows"]]
    pr = G["Payload mass"]["rows"]
    p_lim = next((a_["value"] + (STAB.SM_MAX - a_["sm_liftoff"]) / (b_["sm_liftoff"] - a_["sm_liftoff"]) * (b_["value"] - a_["value"])
                  for a_, b_ in zip(pr, pr[1:]) if a_["sm_liftoff"] <= STAB.SM_MAX < b_["sm_liftoff"]), None)
    Sm.append("## 5. Findings\n")
    if p_lim is not None:
        Sm.append(f"- **Payload limit:** more than about **{p_lim:.0f} g** added at the payload-bay centre pushes the liftoff margin above 3.0 cal (over-stable, strong weathercocking). "
                  "Heavier payloads need mentor agreement, a more aft position, or a re-check with the real motor, which usually lowers the margin.\n")
    Sm.append(f"- CP from the CAD geometry agrees with `analysis.py` to {abs(cad_cp['cp'] - a['cp_mm']):.3f} mm.\n"
              f"- The airframe **without a motor** has {sm_nomotor:.2f} cal. This value excludes the motor but still contains the placeholder retainer mass "
              f"({A.RET_MASS:.0f} g) and the MMT sized from placeholder data. Any motor adds mass aft and lowers the margin: the heavier the certified motor, "
              "the lower the margin (see the `analysis/analysis.py` sensitivity).\n"
              f"- Every 10 mm of airframe CG error changes the margin by about {abs(cg_lim[-1]['sm_rail_exit'] - cg_lim[0]['sm_rail_exit']) / 6:.2f} cal. **Measure the CG with the real motor installed** (test T-03).\n"
              f"- Liftoff margin with the placeholder motor ({s['sm_liftoff']:.2f} cal) sits in the upper half of the target range. A heavier motor, more aft paint/epoxy or a lighter nose moves it down.\n")
    Sm.append("## 6. Limitations\n- Barrowman: subsonic, small angle of attack, no body lift, rigid body, no fin–body interference beyond K_FB. OpenRocket/RASAero cross-check required.\n"
              "- Static margin only; dynamic stability (pitch damping, roll coupling) is not assessed.\n- Masses are CAD volume × assumed density/fill, plus assumed electronics and recovery masses. Weigh every part.\n")
    with open(os.path.join(RES, "stability_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(Sm) + "\n")

    # --- sensitivity_report.md
    b = ctx["sens"]["baseline"]
    Sn = [BANNER if ph else "", "# ASTRA-66 sensitivity report\n",
          f"One-at-a-time variation of **non-propulsion** parameters around the baseline. The motor input is held fixed ({ctx['motor']['name']}, "
          f"{'placeholder' if ph else 'manufacturer data'}). Absolute values are illustrative while the placeholder is used; the relative changes show which assumptions matter.\n",
          f"Baseline: apogee {b['apogee_m']:.1f} m, v_max {b['v_max_mps']:.1f} m/s, a_max {b['a_max_g']:.1f} g, rail exit {b['rail_exit_v_mps']:.1f} m/s, "
          f"SM rail exit {b['sm_rail_exit']:.2f} cal, descent {b['descent_rate_mps']:.2f} m/s.\n"]
    for g in ctx["sens"]["groups"]:
        Sn.append(f"## {g['name']}: `{g['param']}` [{g['unit']}]\n\n{g['note']}\n")
        Sn.append(table([g["unit"], "apogee m", "Δ apogee %", "v_max m/s", "a_max g", "rail exit m/s", "SM rail cal", "descent m/s"],
                        [[r["value"], f(r["apogee_m"]), f((r["apogee_m"] / b["apogee_m"] - 1) * 100, 1), f(r["v_max_mps"]), f(r["a_max_g"], 2),
                          f(r["rail_exit_v_mps"], 2), f(r["sm_rail_exit"], 2), f(r["descent_rate_mps"], 2)] for r in g["rows"]]))
        Sn.append("")
    swings = []
    for g in ctx["sens"]["groups"]:
        if g["param"] == "rail_length_m":
            continue
        vals = [r["apogee_m"] for r in g["rows"]]
        swings.append((g["name"], (max(vals) - min(vals)) / b["apogee_m"] * 100, f"{g['rows'][0]['value']}…{g['rows'][-1]['value']} {g['unit']}"))
    swings.sort(key=lambda x: -x[1])
    Sn.append("## Ranking (apogee swing over the tested range)\n")
    Sn.append(table(["Parameter", "Tested range", "Apogee swing %"], [[n, rng, f(sw, 1)] for n, sw, rng in swings]))
    Sn.append("\n## Observations\n"
              f"- Largest apogee driver over the tested ranges: **{swings[0][0]}** ({swings[0][1]:.0f} %). Next: {swings[1][0]} ({swings[1][1]:.0f} %).\n"
              "- CG location and payload placement drive the static margin; drag and density do not (1-DOF, CP fixed).\n"
              + (lambda rr: f"- **Rail-exit speed** is {rr[0]['rail_exit_v_mps']:.1f} m/s on a {rr[0]['value']:.1f} m rail and {rr[-1]['rail_exit_v_mps']:.1f} m/s on a {rr[-1]['value']:.1f} m rail "
                            f"with the placeholder input, against the 15 m/s guideline. The rail offered by the range, and the certified motor's early thrust, must be checked together (mentor/RSO).\n")(
                  [g for g in ctx["sens"]["groups"] if g["param"] == "rail_length_m"][0]["rows"]) +
              "- Descent rate depends on burnout mass and air density only (parachute Cd·A fixed).\n"
              "- The drag build-up is the least verified input. Cross-check it with OpenRocket/RASAero and, after flight, with altimeter data.\n")
    Sn.append("Plots: " + ", ".join(f"`simulation/plots/{p}`" for p in plots if "tornado" in p or "vs_" in p) + "\n")
    with open(os.path.join(RES, "sensitivity_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(Sn) + "\n")

    write_validation_doc(ctx, plots, cad_cp, req, sm_nomotor, swings)
    return plots + ["results/flight_summary.json", "results/stability_report.md", "results/sensitivity_report.md", "results/sensitivity_table.csv",
                    "results/trajectory_baseline.csv", "documentation/SIMULATION_VALIDATION.md"]


def write_validation_doc(ctx, plots, cad_cp, req, sm_nomotor, swings):
    s, a, m = ctx["summary"], ctx["audit"], ctx["motor"]
    ph = ctx["motor_status"] == "PLACEHOLDER"
    geo = ctx["aero"]
    L = [BANNER if ph else "", "# ASTRA-66 — Simulation validation report\n",
         f"Generated {ctx['date']} by `simulation/flight_simulation.py` (run as part of `python run_validation.py`). CAD rev {a['cad_rev']}, "
         f"CAD validation {a['cad_summary']['PASS']} PASS / {a['cad_summary']['WARN']} WARN / {a['cad_summary']['FAIL']} FAIL. Motor data status: **{ctx['motor_status']}**.\n",
         "## 1. Inputs\n",
         table(["Input", "Value", "Source", "Class"], [
             ["Body diameter / length", f"{a['body_od_mm']:.1f} / {a['length_mm']:.1f} mm", "CAD meshes (validation_results.json)", "A"],
             ["Fins", f"N={a['fin_n']}, root {a['fin_root_mm']:.0f}, tip {a['fin_tip_mm']:.0f}, semispan {a['fin_semispan_mm']:.0f}, sweep {a['fin_sweep_mm']:.0f}, t {a['fin_t_mm']:.0f} mm", "CAD meshes", "A"],
             ["Airframe mass / CG (no motor)", f"{ctx['base']['vehicle']['airframe_g']:.1f} g / STA {ctx['base']['vehicle']['airframe_cg_mm']:.1f}", "analysis.py mass budget (21 CAD-derived items)", "A×C + C"],
             ["Motor total / propellant mass", f"{m['total_mass_g']:.0f} / {m['prop_mass_g']:.0f} g", "motor_config.json + .eng", "D" if ph else "manufacturer"],
             ["Thrust-time input", f"{m['name']}: {m['total_impulse_Ns']:.1f} N·s, {m['burn_time_s']:.2f} s", m["source"], "D (synthetic test signal)" if ph else "manufacturer"],
             ["Drag coefficient", f"build-up, {s['cd_at_v_max']:.3f} at v_max", "aerodynamics.py", "C"],
             ["Parachute", f"⌀{A.CHUTE_D:.0f} mm, Cd {A.CHUTE_CD}", "analysis.py", "C"],
             ["Rail length / travel to guidance loss", f"{ctx['cfg']['rail_length_m']:.2f} m / {ctx['base']['rail_travel_m']:.3f} m", "analysis.py RAIL_L (USER), button station", "C/USER"],
             ["Atmosphere", "ISA, sea-level site, no wind", "atmosphere.py", "C"]]),
         "\n## 2. Equations and methods\n",
         "- **Atmosphere:** ISO 2533 ISA troposphere/tropopause; Sutherland viscosity.\n"
         "- **Motion:** `m(t) dv/dt = T(t) − ½ρ v|v| C_d A_ref − m g`, `dh/dt = v`. Classical RK4 with dt = 1 ms (burn), 5 ms (coast), 20 ms (descent).\n"
         "- **Motor mass:** `m_motor(t) = m_total − m_prop · I(t)/I_total` (thrust-curve read-only, RASP .eng format).\n"
         "- **Drag:** component build-up.\n"
         "  - Skin friction: `max(0.074 Re^-0.2, 0.032 (ε/L)^0.2)` with form factor `1 + 1/(2 L/D)`.\n"
         "  - Base drag: `0.12 + 0.13 M²`, with the MMT bore filled by exhaust during the burn.\n"
         "  - Fin leading/trailing-edge pressure terms, plus an 8 % protuberance allowance.\n"
         f"  - Reference area {geo['A_ref_m2'] * 1e4:.2f} cm²; wetted areas: body {geo['S_body_wet_m2']:.4f} m², fins {geo['S_fins_wet_m2']:.4f} m².\n"
         "- **Stability:** Barrowman CP re-implemented independently in `stability.py` from CAD-measured geometry; margin = (CP − CG)/d, with CG(t) from the airframe plus the burning motor.\n"
         "- **Recovery:** after apogee, drag = ½ρ v|v| C_d,chute A_chute (idealised instant deployment at apogee; body drag neglected).\n"
         "- **Verification:** closed-form comparisons, a time-step convergence test and cross-checks against analysis.py (§6).\n",
         "## 3. Assumptions\n",
         "- **Flight model:** vertical 1-DOF flight with no wind, no weathercocking and no angle of attack. The rail only defines where guidance is lost.\n"
         "- **Drag:** the build-up coefficients, 20 µm surface roughness and 8 % protuberance allowance are ASSUMPTIONS.\n"
         "- **Recovery:** the parachute opens fully at apogee. The real timing depends on the certified motor's ejection delay (see the ejection-timing table).\n"
         "- **Mass:** masses are CAD volume × assumed density/fill. Electronics, recovery, paint and adhesive masses are estimates.\n"
         "- **Atmosphere:** ISA standard day at a sea-level site unless varied. Gravity is constant (9.80665 m/s²).\n",
         "## 4. Verified CAD-derived values (class A)\n",
         table(["Quantity", "Value"], [["Overall length", f"{a['length_mm']:.1f} mm"], ["Body OD", f"{a['body_od_mm']:.1f} mm"], ["Fin span tip-to-tip", f"{a['fin_span_mm']:.1f} mm"],
                                        ["Fin root LE station", f"{a['fin_le_mm']:.1f} mm"], ["Fin root / tip / sweep", f"{a['fin_root_mm']:.1f} / {a['fin_tip_mm']:.1f} / {a['fin_sweep_mm']:.1f} mm"],
                                        ["Nose length", f"{a['nose_len_mm']:.1f} mm"],
                                        ["Structural part masses", f"{sum(v for k, v in a['mass_by_class'].items() if k.startswith('A')):.1f} g (CAD volume × assumed density)"],
                                        ["CP (from CAD geometry)", f"STA {cad_cp['cp']:.2f} mm (class B, computed from A)"]]),
         "\n## 5. Placeholder values (class D)\n",
         table(["Item", "Value", "Replace with"], [
             ["Motor total / burnout mass", f"{m['total_mass_g']:.0f} / {m['burnout_mass_g']:.0f} g", "certified motor data (motor_config.json)"],
             ["Motor length / MMT / retainer", f"{A.MOTOR_L:.0f} mm / ⌀{A.MMT_ID:.0f}×{A.MMT_L:.0f} mm / ⌀{A.RET_CLEAR_D - 1:.0f} mm", "manufacturer drawings"],
             ["Thrust-time curve", f"{m['name']} (synthetic)", "certified motor's published .eng file"],
             ["Retainer mass (in airframe mass, also in the no-motor margin)", f"{A.RET_MASS:.0f} g", "weighed commercial retainer"],
             ["Burn-phase base-drag relief area", f"MMT_ID ⌀{A.MMT_ID:.0f} mm", "certified motor/MMT data"],
             ["Camera, battery, switch envelopes", "see analysis/results/parameters.csv (USER)", "measured parts"],
             ["Rail length", f"{ctx['cfg']['rail_length_m']:.1f} m", "range data"]] if ph else [["(none for propulsion)", "", ""]]),
         f"\nMass by data class: " + "; ".join(f"{k}: {v:.0f} g" for k, v in a["mass_by_class"].items()) + "\n",
         "## 6. Simulation outputs\n",
         table(["Result", "Value", "Note"], [
             ["Thrust-to-weight, peak / average", f"{s['peak_T_over_W']:.1f} / {s['average_T_over_W']:.1f}", ("placeholder input; " if ph else "") + f"liftoff (T > W) at t = {s['t_liftoff_s']:.3f} s"],
             ["Rail-exit velocity", f"{s['rail_exit_v_mps']:.1f} m/s", "at t = %.2f s" % s["t_rail_exit_s"]],
             ["Burnout", f"t {s['t_burnout_s']:.2f} s, h {s['h_burnout_m']:.1f} m, v {s['v_burnout_mps']:.1f} m/s", ""],
             ["Max velocity / Mach", f"{s['v_max_mps']:.1f} m/s / {s['mach_max']:.3f}", ""], ["Max acceleration", f"{s['a_max_g']:.1f} g", ""],
             ["Max dynamic pressure", f"{s['q_max_Pa']:.0f} Pa", ""], ["Apogee", f"{s['apogee_m']:.1f} m at t = {s['t_apogee_s']:.2f} s", "illustrative" if ph else ""],
             ["Coast burnout → apogee", f"{s['coast_to_apogee_s']:.2f} s", "compare with the motor's delay options (mentor)"],
             ["Descent rate / time", f"{s['descent_rate_mps']:.2f} m/s / {s['descent_time_s']:.1f} s", "chute ⌀%.0f mm" % A.CHUTE_D]]),
         "\n**Envelope checks (design limits from the package):**\n",
         table(["Check", "Value", "Result"], [[e["item"], f(e["value"], 2), ok(e["ok"]) + (" (placeholder)" if ph else "")] for e in ctx["envelope"]]),
         "\n**Recovery-event timing sensitivity** (speed if the event happens Δt from apogee, ballistic):\n",
         table(["Δt s", "speed m/s", "altitude m"], [[t_["offset_s"], f(t_["speed_mps"], 1), f(t_["altitude_m"], 1)] for t_ in ctx["timing"]]),
         "\n**Numerical verification:**\n",
         table(["Check", "Expected", "Computed", "Tolerance", "Result"],
               [[v["check"], f(v["expected"], 5) if isinstance(v["expected"], float) else v["expected"], f(v["computed"], 5), v["tolerance"], ok(v["ok"])] for v in ctx["verification"]]),
         "\n## 7. Stability results\n",
         table(["Condition", "Static margin cal"], [["No motor", f(sm_nomotor, 2)], ["Liftoff", f(s["sm_liftoff"], 2)], ["Rail exit", f(s["sm_rail_exit"], 2)],
                                                   ["Min. powered", f(s["sm_min_powered"], 2)], ["Burnout", f(s["sm_burnout"], 2)]]),
         "\n" + table(["Requirement", "Value", "Result"], [[r["id"] + " " + r["requirement"], f(r["value"], 2), ok(r["ok"])] for r in req]),
         "\n**Placeholder dependence:**\n",
         table(["Result", "Dependence on propulsion data"], [[k, v] for k, v in placeholder_dependency(ph).items()]),
         "\nDetails: `simulation/results/stability_report.md`.\n",
         "## 8. Sensitivity results\n",
         table(["Parameter (tested range)", "Apogee swing %"], [[f"{n} ({rng})", f(sw, 1)] for n, sw, rng in swings]),
         "\nDetails: `simulation/results/sensitivity_report.md`, `simulation/results/sensitivity_table.csv`.\n",
         "## 9. Limitations\n",
         "- 1-DOF: no wind, weathercocking, angle of attack, rail tip-off or drift. Apogee would be lower with a tilted rail or wind.\n"
         "- Barrowman CP and the drag build-up are low-order methods, uncalibrated against wind-tunnel or flight data.\n"
         "- Deployment is idealised at apogee. Opening shock, snatch loads and chute inflation time are not modelled here (see package §7.6 loads).\n"
         "- **With the placeholder motor, trajectory values are not performance predictions.**\n",
         "## 10. Items requiring real-world validation\n",
         "- **T-03** Weigh every module and measure the CG with the actual motor installed. Update analysis.py and re-run.\n"
         "- Drag coefficient: cross-check with OpenRocket and RASAero; after flight, compare with altimeter/IMU data.\n"
         "- Parachute Cd and descent rate: drop test (package T-series), then flight data.\n"
         "- Printed-part densities and fills: weigh the printed parts.\n"
         "- Rail length, site elevation and expected temperature: use the actual range values.\n",
         "## 11. Items requiring qualified mentor / range review\n",
         "- Selection of a legally obtainable certified motor. Its published data go into `simulation/motor_config.json` (`status: MANUFACTURER_DATA`) together with its official `.eng` file, then the pipeline is re-run.\n"
         "- Ejection-delay choice from the manufacturer's options, using the simulated coast time and the timing table above.\n"
         "- Stability margin with the real motor and measured CG, and rail-exit velocity against the range's rules.\n"
         "- Recovery hardware ratings, retainer installation, and the complete flight-readiness review (package §18).\n"
         "- Confirmation that the flight envelope (apogee, field size, wind) fits the range's limits.\n",
         "## Plots\n", "\n".join(f"- `simulation/plots/{p}`" for p in plots) + "\n"]
    with open(os.path.join(DOC, "SIMULATION_VALIDATION.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
