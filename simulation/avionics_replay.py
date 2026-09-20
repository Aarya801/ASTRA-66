"""Sensor replay: feed recorded or synthetic sensor data through the ASTRA-66 avionics processing pipeline.

    python simulation/avionics_replay.py                          # replay simulation/data/sample_flight.csv
    python simulation/avionics_replay.py DATA.csv --out some/dir  # replay any sensor-level CSV
    python simulation/avionics_replay.py --make-sample            # regenerate the deterministic sample dataset

Input: a sensor-level CSV (format in avionics/DATA_FORMAT.md §3): one row per tick on a uniform time grid, one column
per sensor field, empty cell = no sample from that sensor at that tick. Each sensor group is wrapped in a `ReplaySensor`
(the Phase 4 `Sensor` interface), so the data run through exactly the same flight-computer code as simulated sensors:
validation -> estimator -> state classifier -> sensor health -> logger -> telemetry packets -> ground-station receiver.

Outputs (default simulation/results/avionics_replay/):
  replay_estimates.csv   estimated altitude, vertical velocity, flight state and sensor validity per tick
  replay_telemetry.csv   telemetry frames as decoded by the ground-station receiver
  replay_log.csv         flight-data log in the Phase 4 schema format (CRC per row)
  replay_events.json     event timeline (flight events, sensor health changes, invalid samples) and summary

SOFTWARE TEST DATA ONLY. The sample dataset is synthetic; nothing here is flight data or a performance prediction.
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from avionics.firmware.data_source import ACCEPTED, SYNTHETIC, check_available, is_real_sensor_data, label  # noqa: E402
from avionics.firmware.flight_computer import HEALTH_FLAGS, FlightComputer  # noqa: E402
from avionics.firmware.logging.logger import CsvLogSink, DataLogger, MemorySink  # noqa: E402
from avionics.firmware.logging.schema import load_schema  # noqa: E402
from avionics.firmware.logging.timebase import TimestampMonitor  # noqa: E402
from avionics.firmware.sensor_interfaces.base import Sensor  # noqa: E402
from avionics.firmware.sensor_interfaces.simulated import (SimulatedBarometer, SimulatedBatteryMonitor,  # noqa: E402
                                                           SimulatedGNSS, SimulatedIMU, SimulatedSeparationSense,
                                                           SimulatedTemperature, SyntheticFlightProfile)
from avionics.firmware.telemetry.link import SimulatedTelemetryLink  # noqa: E402
from avionics.ground_station.receiver import GroundStationReceiver  # noqa: E402

SAMPLE = os.path.join(ROOT, "simulation", "data", "sample_flight.csv")
BENCH_EXAMPLE = os.path.join(ROOT, "avionics", "bench_data", "example_bench_record.csv")
SAMPLE_META = os.path.join(ROOT, "simulation", "data", "sample_flight.meta.json")
DEFAULT_OUT = os.path.join(ROOT, "simulation", "results", "avionics_replay")
SENSOR_FIELDS = {
    "imu": ("imu_accel_x", "imu_accel_y", "imu_accel_z", "gyro_x", "gyro_y", "gyro_z"),
    "baro": ("barometric_pressure",),
    "gnss": ("latitude", "longitude", "gps_altitude", "gps_fix", "gps_satellites"),
    "temperature": ("temperature",),
    "battery": ("battery_voltage",),
    "separation": ("separation_detected",),
}
INPUT_COLUMNS = ["timestamp", "data_source"] + [f for fs in SENSOR_FIELDS.values() for f in fs]
ESTIMATE_COLUMNS = ["timestamp", "flight_state", "est_altitude_m", "est_vertical_velocity_mps", "baro_altitude_m",
                    "imu_ok", "baro_ok", "gnss_ok", "temp_ok", "battery_ok", "gps_fix"]


# ------------------------------------------------------------------------------------------------------- input
class SensorData:
    """A loaded sensor-level CSV: rows indexed by tick on a uniform grid."""

    def __init__(self, path, allow_flight=False):
        self.path = path
        self.allow_flight = allow_flight
        with open(path, encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
        for req in ("timestamp", "data_source"):
            if req not in header:
                raise ValueError(f"{path}: missing required column '{req}'")
        self.unknown_columns = [c for c in header if c not in INPUT_COLUMNS]
        self.sensors = [s for s, fs in SENSOR_FIELDS.items() if any(f in header for f in fs)]
        sources = {r["data_source"] for r in rows}
        if len(sources) != 1 or not sources <= set(ACCEPTED):
            raise ValueError(f"{path}: data_source must be identical in every row and one of {', '.join(ACCEPTED)}")
        self.data_source = sources.pop()
        self.mode = check_available(self.data_source, allow_flight)   # FLIGHT stays disabled until real data exist
        self.skipped = dict(bad_timestamp=0, duplicate=0, non_monotonic=0, off_grid=0)
        good = []
        for r in rows:
            try:
                t = float(r["timestamp"])
            except (TypeError, ValueError):
                self.skipped["bad_timestamp"] += 1
                continue
            good.append((t, r))
        dts = sorted(b[0] - a[0] for a, b in zip(good, good[1:]) if b[0] > a[0])
        if not dts:
            raise ValueError(f"{path}: fewer than two usable rows")
        self.period_s = round(dts[len(dts) // 2], 6)
        mon = TimestampMonitor(self.period_s)
        self.rows = {}
        for t, r in good:
            ok, issue = mon.check(t)
            if not ok:
                self.skipped[issue] += 1
                continue
            k = int(round(t / self.period_s))
            if abs(t - k * self.period_s) > self.period_s / 4:
                self.skipped["off_grid"] += 1
                continue
            self.rows[k] = r
        self.last_tick = max(self.rows)
        dur = self.last_tick * self.period_s
        self.rates_hz = {}
        for s in self.sensors:
            n = sum(1 for r in self.rows.values() if any((r.get(f) or "").strip() for f in SENSOR_FIELDS[s]))
            self.rates_hz[s] = max(round(n / dur), 1) if dur > 0 else 1


class ReplaySensor(Sensor):
    """Phase 4 `Sensor` interface backed by recorded rows. Returns the recorded values unchanged (as text); the flight
    computer validates them exactly as it validates a live sensor."""

    def __init__(self, name, data):
        super().__init__(name, 1.0 / data.period_s)
        self.fields, self.data = SENSOR_FIELDS[name], data
        self.simulated = not is_real_sensor_data(data.data_source)

    def _read(self, t_us):
        row = self.data.rows.get(int(round(t_us / 1e6 / self.data.period_s)))
        if row is None:
            return None
        vals = {f: row[f] for f in self.fields if (row.get(f) or "").strip()}
        return vals or None


# ------------------------------------------------------------------------------------------------------- replay
def replay(path=SAMPLE, out_dir=None, telemetry_rate_hz=5.0, loss_prob=0.0, bit_error_prob=0.0, seed=0,
           allow_flight=False):
    """Replay a sensor-level CSV (SYNTHETIC, BENCH or - once it exists - FLIGHT data). Returns a dict with estimates,
    telemetry frames, events and a summary; writes the output files when out_dir is given."""
    data = SensorData(path, allow_flight=allow_flight)
    sensors = [ReplaySensor(s, data) for s in data.sensors]
    base_hz = 1.0 / data.period_s
    paths = {}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        paths = {k: os.path.join(out_dir, f"replay_{k}") for k in
                 ("estimates.csv", "telemetry.csv", "log.csv", "events.json")}
    logger = DataLogger(CsvLogSink(paths["log.csv"]) if out_dir else MemorySink(), data.data_source, data.period_s,
                        allow_flight=allow_flight)
    link = SimulatedTelemetryLink(loss_prob, bit_error_prob, seed=seed + 21)
    fc = FlightComputer(sensors, logger=logger, telemetry_link=link, base_rate_hz=base_hz, log_rate_hz=base_hz,
                        telemetry_rate_hz=telemetry_rate_hz, nominal_rates_hz=data.rates_hz)
    estimates, timeline = [], []
    prev_health = {f: False for f in HEALTH_FLAGS.values()}
    prev_invalid, prev_fix, n_events = {}, None, 0
    for _ in range(data.last_tick + 1):
        t = fc.time_s
        state = fc.step()
        h = fc.health(t)
        for flag, ok in h.items():
            if ok != prev_health[flag]:
                timeline.append(dict(time_s=round(t, 3), event=f"{flag[:-3].upper()}_{'OK' if ok else 'STALE'}",
                                     kind="sensor_health"))
        prev_health = h
        for sensor, n in fc.invalid_samples.items():
            if n != prev_invalid.get(sensor, 0):
                timeline.append(dict(time_s=round(t, 3), event=f"{sensor.upper()}_INVALID_SAMPLE", kind="validation"))
        prev_invalid = dict(fc.invalid_samples)
        fix = fc.latest.get("gps_fix")
        if fix is not None and (prev_fix is None or (fix >= 2) != (prev_fix >= 2)):
            timeline.append(dict(time_s=round(t, 3), event="GNSS_FIX" if fix >= 2 else "GNSS_NO_FIX", kind="gnss"))
            prev_fix = fix
        for e in fc.clf.events[n_events:]:
            timeline.append(dict(time_s=round(e.time_s, 3), event=e.name, kind="flight_state",
                                 **{k: round(v, 3) if isinstance(v, float) else v for k, v in e.detail.items()}))
        n_events = len(fc.clf.events)
        ready = fc.est.kf.initialised
        estimates.append(dict(timestamp=t, flight_state=state.value,
                              est_altitude_m=fc.est.altitude if ready else None,
                              est_vertical_velocity_mps=fc.est.vertical_velocity if ready else None,
                              baro_altitude_m=fc._tick_values.get("altitude"), gps_fix=fix, **h))
    log_summary = logger.close()
    packets = link.receive()
    rx = GroundStationReceiver()
    for t, p in packets:
        rx.ingest(p, t)
    timeline.sort(key=lambda e: (e["time_s"], e["kind"] != "flight_state"))
    alts = [(e["est_altitude_m"], e["timestamp"]) for e in estimates if e["est_altitude_m"] is not None]
    summary = dict(
        notice="SOFTWARE TEST DATA ONLY: replay of a sensor-level dataset through the avionics software. Not flight data.",
        input=os.path.relpath(path, ROOT).replace(os.sep, "/"), data_source=data.data_source,
        data_source_mode=data.mode, data_source_label=label(data.data_source),
        rows_used=len(data.rows), rows_skipped=data.skipped, unknown_columns=data.unknown_columns,
        base_rate_hz=round(base_hz, 3), sensor_rates_hz=data.rates_hz,
        flight_events={e.name: round(e.time_s, 3) for e in fc.clf.events},
        max_estimated_altitude=None if not alts else dict(altitude_m=round(max(alts)[0], 2), time_s=round(max(alts)[1], 3)),
        invalid_samples=dict(sorted(fc.invalid_samples.items())), logger_counts=log_summary["counts"],
        logger_issue_counts=log_summary["issue_counts"],
        telemetry=dict(link="SIMULATED TELEMETRY", sent=link.sent, **rx.stats()))
    result = dict(estimates=estimates, frames=[f for _, f in rx.frames], timeline=timeline, summary=summary,
                  receiver=rx, packets=packets, paths=paths)
    if out_dir:
        _write_estimates(paths["estimates.csv"], estimates)
        rx.write_csv(paths["telemetry.csv"])
        with open(paths["events.json"], "w", encoding="utf-8", newline="\n") as fh:
            json.dump(dict(summary=summary, timeline=timeline), fh, indent=2)
            fh.write("\n")
    return result


def _fmt(v, nd):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    s = f"{v:.{nd}f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def _write_estimates(path, rows):
    nd = dict(timestamp=3, est_altitude_m=2, est_vertical_velocity_mps=2, baro_altitude_m=2)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(ESTIMATE_COLUMNS) + "\n")
        for r in rows:
            fh.write(",".join(r[c] if c == "flight_state" else _fmt(r[c], nd.get(c, 0)) for c in ESTIMATE_COLUMNS) + "\n")


# ------------------------------------------------------------------------------------------------------- sample data
def make_sample(path=SAMPLE, meta_path=SAMPLE_META, faults_on=True, duration_s=None, title=None, profile=None):
    """Write the deterministic synthetic sample dataset (50 Hz grid) with documented, scripted sensor faults."""
    p = profile or SyntheticFlightProfile()
    rate = 50.0
    sensors = [SimulatedIMU(p, seed=111, rate_hz=rate), SimulatedBarometer(p, seed=112, rate_hz=rate),
               SimulatedGNSS(p, seed=113), SimulatedTemperature(p, seed=114), SimulatedBatteryMonitor(p, seed=115),
               SimulatedSeparationSense(p, seed=116, rate_hz=rate)]
    L = p.t_liftoff
    faults = [
        dict(time_s=2.0, sensor="imu", field="imu_accel_z", value="nan", purpose="non-finite value on the pad"),
        dict(window_s=[L + 1.0, L + 4.0], sensor="gnss", purpose="GNSS messages lost during boost and coast (loss of lock)"),
        dict(time_s=round(L + 6.0, 2), sensor="baro", field="barometric_pressure", value="250000.0",
             purpose="physically impossible pressure (above the 120 000 Pa plausibility limit)"),
        dict(window_s=[20.0, 25.0], sensor="temperature", purpose="temperature sensor silent (stale)"),
        dict(time_s=30.0, sensor="battery", field="battery_voltage", value="9.900",
             purpose="impossible 1S battery voltage (above the 5.5 V plausibility limit)"),
    ]
    if not faults_on:
        faults = []
    schema = load_schema()
    n = int(round((p.duration if duration_s is None else duration_s) * rate))
    rows = []
    for k in range(n + 1):
        t_us = int(round(k * 1e6 / rate))
        t = t_us / 1e6
        row = dict(timestamp=f"{t:.3f}", data_source=SYNTHETIC)
        for s in sensors:
            if s.due(t_us):
                smp = s.sample(t_us)
                if smp is not None:
                    row.update({f: schema.format_value(f, v) for f, v in smp.values.items()})
        for f in faults:
            if "window_s" in f and f["window_s"][0] <= t < f["window_s"][1]:
                for field in SENSOR_FIELDS[f["sensor"]]:
                    row.pop(field, None)
            elif "time_s" in f and abs(t - f["time_s"]) < 1e-9:
                row[f["field"]] = f["value"]
        rows.append(row)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(INPUT_COLUMNS) + "\n")
        for r in rows:
            fh.write(",".join(r.get(c, "") for c in INPUT_COLUMNS) + "\n")
    meta = dict(
        title=title or "ASTRA-66 sample_flight.csv: SYNTHETIC SOFTWARE TEST DATASET, NOT FLIGHT DATA",
        generator="python simulation/avionics_replay.py --make-sample",
        truth_profile=p.label + " (boost / coast / 5 m/s descent; numbers chosen for software testing only)",
        truth_events_s=dict(liftoff=round(p.t_liftoff, 3), burnout=round(p.t_liftoff + 1.5, 3),
                            apogee=round(p.t_apogee, 3), landing=round(p.t_landing, 3)),
        truth_apogee_m=round(max(p.h), 2),
        grid_hz=rate, sensor_rates_hz=dict(imu=50, baro=50, separation=50, gnss=1, temperature=1, battery=1),
        seeds=dict(imu=111, baro=112, gnss=113, temperature=114, battery=115, separation=116),
        scripted_faults=faults,
        notes=["Sensor values come from the Phase 4 simulated sensors (seeded noise). Noise, drift, discharge and "
               "parachute swing are illustrative assumptions, not properties of any component.",
               "GNSS positions are relative to a fictitious origin (0 deg, 0 deg) with synthetic drift."])
    with open(meta_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    return len(rows)


def _write_json(path, doc):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def make_bench_example(path=BENCH_EXAMPLE):
    """Write the bench-record column template: the same sensor-level format, 10 s of synthetic pad data, no faults.
    It is labelled SYNTHETIC because the values are generated; a real recording is labelled BENCH."""
    meta = os.path.splitext(path)[0] + ".meta.json"
    n = make_sample(path, meta, faults_on=False, duration_s=10.0,
                    title="ASTRA-66 example_bench_record.csv: COLUMN TEMPLATE with SYNTHETIC values, NOT a measurement",
                    profile=SyntheticFlightProfile(pad_time_s=120.0))   # stationary the whole time: a bench, not a flight
    with open(meta, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["purpose"] = ("Column template for bench records (avionics/bench_data/README.md). The values are synthetic "
                      "(generated by the simulated sensors), so data_source is SYNTHETIC. A genuine bench recording "
                      "must set data_source to BENCH in every row and come with its own meta file.")
    doc["scripted_faults"] = []
    _write_json(meta, doc)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", default=SAMPLE, help="sensor-level CSV (default: the sample dataset)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--make-sample", action="store_true", help="regenerate simulation/data/sample_flight.csv first")
    ap.add_argument("--make-bench-example", action="store_true",
                    help="regenerate the bench-record column template avionics/bench_data/example_bench_record.csv")
    ap.add_argument("--loss", type=float, default=0.0, help="simulated telemetry packet-loss probability")
    ap.add_argument("--bit-errors", type=float, default=0.0, help="simulated corrupted-packet probability")
    ap.add_argument("--allow-flight", action="store_true",
                    help="allow a dataset labelled FLIGHT (disabled: no real flight record exists)")
    a = ap.parse_args(argv)
    if a.make_sample:
        print(f"wrote {os.path.relpath(SAMPLE, ROOT)} ({make_sample()} rows) + meta")
    if a.make_bench_example:
        print(f"wrote {os.path.relpath(BENCH_EXAMPLE, ROOT)} ({make_bench_example()} rows) + meta")
    r = replay(a.data, a.out, loss_prob=a.loss, bit_error_prob=a.bit_errors, allow_flight=a.allow_flight)
    s = r["summary"]
    print(f"{s['data_source_mode']} sensor replay of {s['input']}: {s['rows_used']} rows; events {s['flight_events']}; "
          f"invalid samples {s['invalid_samples']}; telemetry {s['telemetry']['decoded']} packets")
    print(s["data_source_label"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
