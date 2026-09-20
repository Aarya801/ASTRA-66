"""Timestamp handling: counter wrap, monotonic checks, gaps, fixed-rate frame times."""
import unittest

from avionics.firmware.logging.logger import DataLogger, MemorySink
from avionics.firmware.logging.timebase import CounterUnwrapper, TimestampMonitor, unwrap_counter

from .helpers import nominal_flight


class CounterWrap(unittest.TestCase):
    def test_32_bit_wrap(self):
        m = 1 << 32
        self.assertEqual(unwrap_counter([m - 10, m - 1, 5, 20]), [m - 10, m - 1, m + 5, m + 20])

    def test_16_bit_multiple_wraps(self):
        raw = [(i * 20_000) % 65536 for i in range(20)]
        out = unwrap_counter(raw, bits=16)
        self.assertEqual(out, [i * 20_000 for i in range(20)])

    def test_rejects_values_outside_counter_width(self):
        with self.assertRaises(ValueError):
            CounterUnwrapper(bits=16)(70000)


class Monitor(unittest.TestCase):
    def test_classification(self):
        m = TimestampMonitor(0.02)
        self.assertEqual(m.check(0.00), (True, None))
        self.assertEqual(m.check(0.02), (True, None))
        self.assertEqual(m.check(0.02), (False, "duplicate"))
        self.assertEqual(m.check(0.01), (False, "non_monotonic"))
        self.assertEqual(m.check(0.20), (True, "gap"))
        self.assertEqual(m.counts, dict(ok=2, gap=1, duplicate=1, non_monotonic=1))


class LoggerTimestamps(unittest.TestCase):
    def frame(self, seq, t):
        return dict(seq=seq, timestamp=t, flight_state="PRELAUNCH")

    def test_logger_never_writes_time_backwards_and_flags_gaps(self):
        sink = MemorySink()
        lg = DataLogger(sink, "SIMULATED", 0.02)
        self.assertTrue(lg.log(self.frame(0, 0.00))[0])
        self.assertTrue(lg.log(self.frame(1, 0.02))[0])
        self.assertFalse(lg.log(self.frame(2, 0.01))[0])          # backwards
        self.assertFalse(lg.log(self.frame(3, 0.02))[0])          # duplicate
        self.assertTrue(lg.log(self.frame(4, 0.50))[0])           # gap: kept, flagged
        self.assertEqual([r["timestamp"] for r in sink.records], [0.0, 0.02, 0.5])
        self.assertTrue(sink.records[-1]["quality_flags"] & (1 << 6))
        self.assertEqual(lg.counts["rejected"], 2)
        self.assertEqual(lg.counts["timestamp_gaps"], 1)

    def test_flight_computer_frames_are_exactly_periodic(self):
        recs = nominal_flight()["records"]
        ts = [r["timestamp"] for r in recs]
        self.assertTrue(all(abs((b - a) - 0.02) < 1e-9 for a, b in zip(ts, ts[1:])))
        self.assertEqual([r["seq"] for r in recs], list(range(len(recs))))


if __name__ == "__main__":
    unittest.main()
