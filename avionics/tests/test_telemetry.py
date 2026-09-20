"""Telemetry packet formatting, links and the ground-station receiver."""
import unittest

from avionics.firmware.crc import crc16
from avionics.firmware.telemetry.link import (LINK_HARDWARE, LINK_SIMULATED, HardwareTelemetryLink, SimulatedTelemetryLink,
                                              TelemetryHardwareUnavailable)
from avionics.firmware.telemetry.packet import PACKET_SIZE, PacketError, TelemetryFrame, decode, encode
from avionics.ground_station.receiver import GroundStationReceiver

from .helpers import nominal_flight

FULL = TelemetryFrame(seq=42, time_s=12.345, simulated=True, flight_state="COAST", altitude_m=210.37,
                      vertical_velocity_mps=-3.21, accel_axial_mps2=-12.34, accel_magnitude_mps2=12.5, temperature_c=18.76,
                      latitude_deg=0.0012345, longitude_deg=-0.0006789, gps_altitude_m=215.4, gps_fix=3, gps_satellites=9,
                      battery_voltage_v=4.056, separation=True)


class PacketFormat(unittest.TestCase):
    def test_crc_check_value(self):
        self.assertEqual(crc16(b"123456789"), 0x29B1)

    def test_size_and_round_trip(self):
        raw = encode(FULL)
        self.assertEqual(len(raw), PACKET_SIZE)
        self.assertEqual(PACKET_SIZE, 41)
        d = decode(raw)
        self.assertEqual((d.seq, d.flight_state, d.gps_fix, d.gps_satellites, d.simulated, d.separation),
                         (42, "COAST", 3, 9, True, True))
        for name, q in (("time_s", 0.001), ("altitude_m", 0.05), ("vertical_velocity_mps", 0.005), ("accel_axial_mps2", 0.005),
                        ("temperature_c", 0.005), ("latitude_deg", 5e-8), ("longitude_deg", 5e-8), ("gps_altitude_m", 0.05),
                        ("battery_voltage_v", 0.0005)):
            with self.subTest(field=name):
                self.assertAlmostEqual(getattr(d, name), getattr(FULL, name), delta=q + 1e-12)

    def test_missing_values_survive_as_none(self):
        d = decode(encode(TelemetryFrame(seq=1, time_s=0.0, simulated=True)))
        for name in ("altitude_m", "vertical_velocity_mps", "temperature_c", "latitude_deg", "battery_voltage_v", "gps_fix",
                     "flight_state"):
            self.assertIsNone(getattr(d, name), name)

    def test_saturation_not_wraparound(self):
        d = decode(encode(TelemetryFrame(seq=1, time_s=0.0, simulated=True, accel_axial_mps2=1e6, vertical_velocity_mps=-1e6)))
        self.assertAlmostEqual(d.accel_axial_mps2, 327.67)
        self.assertAlmostEqual(d.vertical_velocity_mps, -327.67)

    def test_corruption_is_detected(self):
        raw = bytearray(encode(FULL))
        for i in (0, 5, 20, 40):
            bad = bytearray(raw)
            bad[i] ^= 0x10
            with self.subTest(byte=i), self.assertRaises(PacketError):
                decode(bytes(bad))
        with self.assertRaises(PacketError):
            decode(bytes(raw[:-1]))


class Links(unittest.TestCase):
    def test_simulated_link_loss_and_errors_are_seeded(self):
        a, b = SimulatedTelemetryLink(0.1, 0.1, seed=3), SimulatedTelemetryLink(0.1, 0.1, seed=3)
        for i in range(500):
            p = encode(TelemetryFrame(seq=i, time_s=i * 0.2, simulated=True))
            a.send(p, i * 0.2)
            b.send(p, i * 0.2)
        self.assertEqual(a.receive(), b.receive())
        self.assertEqual(a.kind, LINK_SIMULATED)
        self.assertTrue(30 < a.lost < 75 and 25 < a.corrupted < 80)

    def test_hardware_link_refuses_without_radio(self):
        with self.assertRaises(TelemetryHardwareUnavailable):
            HardwareTelemetryLink()

    def test_hardware_link_interface_with_loopback_driver(self):
        class Loopback:
            def __init__(self):
                self.buf = []

            def transmit(self, data):
                self.buf.append(data)

            def receive(self):
                return self.buf.pop(0) if self.buf else None
        link = HardwareTelemetryLink(Loopback())
        self.assertEqual(link.kind, LINK_HARDWARE)
        link.send(encode(FULL), 0.0)
        self.assertEqual(decode(link.receive()[0][1]).seq, 42)

    def test_flight_computer_marks_packets_simulated_at_5_hz(self):
        r = nominal_flight()
        fc = r["fc"]
        self.assertTrue(fc.simulated)
        dur = fc.tick * fc.base_us / 1e6
        self.assertAlmostEqual(fc.packets_sent, dur * 5, delta=2)


class Receiver(unittest.TestCase):
    def test_statistics(self):
        rx = GroundStationReceiver()
        pk = lambda s: encode(TelemetryFrame(seq=s, time_s=s * 0.2, simulated=True))  # noqa: E731
        for s in (0, 1, 2, 5, 5, 6):                     # 3 and 4 missing, 5 duplicated
            rx.ingest(pk(s))
        bad = bytearray(pk(7))
        bad[12] ^= 1
        rx.ingest(bytes(bad))
        rx.ingest(pk(8))
        st = rx.stats()
        self.assertEqual((st["decoded"], st["lost"], st["duplicates"], st["rejected"]), (6, 3, 1, 1))
        self.assertTrue(rx.simulated)

    def test_sequence_wrap_is_not_loss(self):
        rx = GroundStationReceiver()
        for s in (65534, 65535, 0, 1):
            rx.ingest(encode(TelemetryFrame(seq=s, time_s=0.0, simulated=True)))
        self.assertEqual(rx.stats()["lost"], 0)

    def test_end_to_end_through_lossy_link(self):
        from .helpers import fly
        r = fly(loss=0.05, bit_errors=0.05, seed=9)
        rx = GroundStationReceiver()
        for t, p in r["link"].receive():
            rx.ingest(p, t)
        st = rx.stats()
        self.assertEqual(st["rejected"], r["link"].corrupted)
        self.assertEqual(st["decoded"], r["link"].sent - r["link"].lost - r["link"].corrupted)
        self.assertEqual(st["lost"], r["link"].lost + r["link"].corrupted)
        self.assertEqual([f.flight_state for _, f in rx.frames][-1], "LANDED")


if __name__ == "__main__":
    unittest.main()
