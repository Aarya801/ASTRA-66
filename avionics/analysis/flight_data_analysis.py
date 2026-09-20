"""Post-flight analysis of an ASTRA-66 flight-data log (CSV, schema avionics/data/schema/flight_data_schema.json).

    python avionics/analysis/flight_data_analysis.py avionics/data/example/example_flight_simulated.csv
    python avionics/analysis/flight_data_analysis.py LOG.csv --out some/dir

Reads the log tolerantly (corrupted, malformed and out-of-order rows are dropped and reported), then writes to the
output folder (default avionics/analysis/results/<log name>/):
  altitude_vs_time.svg, velocity_vs_time.svg, acceleration_vs_time.svg, temperature_vs_time.svg,
  battery_voltage_vs_time.svg, gps_track.svg (only if GNSS fixes exist), flight_summary.json, flight_report.md

Derived quantities (velocity from differentiated barometric altitude, descent rate, distances) are CALCULATED from
the log. The derived velocity is smoothed (two 0.3 s moving averages), so it underestimates sharp peaks such as the
velocity at burnout by a few m/s; the logged onboard estimate is reported next to it. Every output carries the log's
data-source mode (SYNTHETIC / BENCH / FLIGHT): synthetic and bench data are never presented as flight data.
"""
import argparse
import importlib.util
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from avionics.firmware.data_source import FLIGHT, is_real_sensor_data, label, normalise  # noqa: E402
from avionics.firmware.flight_state.classifier import ClassifierConfig, classify_series  # noqa: E402
from avionics.firmware.logging.reader import read_flight_log  # noqa: E402

G0 = 9.80665
EARTH_R = 6_371_000.0
STATE_NAMES = ["PRELAUNCH", "ASCENT", "COAST", "DESCENT", "LANDED"]
MAX_PLOT_POINTS = 1500


def _load_plotting():
    """Reuse the project's dependency-free SVG plotter (simulation/plotting.py) without importing the simulation."""
    spec = importlib.util.spec_from_file_location("astra66_plotting", os.path.join(ROOT, "simulation", "plotting.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------------------------------------- numerics
def series(records, name):
    """(times, values) for rows where `name` has a value."""
    t, v = [], []
    for r in records:
        if r.get(name) is not None:
            t.append(r["timestamp"])
            v.append(r[name])
    return t, v


def moving_average(t, y, window_s):
    """Centred moving average over +/- window_s/2 (handles uneven sampling). O(n) with two pointers."""
    out, lo, hi, acc, n = [], 0, 0, 0.0, len(y)
    for i in range(n):
        while hi < n and t[hi] <= t[i] + window_s / 2:
            acc += y[hi]
            hi += 1
        while t[lo] < t[i] - window_s / 2:
            acc -= y[lo]
            lo += 1
        out.append(acc / (hi - lo))
    return out


def derivative(t, y):
    """Central differences (one-sided at the ends)."""
    n = len(y)
    if n < 2:
        return [0.0] * n
    d = []
    for i in range(n):
        a, b = max(i - 1, 0), min(i + 1, n - 1)
        d.append((y[b] - y[a]) / (t[b] - t[a]) if t[b] > t[a] else 0.0)
    return d


def velocity_from_altitude(t, h, window_s=0.3):
    """Vertical velocity (m/s): smoothed barometric altitude, then central differences, then smoothed again."""
    if len(h) < 3:
        return [0.0] * len(h)
    return moving_average(t, derivative(t, moving_average(t, h, window_s)), window_s)


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def local_en(lat, lon, lat0, lon0):
    """East / north offsets (m) from (lat0, lon0), equirectangular approximation (fine over a few km)."""
    return (math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0)), math.radians(lat - lat0) * EARTH_R)


def _stats(v):
    return None if not v else dict(min=min(v), max=max(v), mean=sum(v) / len(v), start=v[0], end=v[-1])


def _median(v):
    s = sorted(v)
    return None if not s else (s[len(s) // 2] if len(s) % 2 else 0.5 * (s[len(s) // 2 - 1] + s[len(s) // 2]))


def _decimate(x, y, n=MAX_PLOT_POINTS):
    if len(x) <= n:
        return list(x), list(y)
    k = math.ceil(len(x) / n)
    return x[::k] + ([x[-1]] if (len(x) - 1) % k else []), y[::k] + ([y[-1]] if (len(y) - 1) % k else [])


# ----------------------------------------------------------------------------------------------------- analysis
def state_transitions(records):
    """First time each flight state appears in the log's flight_state column: {state: time}."""
    out = {}
    for r in records:
        s = r.get("flight_state")
        if s and s not in out:
            out[s] = r["timestamp"]
    return out


def analyse(records, report=None):
    if not records:
        raise ValueError("no usable rows in the log")
    th, h = series(records, "altitude")
    ta, az = series(records, "imu_accel_z")
    src = sorted({r["data_source"] for r in records})
    modes = sorted({normalise(v) for v in src})
    s = dict(data_source=src, data_source_modes=modes, simulated=not all(is_real_sensor_data(v) for v in src),
             rows=len(records),
             time_span_s=[records[0]["timestamp"], records[-1]["timestamp"]])
    if report is not None:
        s["data_quality"] = report.as_dict()
    # --- flight states: logged, or reconstructed offline when the column is empty
    trans = state_transitions(records)
    if len(trans) <= 1 and th:
        vz = velocity_from_altitude(th, h)
        acc_at = dict(zip(ta, az))
        _, events = classify_series(th, [acc_at.get(t) for t in th], moving_average(th, h, 0.3), vz)
        names = dict(LIFTOFF="ASCENT", BURNOUT="COAST", APOGEE="DESCENT", LANDING="LANDED")
        trans = {"PRELAUNCH": records[0]["timestamp"], **{names[e.name]: e.time_s for e in events if e.name in names}}
        s["flight_states_source"] = "reconstructed offline (flight_state column empty)"
    else:
        s["flight_states_source"] = "logged flight_state column"
    s["state_transitions_s"] = {k: round(v, 3) for k, v in trans.items()}
    # A state label appears only after its condition has held for the classifier's confirmation time, so the events
    # themselves happened earlier: liftoff/burnout by the confirm time, landing by the stationary window.
    c = ClassifierConfig()
    lag = dict(ASCENT=c.launch_confirm_s, COAST=c.burnout_confirm_s, DESCENT=0.0, LANDED=c.landed_window_s)
    t_lo, t_bo, t_ap, t_ld = (trans[k] - lag[k] if k in trans else None for k in ("ASCENT", "COAST", "DESCENT", "LANDED"))
    # --- altitude and velocity
    if th:
        hs = moving_average(th, h, 0.3)
        i = max(range(len(hs)), key=hs.__getitem__)
        v = velocity_from_altitude(th, h)
        j = max(range(len(v)), key=v.__getitem__)
        s["apogee"] = dict(altitude_m=round(hs[i], 2), time_s=round(th[i], 3), raw_max_altitude_m=round(max(h), 2),
                           basis="barometric altitude above pad, 0.3 s moving average")
        s["max_vertical_velocity"] = dict(mps=round(v[j], 2), time_s=round(th[j], 3),
                                          basis="derivative of smoothed barometric altitude")
        if t_ap is not None:
            lo = t_ap + 2.0
            hi = (t_ld - 1.0) if t_ld is not None else float("inf")
            d = [-vv for tt, vv in zip(th, v) if lo <= tt <= hi]
            s["descent_rate_mps"] = None if not d else round(_median(d), 2)
    tv, vv = series(records, "vertical_velocity")
    if vv:
        k = max(range(len(vv)), key=vv.__getitem__)
        s["onboard_max_vertical_velocity"] = dict(mps=round(vv[k], 2), time_s=round(tv[k], 3), basis="logged estimator output")
    # --- acceleration
    if az:
        k = max(range(len(az)), key=az.__getitem__)
        s["max_axial_specific_force"] = dict(mps2=round(az[k], 2), g=round(az[k] / G0, 2), time_s=round(ta[k], 3))
    mags = [(r["timestamp"], math.sqrt(r["imu_accel_x"] ** 2 + r["imu_accel_y"] ** 2 + r["imu_accel_z"] ** 2))
            for r in records if all(r.get(n) is not None for n in ("imu_accel_x", "imu_accel_y", "imu_accel_z"))]
    if mags:
        tm, m = max(mags, key=lambda p: p[1])
        s["max_acceleration_magnitude"] = dict(mps2=round(m, 2), g=round(m / G0, 2), time_s=round(tm, 3))
    # --- timing
    if th and t_ap is not None:
        t_ap = s["apogee"]["time_s"]
    s["event_times_s"] = {k: None if v is None else round(v, 3) for k, v in
                          dict(liftoff=t_lo, burnout=t_bo, apogee=t_ap, landing=t_ld).items()}
    s["event_times_basis"] = ("state label time minus the classifier's confirmation time (liftoff, burnout, landing); "
                              "apogee = time of maximum smoothed barometric altitude")
    if t_lo is not None:
        s["timing_s"] = {k: (round(b - a, 3) if a is not None and b is not None else None) for k, (a, b) in dict(
            burn_duration=(t_lo, t_bo), time_to_apogee=(t_lo, t_ap),
            flight_duration=(t_lo, t_ld), descent_duration=(t_ap, t_ld)).items()}
    # --- environment and power
    s["temperature_c"] = _round(_stats(series(records, "temperature")[1]))
    b = _stats(series(records, "battery_voltage")[1])
    if b:
        b["drop"] = b["start"] - b["min"]
    s["battery_voltage_v"] = _round(b, 3)
    # --- GNSS
    fixes = [(r["timestamp"], r["latitude"], r["longitude"]) for r in records
             if r.get("latitude") is not None and r.get("longitude") is not None and (r.get("gps_fix") or 0) >= 2]
    if fixes:
        _, la0, lo0 = fixes[0]
        dists = [haversine_m(la0, lo0, la, lo) for _, la, lo in fixes]
        track = sum(haversine_m(a[1], a[2], b[1], b[2]) for a, b in zip(fixes, fixes[1:]))
        s["gnss"] = dict(fixes=len(fixes), first_fix=dict(time_s=fixes[0][0], lat=la0, lon=lo0),
                         last_fix=dict(time_s=fixes[-1][0], lat=fixes[-1][1], lon=fixes[-1][2]),
                         last_fix_distance_from_first_m=round(dists[-1], 1), max_distance_from_first_m=round(max(dists), 1),
                         track_length_m=round(track, 1))
    else:
        s["gnss"] = None
    return s


def _round(d, n=2):
    return None if d is None else {k: round(v, n) for k, v in d.items()}


# ----------------------------------------------------------------------------------------------------- outputs
def make_plots(records, summary, out_dir):
    P = _load_plotting()
    tag = " · ".join(label(m) for m in summary["data_source_modes"])
    ev = summary["event_times_s"]          # burnout is unlabelled: it sits too close to liftoff for a readable label
    vl = [(ev[k], lab) for k, lab in (("liftoff", "liftoff"), ("burnout", ""), ("apogee", "apogee"), ("landing", "landing"))
          if ev.get(k) is not None]
    files = []

    def plot(name, series_, ylabel, title, **kw):
        ser = [dict(label=lab, x=_decimate(x, y)[0], y=_decimate(x, y)[1], dash=dash) for lab, x, y, dash in series_ if x]
        if not ser:
            return
        path = os.path.join(out_dir, name)
        P.line_plot(path, ser, "Time since logger start (s)", ylabel, title, subtitle=tag, vlines=vl, **kw)
        files.append(name)

    th, h = series(records, "altitude")
    apo = summary.get("apogee")
    plot("altitude_vs_time.svg", [("barometric altitude", th, h, False)], "Altitude above pad (m)", "Altitude vs time",
         points=[(apo["time_s"], apo["altitude_m"], f"apogee {apo['altitude_m']:.1f} m")] if apo else ())
    tv, vv = series(records, "vertical_velocity")
    plot("velocity_vs_time.svg", [("from barometric altitude (derived)", th, velocity_from_altitude(th, h), False),
                                  ("onboard estimate (logged)", tv, vv, True)],
         "Vertical velocity (m/s)", "Vertical velocity vs time")
    ta, az = series(records, "imu_accel_z")
    mag = [(r["timestamp"], math.sqrt(r["imu_accel_x"] ** 2 + r["imu_accel_y"] ** 2 + r["imu_accel_z"] ** 2))
           for r in records if all(r.get(n) is not None for n in ("imu_accel_x", "imu_accel_y", "imu_accel_z"))]
    plot("acceleration_vs_time.svg", [("axial specific force (z)", ta, az, False),
                                      ("magnitude", [p[0] for p in mag], [p[1] for p in mag], True)],
         "Accelerometer reading (m/s²)", "Acceleration vs time")
    tt, temp = series(records, "temperature")
    plot("temperature_vs_time.svg", [("bay temperature", tt, temp, False)], "Temperature (°C)", "Temperature vs time")
    tb, bat = series(records, "battery_voltage")
    plot("battery_voltage_vs_time.svg", [("battery voltage", tb, bat, False)], "Battery voltage (V)", "Battery voltage vs time")
    g = summary.get("gnss")
    if g:
        la0, lo0 = g["first_fix"]["lat"], g["first_fix"]["lon"]
        en = [local_en(r["latitude"], r["longitude"], la0, lo0) for r in records
              if r.get("latitude") is not None and r.get("longitude") is not None and (r.get("gps_fix") or 0) >= 2]
        e, n = [p[0] for p in en], [p[1] for p in en]
        path = os.path.join(out_dir, "gps_track.svg")
        P.line_plot(path, [dict(label="GNSS track", x=e, y=n, markers=len(e) <= 200)], "East of first fix (m)",
                    "North of first fix (m)", "GPS ground track", subtitle=tag,
                    points=[(e[0], n[0], "first fix"), (e[-1], n[-1], "last fix")])
        files.append("gps_track.svg")
    return files


def write_report(summary, files, out_dir, log_name):
    J = lambda v, u="": "n/a" if v is None else f"{v}{u}"  # noqa: E731
    s = summary
    L = [f"# Post-flight analysis: `{log_name}`\n"]
    for m in s["data_source_modes"]:
        if m == FLIGHT:
            L.append("> **FLIGHT DATA.** Review with a qualified mentor before drawing any conclusion.\n")
        elif m == "BENCH":
            L.append("> **BENCH DATA: recorded from real hardware on the bench, not flight data.** The vehicle was not "
                     "flying; the values show sensor and software behaviour on the bench only.\n")
        else:
            L.append("> **SYNTHETIC DATA: not flight data.** Computer-generated; where the truth trajectory is the "
                     "project simulation it uses the PLACEHOLDER propulsion input. The values show that the software "
                     "works, not how a real flight would behave.\n")
    q = s.get("data_quality", {})
    L += ["## Data quality\n", f"- Rows read: {q.get('rows_total', s['rows'])}; usable: {s['rows']}; dropped: {q.get('dropped', {})}",
          f"- Row CRC verified: {q.get('crc_checked', 'n/a')}; timestamp gaps: {q.get('timestamp_gaps', 'n/a')}",
          f"- Rejected values by field: {q.get('value_issues') or 'none'}", f"- Flight states: {s['flight_states_source']}\n",
          "## Key results (CALCULATED from the log)\n", "| Quantity | Value | Time (s) |", "|---|---|---|"]
    a, v = s.get("apogee", {}), s.get("max_vertical_velocity", {})
    L.append(f"| Apogee (barometric, above pad) | {J(a.get('altitude_m'), ' m')} | {J(a.get('time_s'))} |")
    L.append(f"| Max vertical velocity (derived) | {J(v.get('mps'), ' m/s')} | {J(v.get('time_s'))} |")
    ov = s.get("onboard_max_vertical_velocity", {})
    L.append(f"| Max vertical velocity (onboard estimate) | {J(ov.get('mps'), ' m/s')} | {J(ov.get('time_s'))} |")
    f = s.get("max_axial_specific_force", {})
    L.append(f"| Max axial specific force | {J(f.get('mps2'), ' m/s²')} ({J(f.get('g'), ' g')}) | {J(f.get('time_s'))} |")
    L.append(f"| Mean descent rate (median) | {J(s.get('descent_rate_mps'), ' m/s')} | |")
    for k, val in (s.get("timing_s") or {}).items():
        L.append(f"| {k.replace('_', ' ').capitalize()} | {J(val, ' s')} | |")
    t, b = s.get("temperature_c") or {}, s.get("battery_voltage_v") or {}
    L.append(f"| Temperature min / max | {J(t.get('min'))} / {J(t.get('max'))} °C | |")
    L.append(f"| Battery start / min / drop | {J(b.get('start'))} / {J(b.get('min'))} / {J(b.get('drop'))} V | |")
    g = s.get("gnss")
    if g:
        L.append(f"| GNSS: last fix from first fix | {g['last_fix_distance_from_first_m']} m ({g['fixes']} fixes) | {g['last_fix']['time_s']} |")
    L += ["", "## Events\n", f"Estimated event times ({s['event_times_basis']}):\n", "| Event | Time (s) |", "|---|---|"]
    L += [f"| {k} | {J(val)} |" for k, val in s["event_times_s"].items()]
    L += ["", "State labels as logged (first time each state appears):\n", "| State | Time (s) |", "|---|---|"]
    L += [f"| {k} | {val} |" for k, val in s["state_transitions_s"].items()]
    L += ["", "## Plots\n"] + [f"- [{p}]({p})" for p in files]
    with open(os.path.join(out_dir, "flight_report.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


def run(log_path, out_dir=None):
    records, report = read_flight_log(log_path)
    summary = analyse(records, report)
    stem = os.path.splitext(os.path.basename(log_path))[0]
    out_dir = out_dir or os.path.join(ROOT, "avionics", "analysis", "results", stem)
    os.makedirs(out_dir, exist_ok=True)
    files = make_plots(records, summary, out_dir)
    summary["log_file"] = os.path.basename(log_path)
    summary["outputs"] = files + ["flight_summary.json", "flight_report.md"]
    with open(os.path.join(out_dir, "flight_summary.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    write_report(summary, files, out_dir, os.path.basename(log_path))
    return summary, out_dir


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", help="flight-data CSV log")
    ap.add_argument("--out", help="output folder (default avionics/analysis/results/<log name>)")
    a = ap.parse_args(argv)
    s, out = run(a.log, a.out)
    print(f"{'/'.join(s['data_source_modes'])} data: {s['rows']} rows; "
          f"apogee {s.get('apogee', {}).get('altitude_m')} m; outputs in {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
