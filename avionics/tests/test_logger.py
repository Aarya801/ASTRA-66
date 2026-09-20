"""Data logging: CSV / JSON-lines sinks, metadata, freshness, SIMULATED labelling, the committed example dataset."""
import csv
import json
import os
import shutil
import tempfile
import unittest

from avionics.firmware.crc import crc16
from avionics.firmware.flight_computer import FlightComputer
from avionics.firmware.logging.logger import CsvLogSink, DataLogger, JsonlLogSink, MemorySink
from avionics.firmware.logging.reader import read_flight_log
from avionics.firmware.logging.schema import load_schema
from avionics.firmware.sensor_interfaces.simulated import SyntheticFlightProfile, simulated_sensor_suite
from avionics.firmware.simulate_flight import EXAMPLE_DIR, EXAMPLE_STEM, run_simulated_flight

from .helpers import nominal_flight

FRAME = dict(seq=0, timestamp=0.0, flight_state="PRELAUNCH", imu_accel_z=9.80665, temperature=21.456789, latitude=None)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _json(path):
    return json.loads(_text(path))


class Sinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="astra66_log_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_csv_header_crc_and_round_trip(self):
        path, meta = os.path.join(self.tmp, "a.csv"), os.path.join(self.tmp, "a.meta.json")
        lg = DataLogger(CsvLogSink(path), "SIMULATED", 0.02, meta_path=meta, metadata=dict(note="unit test"))
        lg.log(FRAME)
        lg.log({**FRAME, "seq": 1, "timestamp": 0.02, "temperature": float("nan")})
        s = lg.close()
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0], load_schema().names)
        for r in rows[1:]:
            self.assertEqual(int(r[-1], 16), crc16(",".join(r[:-1])))
        recs, rep = read_flight_log(path)
        self.assertEqual(recs[0]["temperature"], 21.46)            # schema decimals
        self.assertIsNone(recs[1]["temperature"])
        self.assertTrue(recs[1]["quality_flags"] & (1 << 3))
        m = _json(meta)
        self.assertEqual((m["data_source"], m["counts"]["written"], m["note"]), ("SIMULATED", 2, "unit test"))
        self.assertEqual(s["issue_counts"], {"temperature:non_finite": 1})

    def test_jsonl_sink(self):
        path = os.path.join(self.tmp, "a.jsonl")
        lg = DataLogger(JsonlLogSink(path), "SIMULATED", 0.02)
        lg.log(FRAME)
        lg.close()
        obj = json.loads(_text(path).splitlines()[0])
        self.assertEqual(obj["data_source"], "SIMULATED")
        self.assertEqual(obj["crc16"], f"{crc16(JsonlLogSink.canonical(obj)):04X}")
        self.assertEqual(set(obj), set(load_schema().names))

    def test_source_labels_cannot_be_mixed(self):
        with self.assertRaises(ValueError):
            DataLogger(MemorySink(), "REAL", 0.02)
        lg = DataLogger(MemorySink(), "SIMULATED", 0.02)
        self.assertFalse(lg.log({**FRAME, "data_source": "HARDWARE"})[0])
        p = SyntheticFlightProfile()
        with self.assertRaises(ValueError):                         # simulated sensors may not log as HARDWARE
            FlightComputer(simulated_sensor_suite(p), logger=DataLogger(MemorySink(), "HARDWARE", 0.02))


class FlightLog(unittest.TestCase):
    def test_slow_sensors_are_logged_only_when_fresh(self):
        recs = nominal_flight()["records"]
        n = len(recs)
        dur = recs[-1]["timestamp"]
        self.assertEqual(sum(r["altitude"] is not None for r in recs), n)              # 50 Hz baro every frame
        self.assertAlmostEqual(sum(r["battery_voltage"] is not None for r in recs), dur, delta=2)   # 1 Hz
        self.assertAlmostEqual(sum(r["gps_fix"] is not None for r in recs), dur, delta=2)
        self.assertTrue(all(r["data_source"] == "SIMULATED" for r in recs))


class CommittedExample(unittest.TestCase):
    """The committed example must be valid, labelled SIMULATED, and reproducible by the generator."""

    @classmethod
    def setUpClass(cls):
        cls.csv = os.path.join(EXAMPLE_DIR, EXAMPLE_STEM + ".csv")
        cls.meta = _json(os.path.join(EXAMPLE_DIR, EXAMPLE_STEM + ".meta.json"))
        cls.recs, cls.rep = read_flight_log(cls.csv)

    def test_valid_and_labelled(self):
        self.assertTrue(self.rep.crc_checked)
        self.assertEqual(sum(self.rep.dropped.values()), 0)
        self.assertEqual(self.rep.data_sources, {"SIMULATED"})
        self.assertEqual(self.meta["data_source"], "SIMULATED")
        self.assertIn("NOT FLIGHT DATA", self.meta["title"])
        self.assertIn("PLACEHOLDER", self.meta["truth_profile"])
        self.assertEqual(self.meta["counts"]["written"], len(self.recs))

    def test_regenerates_to_the_same_data(self):
        tmp = tempfile.mkdtemp(prefix="astra66_ex_")
        try:
            r = run_simulated_flight(out_dir=tmp)
            recs, _ = read_flight_log(r["paths"]["csv"])
            self.assertEqual(len(recs), len(self.recs))
            for a, b in zip(recs[::97], self.recs[::97]):
                for k in ("timestamp", "altitude", "imu_accel_z", "vertical_velocity", "battery_voltage", "latitude"):
                    if b[k] is None:
                        self.assertIsNone(a[k])
                    else:
                        self.assertAlmostEqual(a[k], b[k], delta=0.02 if k != "latitude" else 1e-6)
                self.assertEqual(a["flight_state"], b["flight_state"])
            meta = _json(r["paths"]["meta"])
            self.assertEqual(meta["detected_events_s"], self.meta["detected_events_s"])
            with open(r["paths"]["capture"], encoding="utf-8") as f1, \
                    open(os.path.join(EXAMPLE_DIR, EXAMPLE_STEM + "_telemetry_capture.csv"), encoding="utf-8") as f2:
                self.assertEqual(sum(1 for _ in f1), sum(1 for _ in f2))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
