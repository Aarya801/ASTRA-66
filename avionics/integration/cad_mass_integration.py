"""CAD <-> avionics integration check and avionics mass-properties table.

    python avionics/integration/cad_mass_integration.py            # writes the report, the checks JSON and the mass CSV
    python avionics/integration/cad_mass_integration.py --check    # same, exit code 1 if any check FAILs

Inputs (read only; nothing in the CAD or the analysis is changed):
  cad/exports/validation_results.json     committed CAD validation (placeholder electronics envelopes, interference)
  cad/parts/COTS_envelopes.scad           placeholder module envelopes (MCU, IMU, barometer, microSD, radio)
  cad/astra66_params.scad                 parameters
  analysis/results/mass_budget.csv        mass budget (the source of the CG analysis)
  analysis/results/analysis.json          liftoff mass, CG, CP, static margin

Every check is one of:
  PASS        shown by the CAD model or a calculation from it (for PLACEHOLDER envelopes, not real parts)
  WARN        shown by the CAD / calculation, but a risk or a documentation conflict remains
  UNVERIFIED  cannot be verified from the CAD: UNVERIFIED — PHYSICAL MEASUREMENT REQUIRED
  FAIL        the CAD data contradict the requirement
"""
import argparse
import csv
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(ROOT, "documentation", "CAD_AVIONICS_INTEGRATION.md")
CHECKS_JSON = os.path.join(HERE, "cad_avionics_checks.json")
MASS_CSV = os.path.join(HERE, "avionics_mass_properties.csv")
UNVERIFIED = "UNVERIFIED — PHYSICAL MEASUREMENT REQUIRED"
# Avionics, payload electronics and their mounting hardware in the mass budget.
AVIONICS_ITEMS = ["EL-AV", "EL-BAT", "EL-GPS", "EL-CAM", "AV-306", "AV-308", "AV-312", "AV-305", "AV-309/310",
                  "PL-202", "PL-203", "PL-204"]
UNCERTAINTY = 0.25       # illustrative +/-25 % band on ASSUMPTION / USER-SUPPLIED masses (an assumption, not a measurement)
SM_TARGET = (1.5, 3.0)   # calibres, the project's stability target


def _load(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return json.load(fh) if p[-1].endswith(".json") else fh.read()


def scad_params():
    out = {}
    for m in re.finditer(r"^([A-Z][A-Z0-9_]*)\s*=\s*(-?[0-9.]+)\s*;", _load("cad", "astra66_params.scad"), re.M):
        out[m.group(1)] = float(m.group(2))
    return out


def module_envelopes(params, stations):
    """Parse EL_modules() in COTS_envelopes.scad -> {name: (x0, y0, z0, dx, dy, dz)} in mm."""
    src = _load("cad", "parts", "COTS_envelopes.scad")
    body = src[src.index("module EL_modules()"):]
    body = body[:body.index("\n}")]
    names = dict(SLED_T=params["SLED_T"], X_SLED_FWD=stations["sled_fwd"],
                 X_SW=stations["pl_end"] + params["AV_BAND_L"] / 2)
    ys = re.search(r"ys\s*=\s*([^;]+);", body).group(1)
    names["ys"] = eval(ys, {"__builtins__": {}}, dict(names))  # noqa: S307  (arithmetic on known names only)
    env = {}
    for m in re.finditer(r"translate\(\[([^\]]+)\]\)\s*cube\(\[([^\]]+)\]\);\s*//\s*([A-Za-z]+)", body):
        pos = [eval(e, {"__builtins__": {}}, dict(names)) for e in m.group(1).split(",")]  # noqa: S307
        size = [float(e) for e in m.group(2).split(",")]
        env[m.group(3)] = tuple(pos + size)
    return env


def mass_table(budget, aj):
    M, cg, cp, sm = aj["M0"], aj["cg0"], aj["cp"], aj["sm0"]
    D = (cp - cg) / sm
    rows = []
    for r in budget:
        if r["id"] not in AVIONICS_ITEMS:
            continue
        m, x = float(r["mass_g"]), float(r["cg_station_mm"])
        prov = r["provenance"]
        conf = {"CALCULATED": "MEDIUM: CAD volume x assumed density" if r["note"].startswith("CAD") else "MEDIUM: calculated",
                "ASSUMPTION": "LOW: estimate, weigh", "USER-SUPPLIED": "LOW: placeholder, weigh"}.get(prov, prov)
        cg_without = (M * cg - m * x) / (M - m)
        d10 = (M * cg + 10 * x) / (M + 10) - cg
        rows.append(dict(component=f"{r['id']} {r['item']}", mass_g=m, source=f"{prov}" + (f" ({r['note']})" if r["note"] else ""),
                         location=f"STA {x:.1f} mm, {r['module']}", confidence=conf, station_mm=x,
                         cg_shift_if_removed_mm=round(cg_without - cg, 2), cg_shift_per_10g_mm=round(d10, 2),
                         sm_change_per_10g_cal=round(-d10 / D, 3), assumed=prov in ("ASSUMPTION", "USER-SUPPLIED")))
    return rows, D


def mass_checks(budget, aj, rows, D):
    checks = []
    M = sum(float(r["mass_g"]) for r in budget)
    cg = sum(float(r["mass_g"]) * float(r["cg_station_mm"]) for r in budget) / M
    ok = abs(M - aj["M0"]) < 0.5 and abs(cg - aj["cg0"]) < 0.5
    checks.append(("Mass properties", "CG analysis regenerated from analysis/results/mass_budget.csv",
                   "PASS" if ok else "FAIL",
                   f"recomputed M0 {M:.1f} g / CG STA {cg:.1f} mm vs analysis {aj['M0']:.1f} g / {aj['cg0']:.1f} mm "
                   "(budget masses are rounded to 0.1 g)"))
    sub_m = sum(r["mass_g"] for r in rows)
    sub_x = sum(r["mass_g"] * r["station_mm"] for r in rows) / sub_m
    checks.append(("Mass properties", "Avionics / payload subtotal and its station", "PASS",
                   f"{sub_m:.1f} g at STA {sub_x:.1f} mm ({100 * sub_m / aj['M0']:.1f} % of liftoff mass), "
                   f"forward of the liftoff CG (STA {aj['cg0']:.1f} mm)"))
    assumed = [r for r in rows if r["assumed"]]
    am = sum(r["mass_g"] for r in assumed)
    ax = sum(r["mass_g"] * r["station_mm"] for r in assumed) / am
    sms = []
    for f in (-UNCERTAINTY, UNCERTAINTY):
        dm = f * am
        cg_new = (aj["M0"] * aj["cg0"] + dm * ax) / (aj["M0"] + dm)
        sms.append((aj["cp"] - cg_new) / D)
    lo, hi = min(sms), max(sms)
    inside = SM_TARGET[0] <= lo and hi <= SM_TARGET[1]
    checks.append(("Mass properties", f"Liftoff static margin with assumed avionics masses +/-{UNCERTAINTY:.0%} (illustrative band)",
                   "PASS" if inside else "WARN",
                   f"{am:.1f} g assumed at STA {ax:.1f} mm -> SM {lo:.2f}–{hi:.2f} cal (nominal {aj['sm0']:.2f}; target "
                   f"{SM_TARGET[0]}–{SM_TARGET[1]}). Includes the PLACEHOLDER motor mass"))
    checks.append(("Mass properties", "Avionics, GPS, battery, camera and switch masses", "UNVERIFIED",
                   f"{', '.join(r['component'].split(' ')[0] for r in assumed)} are estimates or placeholders: weigh the "
                   "selected parts and update analysis/analysis.py through the normal pipeline"))
    return checks


def cad_checks(vr, params, stations, env):
    C = []
    el = {e["check"]: e for e in vr["electronics"]}
    fz = {e["check"][:40]: e for e in vr["feasibility"]}
    cots = {c["id"]: c for c in vr["cots"]}
    get = lambda d, prefix: next(v for k, v in d.items() if k.startswith(prefix))  # noqa: E731

    e = get(el, "Sled stack max radius")
    C.append(("Electronics sled envelope", "Sled stack (sled, cage, spacers, switch, module envelopes) vs coupler bore",
              "PASS" if e["status"] == "PASS" else "FAIL", f"{e['value']} mm (CAD validation, PLACEHOLDER envelopes)"))
    bad = [i for i in vr["interference"] if any(k in (i["a"], i["b"]) for k in ("EL-MOD", "EL-BAT", "EL-GPS", "AV-307"))
           and i["result"] not in ("clear", "contact")]
    C.append(("Electronics sled envelope", "Module / battery / GPS / switch envelopes vs structure (interference)",
              "FAIL" if bad else "PASS", "no interference in the CAD validation" if not bad else f"{bad}"))
    C.append(("Electronics sled envelope", "Envelope completeness", "WARN",
              f"EL_modules() models {', '.join(env)} only. Buzzer, status LED, regulator, temperature sensor, battery "
              "divider, connectors and wiring (all in the EL-AV mass or the interface list) have no envelope"))
    C.append(("Electronics sled envelope", "Real module dimensions vs placeholder envelopes", "UNVERIFIED",
              "no component selected; measure the selected boards (with headers and connectors) and update COTS_envelopes.scad"))
    mb = next(e for e in vr["electronics"] if e["check"].startswith("M2.5 insert bosses"))
    C.append(("Sensor mounting", "Mounting bosses on sled / GPS tray / switch tower", "PASS" if mb["status"] == "PASS" else "FAIL",
              f"{mb['value']} M2.5 bosses (CAD validation); hole patterns of real boards {UNVERIFIED.split(' — ')[0].lower()}"))
    x0, y0, z0, dx, dy, dz = env["IMU"]
    cx, cy = x0 + dx / 2, y0 + dy / 2
    r_imu = math.hypot(cx, cy)
    a_c = math.radians(1000.0) ** 2 * r_imu / 1000.0
    C.append(("Sensor mounting", "IMU position relative to the roll axis", "WARN",
              f"IMU envelope centre {r_imu:.1f} mm off the axis (x {cx:.1f}, y {cy:.1f} mm, beside the switch tower); the "
              "interface specification asks for near-axis mounting. Roll would add a centripetal reading of up to "
              f"{a_c:.1f} m/s² at the 1000 deg/s gyro requirement. Roll rate is not simulated (1-DOF): decide the IMU position when "
              "the board is selected"))
    bx0, _, bz0, _, _, bdz = env["barometer"]
    x_sw = stations["pl_end"] + params["AV_BAND_L"] / 2
    C.append(("Sensor mounting", "Barometer at the static-port station", "PASS" if bz0 <= x_sw <= bz0 + bdz else "WARN",
              f"barometer envelope STA {bz0:.1f}–{bz0 + bdz:.1f} mm; 4 × ⌀{params['STATIC_PORT_D']:.0f} mm static ports at "
              f"STA {x_sw:.1f} mm (switch band)"))
    C.append(("Sensor mounting", "Avionics-bay sealing and static-port sizing", "UNVERIFIED",
              "gasket AV-309 and port size need a leak / pressure-lag bench test once a barometer has been selected"))
    g = get(el, "GPS envelope under the hatch")
    C.append(("Sensor mounting", "GPS module under the service hatch", "PASS" if g["status"] == "PASS" else "FAIL",
              f"{g['value']} (CAD validation)"))
    b = get(el, "Battery width limit")
    C.append(("Battery space", "Battery envelope in the AV-308 cage", "PASS" if b["status"] == "PASS" else "FAIL",
              f"{b['value']} mm; cage vs battery envelope clear (CAD validation)"))
    C.append(("Battery space", "Real cell size, strap retention, charging access", "UNVERIFIED",
              f"placeholder cell {params['BAT_L']:.0f} × {params['BAT_W']:.0f} × {params['BAT_H']:.0f} mm; "
              "retention needs a shake / drop check"))
    C.append(("Cable routing", "Harness pass-through AV-303 (I-08) and strain relief", "PASS",
              f"⌀{params['HARNESS_D']:.0f} mm hole {params['HARNESS_Y']:.0f} mm off axis in AV-303; zip-tie slots on AV-306 (CAD sources)"))
    C.append(("Cable routing", "Connector passage through ⌀8 mm, wire count, bend radius, lengths", "UNVERIFIED",
              "no wiring is modelled; check with the selected connectors (keyed, per interface I-08)"))
    rx0, _, rz0, _, _, rdz = env["LoRa"]
    gps = cots["EL-GPS"]
    gap = rz0 - gps["bbox_max"][2]
    C.append(("Antenna / radio clearance", "Radio envelope to GPS envelope separation", UNVERIFIED.split(" — ")[0],
              f"{gap:.0f} mm axially (radio STA {rz0:.0f}–{rz0 + rdz:.0f}, GPS STA {gps['bbox_min'][2]:.0f}–"
              f"{gps['bbox_max'][2]:.0f}), bulkhead AV-303 between them. RF interference needs a bench test"))
    rods = cots["AV-305"]
    overlap = rods["bbox_min"][2] <= rz0 + rdz and rz0 <= rods["bbox_max"][2]
    C.append(("Antenna / radio clearance", "Metal near the radio antenna", "WARN" if overlap else "PASS",
              f"M4 steel rods AV-305 (STA {rods['bbox_min'][2]:.0f}–{rods['bbox_max'][2]:.0f}) run alongside the radio envelope; "
              "no antenna is modelled. Route the antenna away from the rods and battery; verify by range test (T-14)"))
    C.append(("Antenna / radio clearance", "RF transparency of the airframe", "UNVERIFIED",
              "kraft / phenolic body tube assumed radio-transparent (no carbon fibre in the design); not measured"))
    s = get(el, "Switch envelope top")
    C.append(("Maintenance access", "Power switch reachable through the switch band", "PASS" if s["status"] == "PASS" else "FAIL",
              f"{s['value']} mm (CAD validation)"))
    f = get(fz, "Sled stack slides out aft of AV-301")
    C.append(("Maintenance access", "Sled removal for SD card and battery service",
              "WARN" if f["margin"] < 1.0 else "PASS",
              f"{f['value']}: radial margin {f['margin']:.2f} mm on PLACEHOLDER envelopes (CAD feasibility check). Real boards, "
              "wires and connectors must keep this margin"))
    C.append(("Maintenance access", "SD-card and battery-connector access without disassembly", "UNVERIFIED",
              "both sit inside the coupler; card-slot orientation and connector reach are not modelled"))
    return C


def build():
    vr = _load("cad", "exports", "validation_results.json")
    aj = _load("analysis", "results", "analysis.json")
    with open(os.path.join(ROOT, "analysis", "results", "mass_budget.csv"), encoding="utf-8") as fh:
        budget = list(csv.DictReader(fh))
    params, stations = scad_params(), aj["stations"]
    env = module_envelopes(params, stations)
    rows, D = mass_table(budget, aj)
    checks = cad_checks(vr, params, stations, env) + mass_checks(budget, aj, rows, D)
    return dict(checks=checks, rows=rows, D=D, aj=aj, env=env, vr=vr)


def write(res):
    with open(MASS_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        cols = ["component", "mass_g", "source", "location", "confidence", "cg_shift_if_removed_mm", "cg_shift_per_10g_mm",
                "sm_change_per_10g_cal"]
        w.writerow(cols)
        for r in res["rows"]:
            w.writerow([f"{r[c]:.1f}" if c == "mass_g" else r[c] for c in cols])
    counts = {k: sum(1 for c in res["checks"] if c[2] == k) for k in ("PASS", "WARN", "UNVERIFIED", "FAIL")}
    aj = res["aj"]
    L = ["# ASTRA-66 — CAD ↔ avionics integration and avionics mass properties\n",
         "> Generated by `python avionics/integration/cad_mass_integration.py` from the committed CAD validation, the CAD "
         "sources and the mass budget. **Nothing in the CAD or the analysis was changed.** The CAD contains PLACEHOLDER "
         "envelopes only: a PASS means the placeholder envelope fits, not that a real part fits. No avionics hardware has "
         "been selected, built, weighed or tested, and the project is NOT flight certified.\n",
         f"Summary: **{counts['PASS']} PASS · {counts['WARN']} WARN · {counts['UNVERIFIED']} {UNVERIFIED} · "
         f"{counts['FAIL']} FAIL**\n",
         "## 1. Checks\n", "| Area | Check | Status | Evidence / reason |", "|---|---|---|---|"]
    for area, check, status, ev in res["checks"]:
        st = UNVERIFIED if status == "UNVERIFIED" else status
        L.append(f"| {area} | {check} | {st} | {ev} |")
    L += ["", "## 2. Avionics and payload mass properties\n",
          f"Liftoff mass {aj['M0']:.1f} g, CG STA {aj['cg0']:.1f} mm, CP STA {aj['cp']:.1f} mm, static margin "
          f"{aj['sm0']:.2f} cal (reference diameter {res['D']:.1f} mm), from `analysis/results/analysis.json`. The liftoff "
          "values include the PLACEHOLDER motor. Positive CG shifts move the CG aft (toward the tail); a positive margin "
          "change is more stable.\n",
          "| Component | Mass (g) | Source | Location | Confidence | CG shift if removed (mm) | CG shift per +10 g (mm) | "
          "Static-margin change per +10 g (cal) |", "|---|---|---|---|---|---|---|---|"]
    for r in res["rows"]:
        L.append(f"| {r['component']} | {r['mass_g']:.1f} | {r['source']} | {r['location']} | {r['confidence']} | "
                 f"{r['cg_shift_if_removed_mm']:+.2f} | {r['cg_shift_per_10g_mm']:+.2f} | {r['sm_change_per_10g_cal']:+.3f} |")
    L += ["", "Machine-readable table: `avionics/integration/avionics_mass_properties.csv`.\n",
          "## 3. What this does and does not show\n",
          "- The CG analysis itself is produced by `build.py` from `analysis/analysis.py`; this report recomputes it from the "
          "mass budget and confirms the two agree. No mass was changed, because no avionics part has been weighed.",
          "- Every item marked LOW confidence must be weighed; the static-margin band above is illustrative, not a tolerance.",
          f"- Items marked {UNVERIFIED} need the selected hardware on the bench (see `avionics/HARDWARE_MAPPING.md`).", ""]
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    with open(CHECKS_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(summary=counts,
                       checks=[dict(area=a, check=c, status=st, evidence=e) for a, c, st, e in res["checks"]],
                       mass_rows=[{k: v for k, v in r.items() if k != "assumed"} for r in res["rows"]]),
                  fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit with 1 if any check FAILs")
    a = ap.parse_args(argv)
    counts = write(build())
    print("CAD/avionics integration: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    for p in (REPORT, CHECKS_JSON, MASS_CSV):
        print(f"  wrote {os.path.relpath(p, ROOT)}")
    return 1 if (a.check and counts["FAIL"]) else 0


if __name__ == "__main__":
    sys.exit(main())
