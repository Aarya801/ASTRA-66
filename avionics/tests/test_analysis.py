"""Post-flight analysis calculations and outputs."""
import json
import math
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

from avionics.analysis import flight_data_analysis as A
from avionics.firmware.logging.reader import read_flight_log
from avionics.firmware.sensor_interfaces.simulated import FaultConfig

from .helpers import ROOT, fly


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _json(path):
    return json.loads(_text(path))


class Numerics(unittest.TestCase):
    def test_moving_average_and_derivative(self):
        t = [i * 0.1 for i in range(50)]
        self.assertTrue(all(abs(v - 3.0) < 1e-12 for v in A.moving_average(t, [3.0] * 50, 0.5)))
        d = A.derivative(t, [2.0 * x + 1 for x in t])
        self.assertTrue(all(abs(v - 2.0) < 1e-9 for v in d))

    def test_velocity_from_parabolic_altitude(self):
        t = [i * 0.02 for i in range(600)]
        h = [100 * x - 4.9 * x * x for x in t]
        v = A.velocity_from_altitude(t, h)
        for i in range(50, 550, 50):
            self.assertAlmostEqual(v[i], 100 - 9.8 * t[i], delta=0.05)

    def test_geodesy(self):
        self.assertAlmostEqual(A.haversine_m(0, 0, 1, 0), 111_195, delta=5)
        e, n = A.local_en(0.001, 0.002, 0.0, 0.0)
        self.assertAlmostEqual(e, 222.39, delta=0.1)
        self.assertAlmostEqual(n, 111.19, delta=0.1)

    def test_median(self):
        self.assertEqual(A._median([3, 1, 2]), 2)
        self.assertEqual(A._median([4, 1, 2, 3]), 2.5)
        self.assertIsNone(A._median([]))


class AnalysisOfSimulatedFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="astra66_an_")
        cls.log = os.path.join(cls.tmp, "flight.csv")
        cls.flight = fly(csv_path=cls.log, seed=1)
        cls.summary, cls.out = A.run(cls.log, os.path.join(cls.tmp, "out"))
        cls.p = cls.flight["profile"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_derived_statistics_match_truth(self):
        s, p = self.summary, self.p
        self.assertTrue(s["simulated"])
        self.assertAlmostEqual(s["apogee"]["altitude_m"], max(p.h), delta=2.0)
        self.assertAlmostEqual(s["apogee"]["time_s"], p.t_apogee, delta=0.3)
        # The derived velocity is smoothed twice (0.3 s windows), which blunts the sharp velocity peak at burnout;
        # the logged onboard (Kalman) estimate follows it closely.
        self.assertAlmostEqual(s["max_vertical_velocity"]["mps"], max(p.v), delta=6.0)
        self.assertLess(s["max_vertical_velocity"]["mps"], max(p.v))
        self.assertAlmostEqual(s["onboard_max_vertical_velocity"]["mps"], max(p.v), delta=2.0)
        self.assertAlmostEqual(s["descent_rate_mps"], 5.0, delta=0.3)
        self.assertAlmostEqual(s["event_times_s"]["liftoff"], p.t_liftoff, delta=0.1)
        self.assertAlmostEqual(s["event_times_s"]["landing"], p.t_landing, delta=1.0)
        self.assertAlmostEqual(s["timing_s"]["flight_duration"], p.t_landing - p.t_liftoff, delta=1.0)
        peak_sf = max(p.a) + 9.80665
        self.assertAlmostEqual(s["max_axial_specific_force"]["mps2"], peak_sf, delta=2.0)

    def test_gnss_and_battery(self):
        g, b = self.summary["gnss"], self.summary["battery_voltage_v"]
        flight = self.p.t_landing - self.p.t_liftoff
        self.assertAlmostEqual(g["last_fix_distance_from_first_m"], math.hypot(2.0, 1.0) * flight, delta=8.0)
        self.assertGreater(g["fixes"], 10)
        duration = self.summary["time_span_s"][1]
        self.assertAlmostEqual(b["drop"], 0.0008 * duration, delta=0.02)     # synthetic discharge slope ± noise
        self.assertGreater(b["start"], b["min"])

    def test_outputs_written_and_parse(self):
        want = {"altitude_vs_time.svg", "velocity_vs_time.svg", "acceleration_vs_time.svg", "temperature_vs_time.svg",
                "battery_voltage_vs_time.svg", "gps_track.svg", "flight_summary.json", "flight_report.md"}
        self.assertEqual(set(os.listdir(self.out)), want)
        for f in want:
            if f.endswith(".svg"):
                root = ET.parse(os.path.join(self.out, f)).getroot()
                self.assertIn("SYNTHETIC DATA (not flight data)", ET.tostring(root, encoding="unicode"))
        rep = _text(os.path.join(self.out, "flight_report.md"))
        self.assertIn("SYNTHETIC DATA: not flight data", rep)
        self.assertEqual(_json(os.path.join(self.out, "flight_summary.json"))["rows"],
                         self.summary["rows"])


class MissingData(unittest.TestCase):
    def test_no_gnss_no_track_and_offline_states(self):
        tmp = tempfile.mkdtemp(prefix="astra66_an2_")
        try:
            log = os.path.join(tmp, "nogps.csv")
            fly(csv_path=log, faults=dict(gnss=FaultConfig(dropout_prob=1.0)), seed=2)
            # blank the flight_state column (and re-sign rows) to force offline reconstruction
            from avionics.firmware.crc import crc16
            lines = _text(log).splitlines()
            k = lines[0].split(",").index("flight_state")
            out = [lines[0]]
            for ln in lines[1:]:
                c = ln.split(",")
                c[k] = ""
                body = ",".join(c[:-1])
                out.append(f"{body},{crc16(body):04X}")
            with open(log, "w", encoding="utf-8", newline="") as fh:
                fh.write("\n".join(out) + "\n")
            s, o = A.run(log, os.path.join(tmp, "out"))
            self.assertIsNone(s["gnss"])
            self.assertNotIn("gps_track.svg", os.listdir(o))
            self.assertTrue(s["flight_states_source"].startswith("reconstructed"))
            self.assertEqual(set(s["state_transitions_s"]), {"PRELAUNCH", "ASCENT", "COAST", "DESCENT", "LANDED"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_empty_log_is_an_error(self):
        with self.assertRaises(ValueError):
            A.analyse([])


class CommittedExampleResults(unittest.TestCase):
    def test_committed_summary_matches_a_fresh_analysis(self):
        base = os.path.join(ROOT, "avionics", "analysis", "results", "example_flight_simulated")
        committed = _json(os.path.join(base, "flight_summary.json"))
        recs, rep = read_flight_log(os.path.join(ROOT, "avionics", "data", "example", "example_flight_simulated.csv"))
        fresh = A.analyse(recs, rep)
        for key in ("apogee", "max_vertical_velocity", "descent_rate_mps", "event_times_s", "timing_s", "gnss"):
            self.assertEqual(json.loads(json.dumps(fresh[key])), committed[key], key)


if __name__ == "__main__":
    unittest.main()
