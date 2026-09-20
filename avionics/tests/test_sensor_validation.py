"""Sensor layer and sensor-data validation."""
import math
import unittest

from avionics.firmware.logging.schema import load_schema
from avionics.firmware.sensor_interfaces.base import (COMPONENT_TO_BE_SELECTED, HardwareSensorNotSelected,
                                                      HardwareSensorPlaceholder)
from avionics.firmware.sensor_interfaces.catalog import SENSOR_SPECS
from avionics.firmware.sensor_interfaces.simulated import (G0, P0, FaultConfig, SimulatedBarometer, SimulatedGNSS,
                                                           SimulatedIMU, SyntheticFlightProfile, isa_pressure)

GOOD = dict(seq=1, timestamp=0.02, data_source="SIMULATED", flight_state="PRELAUNCH", imu_accel_x=0.1, imu_accel_y=-0.1,
            imu_accel_z=9.8, gyro_x=0.0, gyro_y=0.0, gyro_z=0.0, barometric_pressure=101325.0, altitude=0.0,
            vertical_velocity=0.0, temperature=20.0, battery_voltage=4.1, separation_detected=0)


class SchemaValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_schema()

    def test_requested_fields_present_with_units(self):
        for name in ("timestamp", "imu_accel_x", "imu_accel_y", "imu_accel_z", "gyro_x", "gyro_y", "gyro_z",
                     "barometric_pressure", "altitude", "temperature", "latitude", "longitude", "gps_altitude",
                     "battery_voltage"):
            with self.subTest(field=name):
                f = self.schema.by_name[name]
                self.assertTrue(f.unit and f.description)
        self.assertEqual(self.schema.names[-1], "crc16")

    def test_good_record_passes_unchanged(self):
        res = self.schema.validate(GOOD)
        self.assertFalse(res.rejected)
        self.assertEqual(res.issues, [])
        self.assertEqual(res.quality_flags, 0)
        self.assertEqual(res.record["imu_accel_z"], 9.8)
        self.assertIsNone(res.record["latitude"])           # optional, simply absent

    def test_non_finite_value_rejected_and_flagged(self):
        res = self.schema.validate({**GOOD, "imu_accel_z": float("nan"), "gyro_x": float("inf")})
        self.assertIsNone(res.record["imu_accel_z"])
        self.assertIsNone(res.record["gyro_x"])
        self.assertEqual(res.quality_flags & 0b11, 0b11)    # accel + gyro bits
        self.assertFalse(res.rejected)

    def test_out_of_range_is_not_clipped(self):
        res = self.schema.validate({**GOOD, "barometric_pressure": 250000.0, "battery_voltage": -1.0})
        self.assertIsNone(res.record["barometric_pressure"])
        self.assertIsNone(res.record["battery_voltage"])
        self.assertTrue(res.quality_flags & (1 << 2) and res.quality_flags & (1 << 5))
        self.assertIn(("barometric_pressure", "out_of_range", 250000.0), res.issues)

    def test_unparseable_and_enum(self):
        res = self.schema.validate({**GOOD, "temperature": "hot", "flight_state": "HOVER", "gps_fix": "3.5"})
        kinds = {f: k for f, k, _ in res.issues}
        self.assertEqual(kinds["temperature"], "unparseable")
        self.assertEqual(kinds["flight_state"], "invalid_enum")
        self.assertEqual(kinds["gps_fix"], "unparseable")

    def test_required_fields(self):
        for missing in ("seq", "timestamp", "data_source"):
            with self.subTest(missing=missing):
                rec = {k: v for k, v in GOOD.items() if k != missing}
                self.assertTrue(self.schema.validate(rec).rejected)
        self.assertTrue(self.schema.validate({**GOOD, "data_source": "REAL"}).rejected)

    def test_unknown_field_reported(self):
        res = self.schema.validate({**GOOD, "mystery": 1})
        self.assertIn(("mystery", "unknown_field", 1), res.issues)

    def test_csv_strings_parse(self):
        res = self.schema.validate({k: str(v) for k, v in GOOD.items()})
        self.assertFalse(res.rejected)
        self.assertEqual(res.record["seq"], 1)
        self.assertAlmostEqual(res.record["battery_voltage"], 4.1)


class SensorCatalogue(unittest.TestCase):
    def test_every_sensor_field_is_in_the_schema_and_catalogued(self):
        schema = load_schema()
        catalogued = {f for s in SENSOR_SPECS for f in s.fields}
        for f in catalogued:
            self.assertIn(f, schema.by_name)
        sensor_fields = {f.name for f in schema.fields if f.quality_bit is not None} | {"separation_detected"}
        self.assertTrue(sensor_fields <= catalogued, sensor_fields - catalogued)

    def test_no_component_is_claimed_selected(self):
        for s in SENSOR_SPECS:
            with self.subTest(sensor=s.key):
                self.assertEqual(s.component, COMPONENT_TO_BE_SELECTED)
                self.assertGreater(s.sampling_rate_hz, 0)
                self.assertTrue(s.measurement and s.required_range and s.unit and s.interface and s.purpose)
                self.assertGreaterEqual(len(s.failure_considerations), 2)


class SimulatedSensors(unittest.TestCase):
    def setUp(self):
        self.p = SyntheticFlightProfile()

    def test_imu_reads_plus_one_g_on_the_pad(self):
        imu = SimulatedIMU(self.p, seed=1)
        z = [imu.sample(int(t * 1e4)).values["imu_accel_z"] for t in range(100)]
        self.assertAlmostEqual(sum(z) / len(z), G0, delta=0.05)

    def test_imu_clips_at_full_scale(self):
        imu = SimulatedIMU(self.p, seed=1, full_scale_g=2.0)
        t_boost = int((self.p.t_liftoff + 0.5) * 1e6)
        self.assertLessEqual(imu.sample(t_boost).values["imu_accel_z"], 2.0 * G0)

    def test_barometer_matches_isa_and_decreases_with_height(self):
        baro = SimulatedBarometer(self.p, seed=1, pressure_sigma=0.0)
        self.assertAlmostEqual(baro.sample(0).values["barometric_pressure"], P0, places=6)
        self.assertLess(isa_pressure(300.0), isa_pressure(0.0))

    def test_gnss_has_no_fix_before_time_to_fix(self):
        g = SimulatedGNSS(self.p, seed=1, time_to_fix_s=2.0)
        v = g.sample(0).values
        self.assertEqual(v["gps_fix"], 0)
        self.assertIsNone(v["latitude"])
        self.assertEqual(g.sample(3_000_000).values["gps_fix"], 3)

    def test_dropout_fault(self):
        imu = SimulatedIMU(self.p, seed=3, faults=FaultConfig(dropout_prob=0.3))
        got = [imu.sample(i * 10_000) for i in range(2000)]
        frac = sum(g is None for g in got) / len(got)
        self.assertAlmostEqual(frac, 0.3, delta=0.05)

    def test_nan_fault_produces_nan(self):
        imu = SimulatedIMU(self.p, seed=3, faults=FaultConfig(nan_prob=1.0))
        vals = imu.sample(0).values
        self.assertTrue(any(isinstance(v, float) and math.isnan(v) for v in vals.values()))

    def test_scheduling_has_no_drift(self):
        baro = SimulatedBarometer(self.p, seed=1)
        n = sum(1 for t in range(0, 10_000_000, 10_000) if baro.due(t) and baro.sample(t))
        self.assertEqual(n, 500)                            # 50 Hz for 10 s

    def test_hardware_placeholder_refuses_to_read(self):
        s = HardwareSensorPlaceholder("imu", 100)
        self.assertFalse(s.simulated)
        with self.assertRaises(HardwareSensorNotSelected):
            s.sample(0)


if __name__ == "__main__":
    unittest.main()
