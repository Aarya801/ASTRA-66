#!/usr/bin/env python3
"""ASTRA-66 complete non-hazardous validation pipeline: one command.

    python run_validation.py                              # uses the committed CAD validation, checks it is current
    python run_validation.py --with-cad --openscad PATH   # also re-renders and re-validates the CAD (~3 min)

Steps
  1. build.py                    engineering package, BOM, parameters (analysis/analysis.py is the source of truth)
  2. CAD integration             re-run cad/build_cad.py (--with-cad) OR verify the committed CAD validation matches the
                                 current parameters (params SHA-256) and has 0 FAIL
  3. flight simulation           simulation/flight_simulation.py: trajectory, stability, sensitivity, verification,
                                 plots, reports, documentation/SIMULATION_VALIDATION.md
  4. avionics integration        simulation/avionics_replay.py (sensor replay of the synthetic sample) and
                                 avionics/integration/cad_mass_integration.py --check (CAD fit, mass properties)
  5. regression tests            python -m unittest discover -s tests
  6. avionics software tests     python -m unittest discover -s avionics/tests -t .   (hardware-free, SIMULATED data)
Writes simulation/results/pipeline_status.json and exits non-zero if any step fails.
Propulsion is never designed here: the motor is external data (simulation/motor_config.json).
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd, label):
    t = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
    return dict(step=label, ok=r.returncode == 0, seconds=round(time.time() - t, 1), tail=tail)


def cad_sources_sha256():
    """Same algorithm as cad/build_cad.py: every .scad source, line-ending independent."""
    cad = os.path.join(ROOT, "cad")
    files = []
    for d, _, fs in os.walk(cad):
        if "exports" in os.path.relpath(d, cad).split(os.sep):
            continue
        files += [os.path.join(d, f) for f in fs if f.endswith(".scad")]
    h = hashlib.sha256()
    for p in sorted(files, key=lambda p: os.path.relpath(p, cad).replace(os.sep, "/")):
        h.update(os.path.relpath(p, cad).replace(os.sep, "/").encode())
        h.update(open(p, "rb").read().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def cad_current():
    vr = json.load(open(os.path.join(ROOT, "cad", "exports", "validation_results.json"), encoding="utf-8"))
    same = vr.get("sources_sha256") == cad_sources_sha256()
    ok = same and vr["summary"]["FAIL"] == 0
    msg = [f"CAD validation {vr['date']}: {vr['summary']}", "CAD sources + parameters unchanged since CAD validation" if same else
           "CAD SOURCES OR PARAMETERS CHANGED since the last CAD validation: run with --with-cad"]
    return dict(step="CAD integration (committed validation is current)", ok=ok, seconds=0.0, tail=msg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--with-cad", action="store_true")
    ap.add_argument("--openscad")
    args = ap.parse_args()
    py = sys.executable
    steps = [run([py, "build.py"], "Engineering package build (build.py)")]
    if args.with_cad:
        cmd = [py, os.path.join("cad", "build_cad.py")] + (["--openscad", args.openscad] if args.openscad else [])
        steps.append(run(cmd, "CAD render + validation (cad/build_cad.py)"))
    steps.append(cad_current())
    steps.append(run([py, os.path.join("simulation", "flight_simulation.py")], "Flight simulation, stability, sensitivity, reports"))
    steps.append(run([py, os.path.join("simulation", "avionics_replay.py")], "Avionics sensor replay (synthetic sample)"))
    steps.append(run([py, os.path.join("avionics", "integration", "cad_mass_integration.py"), "--check"],
                     "Avionics CAD fit and mass-properties check"))
    try:   # preliminary status so the documentation tests can check it; rewritten with the test result below
        write_engineering_status(dict(date=datetime.datetime.now().isoformat(timespec="seconds"), overall="IN PROGRESS", steps=steps))
    except Exception as exc:
        steps.append(dict(step="Engineering status (preliminary)", ok=False, seconds=0.0, tail=[str(exc)]))
    steps.append(run([py, "-m", "unittest", "discover", "-s", "tests"], "Regression tests"))
    steps.append(run([py, "-m", "unittest", "discover", "-s", os.path.join("avionics", "tests"), "-t", "."],
                     "Avionics software tests (hardware-free)"))
    ok = all(s["ok"] for s in steps)
    status = dict(date=datetime.datetime.now().isoformat(timespec="seconds"), overall="PASS" if ok else "FAIL", steps=steps)
    os.makedirs(os.path.join(ROOT, "simulation", "results"), exist_ok=True)
    with open(os.path.join(ROOT, "simulation", "results", "pipeline_status.json"), "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=2)
    try:
        write_engineering_status(status)
        print("  wrote documentation/ENGINEERING_STATUS.md")
    except Exception as exc:                      # status must never mask a pipeline result
        print(f"  [FAIL] ENGINEERING_STATUS.md not written: {exc}")
        ok = False
        status["overall"] = "FAIL"
    print("ASTRA-66 validation pipeline")
    for s in steps:
        print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}  ({s['seconds']} s)")
        for line in s["tail"][-3:]:
            print(f"         {line}")
    print(f"OVERALL: {status['overall']}")
    return 0 if ok else 1


def write_engineering_status(status):
    """documentation/ENGINEERING_STATUS.md, generated from the current result files (never hand-edited)."""
    J = lambda *p: json.load(open(os.path.join(ROOT, *p), encoding="utf-8"))  # noqa: E731
    vr = J("cad", "exports", "validation_results.json")
    fs = J("simulation", "results", "flight_summary.json")
    aj = J("analysis", "results", "analysis.json")
    mc = J("simulation", "motor_config.json")
    sc = J("simulation", "sim_config.json")
    steps = {s["step"]: s for s in status["steps"]}
    ph = mc["status"] == "PLACEHOLDER"
    r, v = fs["results"], fs["vehicle"]
    ver = fs["verification"]
    req = fs["stability_requirements"]
    mass_ok = abs(aj["M0"] - r["mass_liftoff_g"]) < 1e-6 and abs(aj["M0"] - vr["totals"]["rev_b"]["M0"]) < 1e-6
    cp_ok = abs(aj["cp"] - v["cp_mm"]) < 0.05 and abs(aj["cp"] - vr["totals"]["rev_b"]["cp"]) < 0.05
    cad_ok = steps.get("CAD integration (committed validation is current)", {}).get("ok", False)
    sim_ok = steps.get("Flight simulation, stability, sensitivity, reports", {}).get("ok", False) and all(c["ok"] for c in ver)
    tests_ok = steps.get("Regression tests", {}).get("ok", False)
    av_ok = steps.get("Avionics software tests (hardware-free)", {}).get("ok", False)
    replay_ok = steps.get("Avionics sensor replay (synthetic sample)", {}).get("ok", False)
    cadm = steps.get("Avionics CAD fit and mass-properties check", {})
    cadm_line = next((t for t in cadm.get("tail", []) if "PASS" in t), "not run")
    sens_ok = os.path.exists(os.path.join(ROOT, "simulation", "results", "sensitivity_report.md"))
    P = lambda b: "PASS" if b else "FAIL"  # noqa: E731
    ph_note = " (placeholder motor)" if ph else ""
    L = ["# ASTRA-66 — Engineering status\n",
         "> **Draft student engineering design. NOT flight certified.** Propulsion is an external, commercially certified component, "
         "never designed, modified or produced here. Any launch requires review and sign-off by a qualified rocketry mentor or institution "
         "and the range safety officer.\n",
         f"Generated {status['date']} by `python run_validation.py` from the current result files. Pipeline result: **{status['overall']}**. "
         f"Motor data status: **{mc['status']}**.\n",
         "## 1. Status summary\n",
         "| Area | Status | Basis |", "|---|---|---|",
         f"| CAD | {P(cad_ok)} | 25 parametric parts + master assembly; committed validation current (source hash match) |",
         f"| CAD validation | {P(vr['summary']['FAIL'] == 0)} | {vr['summary']['PASS']} PASS · {vr['summary']['WARN']} WARN (accepted) · {vr['summary']['FAIL']} FAIL · 0 interferences; `documentation/CAD_VALIDATION.md` |",
         f"| Simulation | {P(sim_ok)} | {sum(c['ok'] for c in ver)}/{len(ver)} numerical verification checks; trajectory **{'ILLUSTRATIVE ONLY (placeholder propulsion)' if ph else 'model estimate'}** |",
         f"| Stability | {P(cp_ok and all(q['ok'] for q in req))}{ph_note} | CP STA {v['cp_mm']:.2f} mm (CAD cross-check exact); SM liftoff {r['sm_liftoff']:.2f} / rail exit {r['sm_rail_exit']:.2f} / burnout {r['sm_burnout']:.2f} cal vs 1.5–3.0 target |",
         f"| Mass properties | {P(mass_ok)} | liftoff {aj['M0']:.1f} g identical in analysis, CAD validation and simulation; CG STA {aj['cg0']:.1f} mm |",
         f"| Sensitivity analysis | {P(sens_ok and sim_ok)} | 8 non-propulsion parameters; `simulation/results/sensitivity_report.md` |",
         f"| Reproducibility | {P(tests_ok)} | one command, standard library only; regression tests re-derive committed outputs |",
         f"| Documentation | {P(tests_ok)} | file references and disclaimers checked by `tests/test_docs.py` |",
         f"| Avionics software | {P(av_ok)} | sensing, logging, telemetry, ground station, analysis; hardware-free tests on SIMULATED data only; "
         "no component selected; `documentation/AVIONICS_DESIGN.md` |",
         f"| Avionics integration | {P(replay_ok and cadm.get('ok', False))} | sensor replay of the synthetic sample; CAD fit and mass check: "
         f"{cadm_line.split(': ', 1)[-1]} (`documentation/CAD_AVIONICS_INTEGRATION.md`); `documentation/PHASE_5_STATUS.md` |",
         "",
         "## 2. Value classes\n",
         "### VERIFIED FROM CAD (measured on the rendered OpenSCAD meshes)",
         f"- Overall length {vr['dimensions'][0]['cad']} mm; body OD {vr['dimensions'][1]['cad']} mm; nose length 264 mm; fin span tip-to-tip 186 mm; "
         "fin root / tip / sweep 150 / 60 / 70 mm; fin LE at STA 994 mm.",
         "- Bay lengths: payload 114 mm, avionics 158.5 mm, recovery 273.5 mm. Rail buttons at STA 885 / 1115 on the 45° line.",
         "- Part volumes of 21 structural items; closed-manifold geometry; zero interferences; fins removable with the retainer fitted.",
         "### CALCULATED",
         f"- CP STA {v['cp_mm']:.2f} mm (Barrowman, from CAD geometry); CG liftoff STA {aj['cg0']:.1f} mm; static margins; structural masses (volume × density × fill).",
         f"- Simulated trajectory, loads, descent rate {r['descent_rate_mps']:.2f} m/s, sensitivity deltas (1-DOF model).",
         "### ASSUMED",
         "- Material densities and print fill factors; electronics, recovery, paint and adhesive masses.",
         f"- Drag build-up coefficients (roughness {sc['aerodynamics']['surface_roughness_m']} m, protuberances {sc['aerodynamics']['protuberance_fraction']:.0%}); parachute Cd 0.8.",
         "- ISA standard atmosphere, no wind, vertical flight, parachute open at apogee; structural allowables; design load factor.",
         "### PLACEHOLDER",
         ("- **Propulsion:** motor mass/length, thrust curve (`simulation/motors/PLACEHOLDER_TEST_INPUT.eng`, synthetic), retainer mass/OD, MMT bore/length. "
          "**Every trajectory, acceleration, altitude and apogee result depends on these and is NOT representative of any real motor.**") if ph else "- Propulsion: manufacturer data supplied.",
         f"- Camera, battery and switch envelopes; heat-set insert and tee-nut sizes; rail-button, eyebolt and retainer envelopes; rail length {fs['sim_config']['rail_length_m']} m; "
         f"launch site ({sc['launch_site']['status']}: {sc['launch_site']['site_elevation_m']} m, ISA{sc['launch_site']['temp_offset_K']:+.0f} K).",
         "### REQUIRES PHYSICAL MEASUREMENT",
         "- Tube, coupler and MMT diameters (3 stations × 2 axes); mass of every part and module; CG with the actual motor installed (test T-03).",
         "- Printed fit coupons (shoulder, guide slot, inserts); fin alignment; separation force at I-03; recovery static proof load.",
         "- Parachute descent rate (drop test); camera field of view through the Ø14 mm hole; battery endurance on the pad.",
         "",
         "## 3. Unresolved issues (including minor)\n",
         f"1. **Propulsion data are placeholders** (`motor_config.json` status {mc['status']}). Stability margins with the motor and all trajectory values are provisional.",
         f"2. **Rail-exit speed {r['rail_exit_v_mps']:.1f} m/s** on the {fs['sim_config']['rail_length_m']} m planning rail is below the 15 m/s guideline with the placeholder input. "
         "The range's rail and the certified motor must be checked together.",
         "3. **Payload limit:** about 100 g extra in the payload bay pushes the margin above 3.0 cal (over-stable).",
         "4. **No-motor margin:** the 3.23 cal value still includes the placeholder retainer mass and MMT geometry.",
         f"5. **CAD warnings:** {vr['summary']['WARN']} accepted. 11 printed parts need support in the chosen pose; the PL-205 hatch wall is 1.0 mm (0.25 mm nozzle recommended).",
         "6. **Drag model** is an uncalibrated build-up. It needs cross-checking with OpenRocket/RASAero and flight data.",
         "7. **Flight model** is 1-DOF: no wind, weathercocking, angle of attack or drift. Dynamic stability is not assessed.",
         "8. **Structural adequacy** relies on hand calculations with conservative allowables. There is no FEA and no coupon test data yet.",
         "9. **Printability** was judged by a 45° overhang rule only; not yet checked in a slicer.",
         "10. **Tooling:** OpenSCAD is an external tool, not bundled. CAD regeneration needs it (`--with-cad`); the default run checks the committed CAD instead.",
         "11. **Dates:** generated reports carry the run date, so outputs are deterministic except for those date fields.",
         "12. **Avionics:** software architecture and simulation only. No avionics component is selected, built or tested; all avionics "
         "data are SIMULATED; state thresholds are assumptions (`documentation/AVIONICS_DESIGN.md`).",
         "13. **Avionics integration:** the CAD holds PLACEHOLDER electronics envelopes only; fit, wiring, antenna and access items "
         "need physical measurement, and all avionics masses are estimates (`documentation/CAD_AVIONICS_INTEGRATION.md`).",
         "",
         "## 4. Mentor / institution review required before any launch\n",
         "- Selection of a legally obtainable certified motor and its published data. Motor preparation and handling are done by a certified person only.",
         "- Ejection-delay choice from the manufacturer's options, using the simulated coast time.",
         "- Static margin with the real motor and a measured CG. Rail-exit speed against the range's rules.",
         "- Retainer installation, recovery hardware ratings and proof loads, and fin/rail alignment inspection.",
         "- Complete flight-readiness review (package §18) and range safety officer approval on the day.",
         ""]
    L += readiness_sections(steps)
    with open(os.path.join(ROOT, "documentation", "ENGINEERING_STATUS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def readiness_sections(steps):
    """Hardware-integration readiness: what software shows, what needs a bench, what needs qualified review.
    The bench list is taken from the generated CAD/avionics check file, so it cannot drift from the checks."""
    try:
        with open(os.path.join(ROOT, "avionics", "integration", "cad_avionics_checks.json"), encoding="utf-8") as fh:
            checks = json.load(fh)
    except OSError:
        checks = dict(summary={}, checks=[])
    unverified = [c for c in checks["checks"] if c["status"] == "UNVERIFIED"]
    warn = [c for c in checks["checks"] if c["status"] == "WARN"]
    tests = {k: steps.get(k, {}) for k in ("Regression tests", "Avionics software tests (hardware-free)")}
    n_ok = sum(1 for t in tests.values() if t.get("ok"))
    L = ["", "## 5. Hardware-integration readiness (Phase 6)\n",
         "> **NOT FLIGHT CERTIFIED.** Nothing here has flown; no avionics hardware has been selected, built, weighed or "
         "tested; propulsion is an external, commercially certified component represented by PLACEHOLDER data. "
         "Full audit: `documentation/HARDWARE_INTEGRATION_STATUS.md`.\n",
         "### VERIFIED BY SOFTWARE\n",
         f"- Automated test suites passing: {n_ok}/2 (project regression tests and avionics software tests); the "
         "simulation's 13 numerical verification checks; the CAD validation committed with the model.",
         "- Covered: schema validation and rejection of impossible values, timestamp handling (wrap, duplicates, gaps), "
         "state estimation and flight-state classification against synthetic truth, data logging with CRC-16, telemetry "
         "packet encode/decode and corruption rejection, link statistics, sensor replay, and the post-flight analysis.",
         "- Data-source modes SYNTHETIC / BENCH / FLIGHT exist in software (`avionics/firmware/data_source.py`); FLIGHT "
         "is disabled because no flight record exists.",
         "- These results are obtained on synthetic data. They are evidence about the software only, never about "
         "hardware, flight behaviour or safety.\n",
         "### REQUIRES PHYSICAL BENCH VALIDATION\n",
         f"- {len(unverified)} items cannot be checked from the CAD or the analysis and need measurement "
         "(`documentation/CAD_AVIONICS_INTEGRATION.md`):"]
    L += [f"  - {c['check']} ({c['area']})" for c in unverified]
    if warn:
        L.append(f"- {len(warn)} integration warnings to resolve with real parts: "
                 + "; ".join(c["check"] for c in warn) + ".")
    L += ["- Every avionics mass is an estimate: weigh the parts and the assembled vehicle, and measure the CG "
          "(`documentation/MASS_MEASUREMENT_PROCEDURE.md`).",
          "- Sensor behaviour, loop timing, SD write latency, power endurance, radio range and packet loss: bench tests "
          "B-01…B-14 in `documentation/AVIONICS_BENCH_TEST_PLAN.md`, with components chosen using "
          "`documentation/HARDWARE_SELECTION_CHECKLIST.md`.\n",
          "### REQUIRES QUALIFIED ROCKETRY REVIEW\n",
          "- Selection of a legally obtainable certified motor and replacement of the PLACEHOLDER motor data; static "
          "margin and rail-exit speed re-checked with that motor and a measured CG.",
          "- Telemetry radio: band, power and frequency coordination legal where the rocket is flown.",
          "- LiPo battery handling, charging and transport under the range's rules; pad power-up procedure.",
          "- Recovery (the certified motor's own ejection, prepared by a mentor), proof loads and hardware ratings.",
          "- Complete flight-readiness review and range safety officer approval on the day. Until then ASTRA-66 is a "
          "draft student design and is **NOT FLIGHT CERTIFIED**.", ""]
    return L


if __name__ == "__main__":
    sys.exit(main())
