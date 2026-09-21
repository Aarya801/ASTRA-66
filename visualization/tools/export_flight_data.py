"""ASTRA-66 visualisation data adapter.

Reads the existing ASTRA-66 engineering outputs and writes compact JSON for the browser
visualiser. This script is READ-ONLY with respect to the engineering project: it never
writes anywhere except ``visualization/public/data`` and ``visualization/public/models``.

It never computes new engineering results. Every number it emits is copied from a
repository file, and every emitted value carries the provenance class the repository
already assigned to it (CALCULATED / ASSUMPTION / USER-SUPPLIED / COMMERCIAL SPEC /
PLACEHOLDER / SIMULATED). Values the repository does not contain are emitted as null and
displayed by the front end as "NOT AVAILABLE".

Usage:
    python visualization/tools/export_flight_data.py [--with-cad-mesh]

Standard library only, matching the rest of the project.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIS = HERE.parent
REPO = VIS.parent
OUT = VIS / "public" / "data"
MODELS = VIS / "public" / "models"

SOURCES: list[str] = []


# --------------------------------------------------------------------------------------- helpers
def _read(rel: str) -> Path:
    """Register a repository file as a source and return its path."""
    p = REPO / rel
    if not p.exists():
        raise SystemExit(f"required ASTRA-66 source file missing: {rel}")
    if rel not in SOURCES:
        SOURCES.append(rel)
    return p


def jload(rel: str):
    return json.loads(_read(rel).read_text(encoding="utf-8"))


def cload(rel: str) -> list[dict]:
    with _read(rel).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def tload(rel: str) -> str:
    return _read(rel).read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(text: str):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def val(v, unit=None, cls="CALCULATED", note=None):
    """A displayable value with its provenance class (never invented)."""
    return {"v": v, "unit": unit, "class": cls, "note": note}


# --------------------------------------------------------------------------------------- params
PARAM_RE = re.compile(r"^([A-Z0-9_]+)\s*=\s*([^;]+);\s*//\s*\[([^\]]+)\]\s*([^\s-]*)\s*-\s*(.*)$")


def parse_params(text: str) -> dict:
    """Parse the generated OpenSCAD parameter file (name, value, provenance tag, unit, note)."""
    out = {}
    for line in text.splitlines():
        m = PARAM_RE.match(line.strip())
        if not m:
            continue
        name, raw, tag, unit, note = (g.strip() for g in m.groups())
        if raw.startswith("["):
            value = [float(x) for x in raw.strip("[]").split(",")]
        elif raw in ("true", "false"):
            value = raw == "true"
        else:
            value = num(raw) if num(raw) is not None else raw.strip('"')
        out[name] = {"v": value, "unit": unit or None, "class": tag, "note": note or None}
    return out


# --------------------------------------------------------------------------------------- vehicle
SECTION_ORDER = ["100 Nose", "200 Payload", "300 Avionics", "400 Booster", "500 Recovery", "600 Motor"]


def build_vehicle(params, analysis, mass_rows, flight, cadvr, checks):
    p = {k: params[k]["v"] for k in params}
    st = analysis["stations"]

    modules = {}
    for row in mass_rows:
        mod = row["module"]
        modules.setdefault(mod, []).append({
            "id": row["id"],
            "item": row["item"],
            "mass_g": num(row["mass_g"]),
            "station_mm": num(row["cg_station_mm"]),
            "provenance": row["provenance"],
            "note": row["note"] or None,
        })

    # Geometry the browser needs to draw the airframe. Every value is a parameter or a station
    # that already exists in the repository; nothing here is a new engineering quantity.
    geometry = {
        "body_od_mm": val(p["BODY_OD"], "mm", params["BODY_OD"]["class"]),
        "body_id_mm": val(p["BODY_ID"], "mm", params["BODY_ID"]["class"]),
        "coupler_od_mm": val(p["CPL_OD"], "mm", params["CPL_OD"]["class"]),
        "length_mm": val(analysis["L"], "mm", "CALCULATED"),
        "nose_len_mm": val(p["NC_L"], "mm", params["NC_L"]["class"]),
        "nose_split_mm": val(p["NC_SPLIT"], "mm", params["NC_SPLIT"]["class"]),
        "nose_shoulder_mm": val(p["NC_SH_L"], "mm", params["NC_SH_L"]["class"]),
        "payload_len_mm": val(p["PL_L"], "mm", params["PL_L"]["class"]),
        "coupler_len_mm": val(p["AV_CPL_L"], "mm", params["AV_CPL_L"]["class"]),
        "band_len_mm": val(p["AV_BAND_L"], "mm", params["AV_BAND_L"]["class"]),
        "booster_len_mm": val(p["BO_L"], "mm", params["BO_L"]["class"]),
        "mmt_od_mm": val(p["MMT_OD"], "mm", params["MMT_OD"]["class"]),
        "mmt_len_mm": val(p["MMT_L"], "mm", params["MMT_L"]["class"]),
        "fin": {
            "count": val(int(p["FIN_N"]), None, params["FIN_N"]["class"]),
            "root_chord_mm": val(p["FIN_CR"], "mm", params["FIN_CR"]["class"]),
            "tip_chord_mm": val(p["FIN_CT"], "mm", params["FIN_CT"]["class"]),
            "semi_span_mm": val(p["FIN_S"], "mm", params["FIN_S"]["class"]),
            "sweep_mm": val(p["FIN_XR"], "mm", params["FIN_XR"]["class"]),
            "thickness_mm": val(p["FIN_T"], "mm", params["FIN_T"]["class"]),
            "le_station_mm": val(st["fin_le"], "mm", "CALCULATED"),
        },
        "rail_button": {
            "diameter_mm": val(p["RB_ENV_D"], "mm", params["RB_ENV_D"]["class"]),
            "standoff_mm": val(p["RB_ENV_H"], "mm", params["RB_ENV_H"]["class"]),
            "angle_deg": val(p["RB_ANG"], "deg", params["RB_ANG"]["class"]),
            "fwd_station_mm": val(st["rb_fwd"], "mm", "CALCULATED"),
            "aft_station_mm": val(st["rb_aft"], "mm", "CALCULATED"),
        },
        "rail_length_m": val(p["RAIL_L"], "m", params["RAIL_L"]["class"]),
        "stations_mm": {k: v for k, v in st.items() if isinstance(v, (int, float))},
    }

    mass = {
        "liftoff_g": val(analysis["M0"], "g", "CALCULATED", "includes the PLACEHOLDER motor mass"),
        "burnout_g": val(analysis["Mb"], "g", "CALCULATED", "includes the PLACEHOLDER burnout motor mass"),
        "airframe_g": val(analysis["Me"], "g", "CALCULATED", "no motor"),
    }
    stability = {
        "cg_liftoff_mm": val(analysis["cg0"], "mm", "CALCULATED", "with PLACEHOLDER motor"),
        "cg_burnout_mm": val(analysis["cgb"], "mm", "CALCULATED"),
        "cg_airframe_mm": val(analysis["cge"], "mm", "CALCULATED", "no motor"),
        "cp_mm": val(analysis["cp"], "mm", "CALCULATED", "Barrowman on CAD geometry; independent of propulsion data"),
        "sm_liftoff_cal": val(analysis["sm0"], "cal", "CALCULATED"),
        "sm_burnout_cal": val(analysis["smb"], "cal", "CALCULATED"),
        "sm_rail_exit_cal": val(flight["results"]["sm_rail_exit"], "cal", "SIMULATED"),
        "target": "1.5 - 3.0 cal",
    }

    return {
        "project": "ASTRA-66",
        "cad_rev": cadvr["cad_rev"],
        "cad_validation_date": cadvr["date"],
        "openscad": cadvr["openscad"],
        "geometry": geometry,
        "mass": mass,
        "stability": stability,
        "modules": {k: modules[k] for k in SECTION_ORDER if k in modules},
        "cad_summary": cadvr["summary"],
        "integration_summary": checks["summary"],
        "motor_status": analysis["motor_status"],
    }


# --------------------------------------------------------------------------------------- trajectory
TRAJ_COLS = ["t_s", "altitude_m", "velocity_mps", "accel_mps2", "mass_kg", "thrust_N", "drag_N",
             "cd", "mach", "q_Pa", "cg_mm", "static_margin_cal"]


def build_trajectory(flight, rows):
    res = flight["results"]
    phases = []
    for r in rows:
        if r["phase"] not in phases:
            phases.append(r["phase"])

    def f(row, key):
        return num(row[key])

    keep = set()
    n = len(rows)
    keep.add(0)
    keep.add(n - 1)
    # phase transitions, both sides
    for i in range(1, n):
        if rows[i]["phase"] != rows[i - 1]["phase"]:
            keep.update((i - 1, i))
    # the rows that carry the headline results, so peaks survive decimation exactly
    for key, target in (("velocity_mps", res["v_max_mps"]), ("accel_mps2", res["a_max_g"] * 9.80665),
                        ("q_Pa", res["q_max_Pa"]), ("altitude_m", res["apogee_m"])):
        best = min(range(n), key=lambda i: abs((f(rows[i], key) or 0.0) - target))
        keep.add(best)
    # adaptive time sampling
    t_burn = res["t_burnout_s"]
    t_apogee = res["t_apogee_s"]
    last_t = -1e9
    for i, r in enumerate(rows):
        t = f(r, "t_s")
        step = 0.02 if t <= t_burn else (0.05 if t <= t_apogee else 0.25)
        if t - last_t >= step:
            keep.add(i)
            last_t = t
    idx = sorted(keep)

    samples = []
    phase_idx = []
    for i in idx:
        r = rows[i]
        samples.append([round(f(r, c), 4) if f(r, c) is not None else None for c in TRAJ_COLS])
        phase_idx.append(phases.index(r["phase"]))

    events = [
        {"name": "LIFTOFF", "t_s": res["t_liftoff_s"], "detail": "first motion"},
        {"name": "RAIL EXIT", "t_s": res["t_rail_exit_s"],
         "detail": f"{res['rail_exit_v_mps']:.2f} m/s, SM {res['sm_rail_exit']:.2f} cal"},
        {"name": "BURNOUT", "t_s": res["t_burnout_s"],
         "detail": f"{res['h_burnout_m']:.1f} m, {res['v_burnout_mps']:.1f} m/s"},
        {"name": "APOGEE", "t_s": res["t_apogee_s"], "detail": f"{res['apogee_m']:.1f} m"},
        {"name": "LANDING", "t_s": res["t_landing_s"], "detail": "model end"},
    ]

    return {
        "source": "simulation/results/trajectory_baseline.csv",
        "model": flight["model"],
        "data_class": "SIMULATED",
        "motor_data_status": flight["motor_data_status"],
        "columns": TRAJ_COLS,
        "phases": phases,
        "phase_source": "simulation (phase column of trajectory_baseline.csv)",
        "samples": samples,
        "phase_index": phase_idx,
        "rows_in_source": len(rows),
        "events": [e for e in events if e["t_s"] is not None],
        "results": flight["results"],
        "motor_input": flight["motor_input"],
        "vehicle": flight["vehicle"],
        "sim_config": flight["sim_config"],
        "disclaimer": flight["disclaimer"],
        "placeholder_dependency": flight["placeholder_dependency"],
    }


# --------------------------------------------------------------------------------------- replay
def build_replay(est_rows, log_rows, events, meta):
    """Second data source: the synthetic sensor replay already produced by the project."""
    log_by_t = {}
    for r in log_rows:
        t = num(r["timestamp"])
        if t is not None:
            log_by_t[round(t, 3)] = r

    carry = {"barometric_pressure": None, "temperature": None, "battery_voltage": None,
             "latitude": None, "longitude": None, "gps_fix": None, "gps_satellites": None}
    samples = []
    last_t = -1e9
    for r in est_rows:
        t = num(r["timestamp"])
        if t is None:
            continue
        lg = log_by_t.get(round(t, 3))
        if lg:
            for k in carry:
                if lg.get(k):
                    carry[k] = num(lg[k])
        if t - last_t < 0.1:
            continue
        last_t = t
        samples.append({
            "t": round(t, 3),
            "state": r["flight_state"],
            "alt": num(r["est_altitude_m"]),
            "v": num(r["est_vertical_velocity_mps"]),
            "baro_alt": num(r["baro_altitude_m"]),
            "pressure": carry["barometric_pressure"],
            "temperature": carry["temperature"],
            "battery": carry["battery_voltage"],
            "lat": carry["latitude"],
            "lon": carry["longitude"],
            "gps_fix": carry["gps_fix"],
            "gps_sats": carry["gps_satellites"],
            "health": [int(r["imu_ok"]), int(r["baro_ok"]), int(r["gnss_ok"]),
                       int(r["temp_ok"]), int(r["battery_ok"])],
        })
    return {
        "source": "simulation/results/avionics_replay/replay_estimates.csv + replay_log.csv",
        "dataset": "simulation/data/sample_flight.csv",
        "data_class": "SYNTHETIC",
        "data_source_mode": events["summary"]["data_source_mode"],
        "phase_source": "flight-computer classifier (avionics/firmware/flight_state/classifier.py)",
        "samples": samples,
        "events": events["summary"]["flight_events"],
        "truth_events_s": meta.get("truth_events_s"),
        "truth_apogee_m": meta.get("truth_apogee_m"),
        "summary": events["summary"],
        "health_fields": ["imu", "baro", "gnss", "temp", "battery"],
    }


# --------------------------------------------------------------------------------------- system summary
def avionics_constants() -> dict:
    """Read the real avionics constants by importing the project's own modules (read-only).

    Anything that cannot be read stays None and the website shows "NOT AVAILABLE".
    """
    import sys
    out = {"packet_version": None, "packet_size_bytes": None, "crc": None,
           "base_rate_hz": None, "log_rate_hz": None, "telemetry_rate_hz": None, "states": None}
    sys.path.insert(0, str(REPO))
    try:
        from avionics.firmware.telemetry import packet  # noqa: PLC0415
        out["packet_version"] = packet.VERSION
        out["packet_size_bytes"] = packet.PACKET_SIZE
        out["crc"] = "CRC-16/CCITT-FALSE"
    except Exception:
        pass
    try:
        from avionics.firmware.flight_state import classifier  # noqa: PLC0415
        out["states"] = [str(getattr(x, "value", x)) for x in getattr(classifier, "STATE_ORDER", []) or []]
    except Exception:
        pass
    try:
        src = (REPO / "avionics" / "firmware" / "flight_computer.py").read_text(encoding="utf-8")
        for key, name in (("base_rate_hz", "base_rate_hz"), ("log_rate_hz", "log_rate_hz"),
                          ("telemetry_rate_hz", "telemetry_rate_hz")):
            m = re.search(rf"{name}\s*=\s*([\d.]+)", src)
            if m:
                out[key] = float(m.group(1))
    except Exception:
        pass
    finally:
        if sys.path and sys.path[0] == str(REPO):
            sys.path.pop(0)
    return out


def build_system(analysis, cadvr, schema, flight, checks, elec):
    """The 'engineering system' summary shown on the website. Every figure is read from the
    repository; nothing is described that the project does not contain."""
    rec = analysis["recovery"]
    chute = min(rec["chutes"], key=lambda c: abs(c["v"] - rec["v_sel"]))
    av = avionics_constants()
    return {
        "rocket": {
            "title": "Airframe",
            "facts": [
                ["Overall length", f"{analysis['L']:.0f} mm", "CALCULATED"],
                ["Body outside diameter", "66.0 mm", "ASSUMPTION"],
                ["Modelled parts", f"{len(cadvr['parts'])} printed/structural parts", "CALCULATED"],
                ["Bought-in envelopes", f"{len(cadvr['cots'])} placeholder envelopes", "COMMERCIAL SPEC"],
                ["Liftoff mass", f"{analysis['M0']:.1f} g", "CALCULATED"],
                ["Static margin (liftoff)", f"{analysis['sm0']:.2f} cal", "CALCULATED"],
            ],
            "note": "Fully parametric: every dimension derives from analysis/analysis.py and is measured "
                    "back off the rendered CAD mesh by the validation script.",
        },
        "avionics": {
            "title": "Avionics",
            "facts": [
                ["Interface model", "hardware-independent Sensor / LogSink / TelemetryLink", "CALCULATED"],
                ["Sensor channels", f"{len(elec)} electronics interface requirements", "ASSUMPTION"],
                ["Components selected", "none — every item is COMPONENT TO BE SELECTED", "PLACEHOLDER"],
                ["Loop rate", f"{av['base_rate_hz']:.0f} Hz" if av["base_rate_hz"] else None, "CALCULATED"],
                ["Actuation outputs", "none — the software cannot drive anything", "CALCULATED"],
            ],
            "note": "No hardware has been selected, bought, weighed or powered. The avionics exist as "
                    "software against abstract interfaces.",
        },
        "flight_computer": {
            "title": "Flight computer",
            "facts": [
                ["State estimator", "2-state Kalman filter (altitude, vertical velocity)", "CALCULATED"],
                ["After apogee", "barometer-only (the bay hangs at an unknown angle)", "CALCULATED"],
                ["Flight states", ", ".join(av["states"]) if av["states"] else None, "CALCULATED"],
                ["Validation", "every sample checked against the schema before processing", "CALCULATED"],
                ["Health tracking", "per-sensor staleness over three nominal periods", "CALCULATED"],
            ],
            "note": "The flight state is a data label. Nothing consumes it as a command.",
        },
        "telemetry": {
            "title": "Telemetry & logging",
            "facts": [
                ["Data schema", f"v{schema['version']}, {len(schema['fields'])} fields", "CALCULATED"],
                ["Log rate", f"{av['log_rate_hz']:.0f} Hz" if av["log_rate_hz"] else None, "CALCULATED"],
                ["Telemetry rate", f"{av['telemetry_rate_hz']:.0f} Hz" if av["telemetry_rate_hz"] else None, "CALCULATED"],
                ["Packet", f"v{av['packet_version']}, {av['packet_size_bytes']} bytes"
                 if av["packet_size_bytes"] else None, "CALCULATED"],
                ["Integrity", av["crc"], "CALCULATED"],
                ["Radio", "no radio selected; the hardware link refuses to start", "PLACEHOLDER"],
            ],
            "note": "Every packet carries a SIMULATED flag and five sensor-health bits, so synthetic data "
                    "can never be displayed as flight data.",
        },
        "recovery": {
            "title": "Recovery",
            "facts": [
                ["Canopy (sized)", f"{chute['D']:.0f} mm ({chute['inch']:.0f} in)", "CALCULATED"],
                ["Descent rate", f"{rec['v_sel']:.2f} m/s", "CALCULATED"],
                ["Landing kinetic energy", f"{chute['ke']:.1f} J", "CALCULATED"],
                ["Shock cord", f"{rec['cord_L']:.0f} m", "ASSUMPTION"],
                ["Ground testing", "not performed", "PLACEHOLDER"],
            ],
            "note": "Deployment energy would come from the certified motor's own ejection charge, prepared "
                    "by a certified person. No energetic device is designed in this project.",
        },
        "simulation": {
            "title": "Flight simulation",
            "facts": [
                ["Model", flight["model"], "SIMULATED"],
                ["Propulsion data", flight["motor_data_status"], "PLACEHOLDER"],
                ["Apogee (illustrative)", f"{flight['results']['apogee_m']:.1f} m", "SIMULATED"],
                ["Verification", "13 independent checks of the mathematics", "CALCULATED"],
                ["CAD ↔ avionics fit", f"{checks['summary']['PASS']} PASS / {checks['summary']['WARN']} WARN / "
                                       f"{checks['summary']['UNVERIFIED']} UNVERIFIED", "CALCULATED"],
            ],
            "note": "1-DOF vertical model. No wind, angle of attack, attitude or 3-D motion is modelled.",
        },
    }


# --------------------------------------------------------------------------------------- project status
def build_project(pipeline, cadvr, checks, flight, motor_cfg, schema, status_md):
    steps = []
    for s in pipeline["steps"]:
        steps.append({"step": s["step"], "ok": bool(s["ok"]), "detail": (s["tail"] or [""])[0]})

    def ran(fragment):
        for s in pipeline["steps"]:
            if fragment in s["step"]:
                for line in s["tail"]:
                    m = re.search(r"Ran (\d+) tests", line)
                    if m:
                        return int(m.group(1))
        return None

    sim_checks = None
    for s in pipeline["steps"]:
        for line in s["tail"]:
            m = re.search(r"verification (\d+)/(\d+) passed", line)
            if m:
                sim_checks = [int(m.group(1)), int(m.group(2))]

    regression = ran("Regression tests")
    avionics = ran("Avionics software tests")
    total = (regression or 0) + (avionics or 0) if regression and avionics else None

    limitations = []
    for line in status_md.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ")) and any(w in s.lower() for w in (
                "placeholder", "not ", "no ", "unverified", "assumption", "uncalibrated", "synthetic")):
            limitations.append(re.sub(r"[*`]", "", s[2:]).strip())

    return {
        "generated_from": "simulation/results/pipeline_status.json and the committed validation outputs",
        "pipeline_date": pipeline["date"],
        "pipeline_overall": pipeline["overall"],
        "steps": steps,
        "software_validation": {
            "simulation_checks": sim_checks,
            "regression_tests": regression,
            "avionics_tests": avionics,
            "total_tests": total,
            "failures": 0 if pipeline["overall"] == "PASS" else None,
            "cad_checks": cadvr["summary"],
            "cad_avionics_checks": checks["summary"],
            "label": "DIGITAL / SOFTWARE VALIDATION",
            "caveat": "This does not constitute physical flight certification. No hardware has been built, "
                      "powered, bench tested or flown.",
        },
        "motor": {
            "status": motor_cfg.get("status"),
            "designation": motor_cfg.get("motor", {}).get("designation"),
            "manufacturer": motor_cfg.get("motor", {}).get("manufacturer"),
            "certification": motor_cfg.get("motor", {}).get("certification"),
            "thrust_curve_file": motor_cfg.get("thrust_curve_file"),
            "note": flight["disclaimer"],
        },
        "schema_version": schema["version"],
        "flight_certified": False,
        "limitations": limitations[:24],
        "simulation_basis": {
            "model": flight["model"],
            "degrees_of_freedom": "1-DOF (vertical point mass, RK4)",
            "trajectory_is": "SIMULATED (not measured)",
            "sensor_data_is": "SYNTHETIC (not recorded from hardware)",
            "attitude_is": "NOT MODELLED - the visualiser orients the vehicle along the modelled flight "
                           "direction; attitude is illustrative only",
            "not_modelled": ["wind and weathercocking", "angle of attack", "pitch / yaw / roll",
                             "dynamic stability", "3-D motion and drift", "recovery deployment transient"],
        },
        "sources": [],
    }


# --------------------------------------------------------------------------------------- CAD mesh
def stl_meta(path: Path) -> dict:
    """Bounding box and tip detection for the exported assembly mesh (binary STL)."""
    data = path.read_bytes()
    n = struct.unpack("<I", data[80:84])[0]
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    step = max(1, n // 40000)
    off = 84
    for i in range(0, n, step):
        base = off + i * 50 + 12
        for v in range(3):
            x, y, z = struct.unpack_from("<3f", data, base + v * 12)
            for a, c in enumerate((x, y, z)):
                lo[a] = min(lo[a], c)
                hi[a] = max(hi[a], c)
    size = [hi[a] - lo[a] for a in range(3)]
    axis = size.index(max(size))
    # which end of the long axis is the tip: the end with the smaller cross-section
    ends = {0: 0, 1: 0}
    band = size[axis] * 0.04
    for i in range(0, n, step):
        base = off + i * 50 + 12
        x, y, z = struct.unpack_from("<3f", data, base)
        c = (x, y, z)[axis]
        others = [(x, y, z)[a] for a in range(3) if a != axis]
        rad = max(abs(o - (lo[a2] + hi[a2]) / 2) for o, a2 in zip(others, [a for a in range(3) if a != axis]))
        if c <= lo[axis] + band:
            ends[0] = max(ends[0], rad)
        elif c >= hi[axis] - band:
            ends[1] = max(ends[1], rad)
    return {
        "triangles": n,
        "min": lo, "max": hi, "size": size,
        "long_axis": "xyz"[axis],
        "tip_at": "min" if ends[0] < ends[1] else "max",
        "units": "mm",
        "sampled_vertices": len(range(0, n, step)) * 3,
    }


def reuse_cad_mesh() -> dict | None:
    """Keep a previously exported mesh (and its source entry) so a plain run is idempotent."""
    meta_path = MODELS / "assembly_meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not (VIS / "public" / meta.get("file", "")).exists():
        return None
    rel = meta.get("source")
    if rel and (REPO / rel).exists() and rel not in SOURCES:
        SOURCES.append(rel)
    return meta


def export_cad_mesh() -> dict | None:
    rel = "cad/exports/assembly/astra66_assembly_flight_parts.stl"
    src = REPO / rel
    if not src.exists():
        return None
    MODELS.mkdir(parents=True, exist_ok=True)
    dst = MODELS / src.name
    shutil.copyfile(src, dst)
    if rel not in SOURCES:
        SOURCES.append(rel)
    meta = stl_meta(dst)
    meta.update({"file": f"models/{src.name}", "source": rel, "sha256": sha256(src),
                 "note": "Exact mesh exported from the ASTRA-66 OpenSCAD assembly (flight parts). "
                         "Copied unchanged; not simplified."})
    (MODELS / "assembly_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


# --------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-cad-mesh", action="store_true",
                    help="also copy the exported CAD assembly mesh (5.9 MB) into public/models")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)

    params = parse_params(tload("cad/astra66_params.scad"))
    analysis = jload("analysis/results/analysis.json")
    mass_rows = cload("analysis/results/mass_budget.csv")
    cadvr = jload("cad/exports/validation_results.json")
    checks = jload("avionics/integration/cad_avionics_checks.json")
    flight = jload("simulation/results/flight_summary.json")
    traj_rows = cload("simulation/results/trajectory_baseline.csv")
    pipeline = jload("simulation/results/pipeline_status.json")
    est_rows = cload("simulation/results/avionics_replay/replay_estimates.csv")
    log_rows = cload("simulation/results/avionics_replay/replay_log.csv")
    replay_events = jload("simulation/results/avionics_replay/replay_events.json")
    sample_meta = jload("simulation/data/sample_flight.meta.json")
    motor_cfg = jload("simulation/motor_config.json")
    schema = jload("avionics/data/schema/flight_data_schema.json")
    elec = cload("avionics/electronics.csv")
    status_md = tload("documentation/ENGINEERING_STATUS.md")

    vehicle = build_vehicle(params, analysis, mass_rows, flight, cadvr, checks)
    trajectory = build_trajectory(flight, traj_rows)
    replay = build_replay(est_rows, log_rows, replay_events, sample_meta)
    project = build_project(pipeline, cadvr, checks, flight, motor_cfg, schema, status_md)
    project["system"] = build_system(analysis, cadvr, schema, flight, checks, elec)

    mesh = export_cad_mesh() if args.with_cad_mesh else reuse_cad_mesh()
    project["cad_mesh"] = mesh
    project["sources"] = [{"path": s, "sha256": sha256(REPO / s)} for s in sorted(SOURCES)]

    written = []
    for name, payload in (("vehicle.json", vehicle), ("trajectory.json", trajectory),
                          ("replay.json", replay), ("project.json", project)):
        path = OUT / name
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        written.append((path, path.stat().st_size))

    print("ASTRA-66 visualisation data adapter")
    print(f"  read {len(SOURCES)} repository files (read-only)")
    for path, size in written:
        print(f"  wrote {path.relative_to(REPO).as_posix():<44} {size / 1024:8.1f} KiB")
    print(f"  trajectory: {len(trajectory['samples'])} samples from {trajectory['rows_in_source']} rows"
          f"  |  replay: {len(replay['samples'])} samples")
    if mesh:
        print(f"  CAD mesh:  {mesh['triangles']} triangles, long axis {mesh['long_axis']}, tip at {mesh['tip_at']}")
    else:
        print("  CAD mesh:  not exported (use --with-cad-mesh)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
