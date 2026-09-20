"""Missing-data and corrupted-data handling: sensor faults in flight, damaged log files."""
import os
import shutil
import tempfile
import unittest

from avionics.firmware.crc import crc16
from avionics.firmware.logging.reader import read_flight_log
from avionics.firmware.sensor_interfaces.simulated import FaultConfig

from .helpers import TOL, event_times, fly


class DamagedLogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="astra66_av_")
        cls.path = os.path.join(cls.tmp, "clean.csv")
        fly(csv_path=cls.path)
        with open(cls.path, encoding="utf-8") as fh:
            cls.lines = fh.read().splitlines()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def write(self, name, lines):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write("\n".join(lines))
        return p

    @staticmethod
    def resign(line):
        body = line.rsplit(",", 1)[0]
        return f"{body},{crc16(body):04X}"

    def test_clean_log_reads_completely(self):
        recs, rep = read_flight_log(self.path)
        self.assertEqual(rep.rows_ok, len(self.lines) - 1)
        self.assertTrue(rep.crc_checked)
        self.assertEqual(sum(rep.dropped.values()), 0)

    def test_bit_flip_is_caught_by_crc(self):
        lines = list(self.lines)
        cells = lines[200].split(",")
        k = self.lines[0].split(",").index("imu_accel_z")
        cells[k] = cells[k][:-1] + ("1" if cells[k][-1] != "1" else "2")    # one digit changed, CRC left as is
        lines[200] = ",".join(cells)
        recs, rep = read_flight_log(self.write("flip.csv", lines))
        self.assertEqual(rep.dropped["crc_mismatch"], 1)
        self.assertEqual(rep.rows_ok, len(self.lines) - 2)

    def test_truncated_last_line_and_garbage(self):
        lines = list(self.lines)
        lines[-1] = lines[-1][:25]                      # power loss mid-write
        lines.insert(100, "\x00\x00\x00garbage")        # card corruption
        recs, rep = read_flight_log(self.write("trunc.csv", lines))
        self.assertEqual(rep.dropped["malformed"], 2)
        self.assertEqual(rep.rows_ok, len(self.lines) - 2)

    def test_out_of_order_and_duplicate_rows_dropped(self):
        lines = list(self.lines)
        lines[300], lines[301] = lines[301], lines[300]
        lines.insert(400, lines[399])
        recs, rep = read_flight_log(self.write("order.csv", lines))
        self.assertEqual(rep.dropped["non_monotonic"], 1)
        self.assertEqual(rep.dropped["duplicate"], 1)
        ts = [r["timestamp"] for r in recs]
        self.assertEqual(ts, sorted(set(ts)))

    def test_bad_values_become_missing_rows_kept(self):
        header = self.lines[0].split(",")
        ti, ai = header.index("temperature"), header.index("imu_accel_z")
        lines = list(self.lines)
        cells = lines[1].split(",")
        cells[ti], cells[ai] = "nan", "abc"
        lines[1] = self.resign(",".join(cells))
        recs, rep = read_flight_log(self.write("values.csv", lines))
        self.assertEqual(rep.rows_ok, len(self.lines) - 1)
        self.assertIsNone(recs[0]["temperature"])
        self.assertIsNone(recs[0]["imu_accel_z"])
        self.assertEqual(rep.value_issues["temperature:non_finite"], 1)
        self.assertEqual(rep.value_issues["imu_accel_z:unparseable"], 1)

    def test_missing_required_timestamp_rejects_row(self):
        header = self.lines[0].split(",")
        lines = list(self.lines)
        cells = lines[5].split(",")
        cells[header.index("timestamp")] = ""
        lines[5] = self.resign(",".join(cells))
        recs, rep = read_flight_log(self.write("nots.csv", lines))
        self.assertEqual(rep.dropped["rejected"], 1)

    def test_log_without_crc_column_or_some_fields(self):
        header = self.lines[0].split(",")
        keep = [header.index(n) for n in ("seq", "timestamp", "data_source", "altitude")]
        lines = [",".join(line.split(",")[i] for i in keep) for line in self.lines]
        recs, rep = read_flight_log(self.write("subset.csv", lines))
        self.assertFalse(rep.crc_checked)
        self.assertIn("imu_accel_z", rep.header_missing)
        self.assertEqual(rep.rows_ok, len(self.lines) - 1)
        self.assertIsNone(recs[10]["imu_accel_z"])

    def test_empty_file(self):
        recs, rep = read_flight_log(self.write("empty.csv", []))
        self.assertEqual((recs, rep.rows_total), ([], 0))


class SensorFaultsInFlight(unittest.TestCase):
    def test_dropouts_and_nans_do_not_break_the_chain(self):
        faults = dict(baro=FaultConfig(dropout_prob=0.2), imu=FaultConfig(nan_prob=0.05, dropout_prob=0.05),
                      gnss=FaultConfig(dropout_prob=0.3), temperature=FaultConfig(nan_prob=0.2))
        r = fly(faults=faults, seed=4)
        ev, p = event_times(r["events"]), r["profile"]
        self.assertEqual(list(ev)[:4], ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
        self.assertAlmostEqual(ev["LIFTOFF"], p.t_liftoff, delta=TOL["liftoff"] + 0.05)
        self.assertGreater(r["logger"].counts["values_rejected"], 0)            # NaNs were flagged, not written
        self.assertEqual(r["logger"].counts["rejected"], 0)                     # no frame lost
        flagged = [x for x in r["records"] if x["quality_flags"]]
        self.assertTrue(flagged)
        self.assertTrue(all(x["temperature"] is None for x in flagged if x["quality_flags"] & (1 << 3)))

    def test_barometer_failure_keeps_logging(self):
        r = fly(faults=dict(baro=FaultConfig(dropout_prob=1.0)), seed=5)
        self.assertTrue(all(x["altitude"] is None for x in r["records"]))
        self.assertIn("LIFTOFF", event_times(r["events"]))                      # accelerometer still sees launch
        self.assertEqual(r["logger"].counts["rejected"], 0)


if __name__ == "__main__":
    unittest.main()
