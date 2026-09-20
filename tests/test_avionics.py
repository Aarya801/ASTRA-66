"""Phase 5 avionics integration tests (synthetic data only; no hardware).

These tests check that the avionics SOFTWARE behaves as specified on synthetic data. They do not show that any
sensor, radio, parachute, motor or the vehicle works, and they are no evidence of flight readiness. ASTRA-66 is NOT
flight certified.
"""
import csv
import importlib.util
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from avionics.firmware.crc import crc16  # noqa: E402
from avionics.firmware import data_source as DS  # noqa: E402
from avionics.firmware.flight_computer import FlightComputer  # noqa: E402
from avionics.firmware.flight_state.estimator import VerticalKalmanFilter, VerticalStateEstimator, pressure_to_altitude  # noqa: E402
from avionics.firmware.logging.reader import read_flight_log  # noqa: E402
from avionics.firmware.logging.schema import load_schema  # noqa: E402
from avionics.firmware.sensor_interfaces.base import Sensor  # noqa: E402
from avionics.firmware.sensor_interfaces.simulated import isa_pressure  # noqa: E402
from avionics.firmware.telemetry import packet as P  # noqa: E402
from avionics.ground_station.receiver import GroundStationReceiver  # noqa: E402
from avionics.analysis import flight_data_analysis as A  # noqa: E402
from avionics.integration import cad_mass_integration as CMI  # noqa: E402


def _load_replay():
    spec = importlib.util.spec_from_file_location("astra66_avionics_replay_test", ROOT / "simulation" / "avionics_replay.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _load_replay()
META = json.loads((ROOT / "simulation" / "data" / "sample_flight.meta.json").read_text(encoding="utf-8"))
COMMITTED = ROOT / "simulation" / "results" / "avionics_replay"
NEWLINE = chr(10)


def _read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def frame(**kw):
    base = dict(seq=7, time_s=12.34, simulated=True, flight_state="COAST", altitude_m=100.0, vertical_velocity_mps=12.5,
                temperature_c=20.0, battery_voltage_v=4.05, gps_fix=3, gps_satellites=8, latitude_deg=0.001,
                longitude_deg=0.002, imu_ok=True, baro_ok=True, gnss_ok=False, temp_ok=True, battery_ok=False)
    base.update(kw)
    return P.TelemetryFrame(**base)


class _Replayed:
    """One replay of the sample dataset, shared by the tests (read-only)."""
    result = None

    @classmethod
    def get(cls):
        if cls.result is None:
            cls.result = R.replay(R.SAMPLE)
        return cls.result


# ------------------------------------------------------------------------------------------------ packets and CRC
class PacketsAndChecksums(unittest.TestCase):
    def test_encode_decode_v2_with_health(self):
        d = P.decode(P.encode(frame()))
        self.assertEqual(len(P.encode(frame())), 41)
        self.assertEqual((d.seq, d.flight_state, d.simulated), (7, "COAST", True))
        self.assertEqual((d.imu_ok, d.baro_ok, d.gnss_ok, d.temp_ok, d.battery_ok), (True, True, False, True, False))
        self.assertAlmostEqual(d.altitude_m, 100.0)
        self.assertAlmostEqual(d.vertical_velocity_mps, 12.5)

    def test_v1_packets_still_decode_without_health(self):
        raw = bytearray(P.encode(frame()))
        raw[2] = 1                                            # version 1
        body = bytes(raw[:P.BODY_SIZE])
        v1 = body + struct.pack("<H", crc16(body))
        d = P.decode(v1)
        self.assertIsNone(d.imu_ok)
        self.assertIsNone(d.battery_ok)
        raw[2] = 3
        body = bytes(raw[:P.BODY_SIZE])
        with self.assertRaises(P.PacketError):
            P.decode(body + struct.pack("<H", crc16(body)))

    def test_crc_check_value_and_every_single_bit_error_is_rejected(self):
        self.assertEqual(crc16(b"123456789"), 0x29B1)
        good = P.encode(frame())
        for i in range(len(good) * 8):
            bad = bytearray(good)
            bad[i // 8] ^= 1 << (i % 8)
            with self.assertRaises(P.PacketError, msg=f"bit {i}"):
                P.decode(bytes(bad))

    def test_truncated_and_padded_packets_rejected(self):
        good = P.encode(frame())
        for bad in (good[:-1], good + b"\x00", b""):
            with self.assertRaises(P.PacketError):
                P.decode(bad)

    def test_sequence_handling_loss_duplicates_wrap_and_latest_time(self):
        rx = GroundStationReceiver()
        for s in (65533, 65534, 65534, 0, 3):                 # duplicate 65534; 65535, 1 and 2 missing (wrap aware)
            rx.ingest(P.encode(frame(seq=s, time_s=float(s % 100))), rx_time_s=float(s % 100))
        st = rx.stats()
        self.assertEqual((st["decoded"], st["duplicates"], st["lost"]), (4, 1, 3))
        self.assertAlmostEqual(st["packet_loss_percent"], 100 * 3 / 7, places=1)
        self.assertEqual(st["last_packet_time_s"], 3.0)


# ------------------------------------------------------------------------------------------------ sensor validity
class _Scripted(Sensor):
    """Test sensor returning scripted values: {tick: dict} (missing tick = no sample)."""

    simulated = True

    def __init__(self, name, rate_hz, script):
        super().__init__(name, rate_hz)
        self.script = script

    def _read(self, t_us):
        return self.script.get(int(round(t_us / self.period_us)))


class SensorValidity(unittest.TestCase):
    def test_health_goes_stale_after_three_periods_and_recovers(self):
        baro = {k: dict(barometric_pressure=101325.0) for k in range(100) if not 40 <= k < 60}
        fc = FlightComputer([_Scripted("baro", 50, baro)], base_rate_hz=50, log_rate_hz=50, telemetry_rate_hz=5)
        seen = []
        for _ in range(100):
            t = fc.time_s
            fc.step()
            seen.append((round(t, 2), fc.health(t)["baro_ok"]))
        ok = dict(seen)
        self.assertTrue(ok[0.78])                               # last sample at 0.78 s
        self.assertTrue(ok[0.84])                               # within 3 periods (0.06 s)
        self.assertFalse(ok[0.86])                              # stale
        self.assertTrue(ok[1.2])                                # recovered at the next sample
        self.assertFalse(fc.health(0.0)["imu_ok"])              # a sensor that does not exist is never OK

    def test_impossible_values_never_reach_the_estimator(self):
        script = {k: dict(barometric_pressure=101325.0) for k in range(60)}
        script[30] = dict(barometric_pressure=250000.0)         # above the plausibility limit
        script[31] = dict(barometric_pressure="garbage")
        script[32] = dict(barometric_pressure=float("nan"))
        fc = FlightComputer([_Scripted("baro", 50, script)], base_rate_hz=50, log_rate_hz=50, telemetry_rate_hz=5)
        for _ in range(60):
            fc.step()
            self.assertLess(abs(fc.est.altitude), 0.5)
        self.assertEqual(fc.invalid_samples["baro"], 3)

    def test_missing_gps_is_handled(self):
        tmp = tempfile.mkdtemp(prefix="astra66_nogps_")
        try:
            rows = _read_csv(R.SAMPLE)
            cols = [c for c in rows[0] if c not in R.SENSOR_FIELDS["gnss"]]
            p = os.path.join(tmp, "nogps.csv")
            with open(p, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, cols, extrasaction="ignore", lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
            r = R.replay(p)
            self.assertNotIn("gnss", r["summary"]["sensor_rates_hz"])
            self.assertTrue(all(e["gnss_ok"] is False and e["gps_fix"] is None for e in r["estimates"]))
            self.assertTrue(all(f.latitude_deg is None and f.gnss_ok is False for f in r["frames"]))
            self.assertEqual(list(r["summary"]["flight_events"]), ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ estimation
class Estimation(unittest.TestCase):
    def test_barometric_altitude_conversion(self):
        for h in (0.0, 50.0, 135.5, 328.0, 1500.0):
            self.assertAlmostEqual(pressure_to_altitude(isa_pressure(h), isa_pressure(0.0)), h, delta=0.05)
        # Relative to a pad above sea level the conversion (sea-level ISA temperature) overestimates height by about
        # lapse x elevation / pad temperature: 1.1 % at a 500 m pad. Documented limitation (avionics/DATA_FORMAT.md §6).
        h = pressure_to_altitude(isa_pressure(800.0), isa_pressure(500.0))
        expected_bias = 0.0065 * 500.0 / (288.15 - 0.0065 * 500.0)
        self.assertAlmostEqual(h / 300.0 - 1.0, expected_bias, delta=0.001)
        ps = [isa_pressure(h) for h in range(0, 2000, 100)]
        hs = [pressure_to_altitude(p, ps[0]) for p in ps]
        self.assertEqual(hs, sorted(hs))

    def test_estimator_tracks_constant_acceleration(self):
        est = VerticalStateEstimator()
        g, a = 9.80665, 20.0
        for k in range(200):                                    # 50 Hz, 4 s at 20 m/s² upward
            t = k * 0.02
            est.on_accel(t, a + g)
            est.on_pressure(t, isa_pressure(0.5 * a * t * t) if k else isa_pressure(0.0))
        self.assertAlmostEqual(est.vertical_velocity, a * 3.98, delta=1.0)

    def test_barometer_only_mode_ignores_the_accelerometer(self):
        kf = VerticalKalmanFilter()
        kf.update(100.0)
        kf.baro_only = True
        kf.predict(1.0, 50.0)                                   # bogus acceleration under the parachute
        self.assertEqual(kf.v, 0.0)


# ------------------------------------------------------------------------------------------------ replay
class Replay(unittest.TestCase):
    def test_state_transitions_match_the_synthetic_truth(self):
        s, truth = _Replayed.get()["summary"], META["truth_events_s"]
        ev = s["flight_events"]
        self.assertEqual(list(ev), ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
        self.assertAlmostEqual(ev["LIFTOFF"], truth["liftoff"], delta=0.1)
        self.assertAlmostEqual(ev["BURNOUT"], truth["burnout"], delta=0.12)
        self.assertAlmostEqual(s["max_estimated_altitude"]["time_s"], truth["apogee"], delta=0.3)
        self.assertAlmostEqual(s["max_estimated_altitude"]["altitude_m"], META["truth_apogee_m"], delta=2.0)
        self.assertAlmostEqual(ev["LANDING"], truth["landing"], delta=1.0)
        order = ["PRELAUNCH", "ASCENT", "COAST", "DESCENT", "LANDED"]
        idx = [order.index(e["flight_state"]) for e in _Replayed.get()["estimates"]]
        self.assertEqual(idx, sorted(idx))

    def test_scripted_faults_are_detected_and_contained(self):
        r = _Replayed.get()
        tl = [(e["time_s"], e["event"]) for e in r["timeline"]]
        L = META["truth_events_s"]["liftoff"]
        for t, name in ((2.0, "IMU_INVALID_SAMPLE"), (round(L + 6.0, 2), "BARO_INVALID_SAMPLE"), (30.0, "BATTERY_INVALID_SAMPLE")):
            self.assertIn((t, name), tl)
        self.assertTrue(any(n == "GNSS_STALE" and L + 1 < t <= L + 4.1 for t, n in tl))
        self.assertTrue(any(n == "TEMP_STALE" and 20 < t <= 25 for t, n in tl))
        self.assertTrue(any(n == "TEMP_OK" and t >= 25 for t, n in tl))
        est = {round(e["timestamp"], 2): e for e in r["estimates"]}
        t_spike = round(L + 6.0, 2)
        jump = abs(est[t_spike]["est_altitude_m"] - est[round(t_spike - 0.02, 2)]["est_altitude_m"])
        self.assertLess(jump, 2.0)                               # the impossible pressure did not move the estimate
        self.assertEqual(r["summary"]["logger_issue_counts"], {"barometric_pressure:out_of_range": 1,
                                                               "battery_voltage:out_of_range": 1,
                                                               "imu_accel_z:non_finite": 1})

    def test_logging_format_of_the_replay_log(self):
        tmp = tempfile.mkdtemp(prefix="astra66_rp_")
        try:
            r = R.replay(R.SAMPLE, out_dir=tmp)
            with open(r["paths"]["log.csv"], encoding="utf-8", newline="") as fh:
                rows = list(csv.reader(fh))
            self.assertEqual(rows[0], load_schema().names)
            self.assertTrue(all(int(x[-1], 16) == crc16(",".join(x[:-1])) for x in rows[1:]))
            recs, rep = read_flight_log(r["paths"]["log.csv"])
            self.assertEqual(sum(rep.dropped.values()), 0)
            self.assertEqual(rep.data_sources, {"SYNTHETIC"})
            with open(r["paths"]["estimates.csv"], encoding="utf-8") as fh:
                self.assertEqual(fh.readline().strip().split(","), R.ESTIMATE_COLUMNS)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_committed_replay_outputs_are_current(self):
        fresh = _Replayed.get()
        committed = json.loads((COMMITTED / "replay_events.json").read_text(encoding="utf-8"))
        self.assertEqual(fresh["summary"]["flight_events"], committed["summary"]["flight_events"])
        self.assertEqual([e["event"] for e in fresh["timeline"]], [e["event"] for e in committed["timeline"]])
        rows = _read_csv(COMMITTED / "replay_estimates.csv")
        self.assertEqual(len(rows), len(fresh["estimates"]))
        for a, b in zip(fresh["estimates"][::37], rows[::37]):
            self.assertEqual(a["flight_state"], b["flight_state"])
            if b["est_altitude_m"]:
                self.assertAlmostEqual(a["est_altitude_m"], float(b["est_altitude_m"]), delta=0.02)

    def test_sample_dataset_is_deterministic(self):
        tmp = tempfile.mkdtemp(prefix="astra66_sm_")
        try:
            p = os.path.join(tmp, "s.csv")
            R.make_sample(p, os.path.join(tmp, "s.meta.json"))
            a, b = _read_csv(p), _read_csv(R.SAMPLE)
            self.assertEqual(len(a), len(b))
            for ra, rb in zip(a[::53], b[::53]):
                for k, v in rb.items():
                    if v in ("", "nan") or k == "data_source":
                        self.assertEqual(ra[k], v)
                    else:
                        self.assertAlmostEqual(float(ra[k]), float(v), delta=1e-6 + 1e-9 * abs(float(v)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bad_rows_in_recorded_data_are_skipped_and_counted(self):
        tmp = tempfile.mkdtemp(prefix="astra66_bad_")
        try:
            lines = (ROOT / "simulation" / "data" / "sample_flight.csv").read_text(encoding="utf-8").splitlines()
            lines.insert(101, lines[100])                        # duplicate
            lines[300], lines[301] = lines[301], lines[300]      # out of order
            lines[500] = "abc" + lines[500][lines[500].index(","):]   # unreadable timestamp
            p = os.path.join(tmp, "bad.csv")
            Path(p).write_text("\n".join(lines) + "\n", encoding="utf-8")
            s = R.replay(p)["summary"]
            self.assertEqual(s["rows_skipped"], dict(bad_timestamp=1, duplicate=1, non_monotonic=1, off_grid=0))
            self.assertIn("APOGEE", s["flight_events"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_mixed_or_unknown_data_source_is_refused(self):
        tmp = tempfile.mkdtemp(prefix="astra66_src_")
        try:
            lines = (ROOT / "simulation" / "data" / "sample_flight.csv").read_text(encoding="utf-8").splitlines()
            lines[5] = lines[5].replace("SYNTHETIC", "BENCH", 1)     # two different modes in one file
            p = os.path.join(tmp, "mixed.csv")
            Path(p).write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                R.replay(p)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ ground station
class GroundStation(unittest.TestCase):
    def test_sensor_replay_feed_serves_health_and_loss(self):
        from argparse import Namespace
        from avionics.ground_station import server
        feed = server.build_feed(Namespace(sensors=R.SAMPLE, simulate=False, capture=None, loss=0.05, bit_errors=0.02,
                                           seed=1, speed=1.0, loop=False))
        feed.clock = lambda: feed.start + 1000.0
        snap = feed.snapshot()
        self.assertTrue(snap["simulated"])
        self.assertTrue(snap["complete"])
        st = snap["stats"]
        self.assertGreater(st["packet_loss_percent"], 0)
        self.assertAlmostEqual(st["last_packet_time_s"], snap["frames"][-1]["time_s"])
        for k in ("imu_ok", "baro_ok", "gnss_ok", "temp_ok", "battery_ok", "gps_fix", "flight_state"):
            self.assertIn(k, snap["frames"][-1])


# ------------------------------------------------------------------------------------------------ integration docs
class IntegrationDocuments(unittest.TestCase):
    def test_cad_mass_integration_report_is_current_and_has_no_fail(self):
        res = CMI.build()
        statuses = [c[2] for c in res["checks"]]
        self.assertNotIn("FAIL", statuses)
        report = (ROOT / "documentation" / "CAD_AVIONICS_INTEGRATION.md").read_text(encoding="utf-8")
        counts = {k: statuses.count(k) for k in ("PASS", "WARN", "UNVERIFIED", "FAIL")}
        self.assertIn(f"{counts['PASS']} PASS · {counts['WARN']} WARN · {counts['UNVERIFIED']} UNVERIFIED", report)
        rows = _read_csv(ROOT / "avionics" / "integration" / "avionics_mass_properties.csv")
        self.assertEqual([r["component"] for r in rows], [r["component"] for r in res["rows"]])
        for a, b in zip(res["rows"], rows):
            self.assertAlmostEqual(a["cg_shift_per_10g_mm"], float(b["cg_shift_per_10g_mm"]), delta=0.011)

    def test_data_format_documents_every_field(self):
        doc = (ROOT / "avionics" / "DATA_FORMAT.md").read_text(encoding="utf-8")
        for f in load_schema().names + R.ESTIMATE_COLUMNS + list(P.HEALTH_BITS):
            self.assertIn(f"`{f}`", doc, f)

    def test_hardware_mapping_marks_every_component(self):
        doc = (ROOT / "avionics" / "HARDWARE_MAPPING.md").read_text(encoding="utf-8")
        for word in ("Required", "Optional", "Prototype assumption", "Needs bench validation", "Needs flight/range approval",
                     "COMPONENT TO BE SELECTED", "NOT flight certified"):
            self.assertIn(word, doc)
        for comp in ("IMU", "Barometer", "GNSS", "Temperature", "Battery monitor", "Microcontroller", "Storage", "Radio",
                     "Separation"):
            self.assertIn(comp, doc)

    def test_status_report_makes_no_unsupported_claims(self):
        doc = (ROOT / "documentation" / "PHASE_5_STATUS.md").read_text(encoding="utf-8").lower()
        self.assertIn("not flight certified", doc)
        for claim in ("flight certified.", "successful flight", "sensors were validated", "radio was validated",
                      "flight-ready", "flight ready"):
            if claim in doc:
                # every occurrence must be negated in the same sentence
                for part in doc.split(claim)[:-1]:
                    tail = part[-60:]
                    self.assertTrue(any(n in tail for n in ("not ", "no ", "never", "without")), claim)


# ------------------------------------------------------------------------------------------------ data sources
class DataSourceModes(unittest.TestCase):
    """SYNTHETIC / BENCH / FLIGHT: the same pipeline consumes all three; FLIGHT stays disabled until real data exist."""

    def test_modes_and_legacy_aliases(self):
        self.assertEqual(DS.normalise("SIMULATED"), DS.SYNTHETIC)      # Phase 4 label
        self.assertEqual(DS.normalise("hardware"), DS.BENCH)
        self.assertEqual(DS.normalise(DS.FLIGHT), DS.FLIGHT)
        self.assertFalse(DS.is_real_sensor_data("SIMULATED"))
        self.assertTrue(DS.is_real_sensor_data("BENCH"))
        for bad in ("", None, "REAL", "sim"):
            with self.assertRaises(ValueError):
                DS.normalise(bad)

    def test_flight_mode_is_disabled_by_default(self):
        self.assertFalse(DS.ENABLED[DS.FLIGHT])
        self.assertEqual(DS.check_available("BENCH"), DS.BENCH)
        with self.assertRaises(DS.DataSourceNotAvailable):
            DS.check_available(DS.FLIGHT)
        self.assertEqual(DS.check_available(DS.FLIGHT, allow_flight=True), DS.FLIGHT)   # only for a real record

    def test_logger_refuses_flight_data_unless_allowed(self):
        from avionics.firmware.logging.logger import DataLogger, MemorySink
        with self.assertRaises(DS.DataSourceNotAvailable):
            DataLogger(MemorySink(), "FLIGHT", 0.02)
        lg = DataLogger(MemorySink(), "BENCH", 0.02)
        self.assertEqual(lg.mode, DS.BENCH)
        self.assertFalse(lg.log(dict(seq=0, timestamp=0.0, data_source="SYNTHETIC"))[0])   # mode mismatch

    def test_replay_accepts_bench_data_and_refuses_flight(self):
        tmp = tempfile.mkdtemp(prefix="astra66_ds_")
        try:
            text = (ROOT / "simulation" / "data" / "sample_flight.csv").read_text(encoding="utf-8")
            bench = os.path.join(tmp, "bench.csv")
            Path(bench).write_text(text.replace("SYNTHETIC", "BENCH"), encoding="utf-8")
            r = R.replay(bench)
            self.assertEqual(r["summary"]["data_source_mode"], "BENCH")
            self.assertIn("BENCH DATA", r["summary"]["data_source_label"])
            self.assertEqual(list(r["summary"]["flight_events"]), ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
            self.assertTrue(all(not f.simulated for f in r["frames"]))     # packets not marked SIMULATED
            flight = os.path.join(tmp, "flight.csv")
            Path(flight).write_text(text.replace("SYNTHETIC", "FLIGHT"), encoding="utf-8")
            with self.assertRaises(DS.DataSourceNotAvailable):
                R.replay(flight)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_analysis_labels_bench_data_as_bench(self):
        tmp = tempfile.mkdtemp(prefix="astra66_ds2_")
        try:
            log = os.path.join(tmp, "bench_log.csv")
            R.replay(R.SAMPLE, out_dir=tmp)
            from avionics.firmware.crc import crc16 as _crc
            rows = (Path(tmp) / "replay_log.csv").read_text(encoding="utf-8").splitlines()
            out = [rows[0]]
            for ln in rows[1:]:
                body = ",".join(ln.split(",")[:-1]).replace("SYNTHETIC", "BENCH")
                out.append(f"{body},{_crc(body):04X}")
            Path(log).write_text(NEWLINE.join(out) + NEWLINE, encoding="utf-8")
            summary, out_dir = A.run(log, os.path.join(tmp, "out"))
            self.assertEqual(summary["data_source_modes"], ["BENCH"])
            report = (Path(out_dir) / "flight_report.md").read_text(encoding="utf-8")
            self.assertIn("BENCH DATA", report)
            self.assertNotIn("SYNTHETIC DATA", report)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BenchDataTemplate(unittest.TestCase):
    def test_template_has_the_record_columns_and_is_labelled_synthetic(self):
        rows = _read_csv(ROOT / "avionics" / "bench_data" / "example_bench_record.csv")
        self.assertEqual(list(rows[0]), R.INPUT_COLUMNS)
        self.assertEqual({r["data_source"] for r in rows}, {"SYNTHETIC"})
        meta = json.loads((ROOT / "avionics" / "bench_data" / "example_bench_record.meta.json").read_text(encoding="utf-8"))
        self.assertIn("SYNTHETIC values", meta["title"])
        self.assertIn("BENCH", meta["purpose"])
        readme = (ROOT / "avionics" / "bench_data" / "README.md").read_text(encoding="utf-8")
        self.assertIn("no real bench data", readme.lower())
        self.assertIn("NOT flight certified", readme)

    def test_template_replays_through_the_same_pipeline(self):
        r = R.replay(ROOT / "avionics" / "bench_data" / "example_bench_record.csv")
        self.assertEqual(r["summary"]["data_source_mode"], "SYNTHETIC")
        self.assertEqual(r["summary"]["rows_used"], 501)
        self.assertEqual(r["summary"]["flight_events"], {})            # 10 s on the pad: no flight events
        self.assertTrue(all(e["flight_state"] == "PRELAUNCH" for e in r["estimates"]))


class Phase6Documents(unittest.TestCase):
    DOCS = ("documentation/HARDWARE_INTEGRATION_STATUS.md", "documentation/HARDWARE_SELECTION_CHECKLIST.md",
            "documentation/CAD_AVIONICS_INTEGRATION.md", "documentation/AVIONICS_BENCH_TEST_PLAN.md",
            "documentation/MASS_MEASUREMENT_PROCEDURE.md", "avionics/bench_data/README.md",
            "documentation/PROJECT_OVERVIEW.md", "documentation/ENGINEERING_METHOD.md", "documentation/VALIDATION.md",
            "documentation/HARDWARE_INTEGRATION.md", "documentation/TEST_PLAN.md", "documentation/REPRODUCIBILITY.md",
            "documentation/ROADMAP.md", "documentation/images/README.md", "documentation/RELEASE_READINESS.md",
            "README.md")

    def test_documents_exist_and_carry_the_disclaimer(self):
        for rel in self.DOCS:
            with self.subTest(doc=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertRegex(text.lower(), r"not flight certified", rel)

    # Claims that must never stand unqualified. A sentence may use them only when it denies them ("nothing has been
    # validated") or limits them to software / CAD / numerics ("validated in software, not on hardware").
    CLAIMS = ("we measured", "component selected:", "flight proven", "flight tested", "has been validated",
              "was validated", "hardware is validated")
    NEGATIONS = ("not ", "no ", "never", "nothing", "none", "without", "has not", "cannot", "unverified")
    QUALIFIERS = ("software", "synthetic", "cad model", "numeric", "simulation", "in simulation", "on the bench plan")

    def test_no_invented_measurements_or_part_numbers_claimed_as_selected(self):
        for rel in self.DOCS:
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            # Headings are section labels, not claims: their section body carries the caveat. Drop them first, then
            # split the prose into sentences (paragraph breaks end a sentence too).
            body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
            for sentence in re.split(r"(?<=[.!?:|])\s+|\n\s*\n", body):
                for claim in self.CLAIMS:
                    if claim in sentence:
                        ok = any(n in sentence for n in self.NEGATIONS) or any(q in sentence for q in self.QUALIFIERS)
                        self.assertTrue(ok, f"{rel}: unqualified claim {claim!r} in: {sentence.strip()[:160]}")

    def test_readiness_categories_and_bench_tests_are_documented(self):
        status = (ROOT / "documentation" / "HARDWARE_INTEGRATION_STATUS.md").read_text(encoding="utf-8")
        for tag in ("PASS", "ASSUMED", "UNVERIFIED", "REQUIRES HARDWARE", "REQUIRES MENTOR/RANGE REVIEW"):
            self.assertIn(tag, status)
        plan = (ROOT / "documentation" / "AVIONICS_BENCH_TEST_PLAN.md").read_text(encoding="utf-8")
        for topic in ("Power-up", "Sensor detection", "IMU data sanity", "Pressure sensor sanity", "GNSS acquisition",
                      "Data logging", "Packet generation", "Packet integrity", "Receiver / ground-station",
                      "Packet-loss handling", "Timestamp consistency", "Battery monitoring", "Long-duration logging",
                      "Power-down / data preservation"):
            self.assertIn(topic, plan)
        for banned in ("igniter", "pyrotechnic", "ejection charge"):
            for line in plan.splitlines():
                if banned in line.lower():
                    self.assertTrue(any(n in line.lower() for n in ("no ", "not ", "never")), line)

    def test_engineering_status_has_the_three_readiness_sections(self):
        text = (ROOT / "documentation" / "ENGINEERING_STATUS.md").read_text(encoding="utf-8")
        for heading in ("VERIFIED BY SOFTWARE", "REQUIRES PHYSICAL BENCH VALIDATION", "REQUIRES QUALIFIED ROCKETRY REVIEW"):
            self.assertIn(heading, text)
        self.assertIn("NOT FLIGHT CERTIFIED", text)


if __name__ == "__main__":
    unittest.main()
