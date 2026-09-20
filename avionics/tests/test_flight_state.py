"""Flight-state classification and the vertical-state estimator."""
import unittest

from avionics.firmware.flight_state.classifier import STATE_ORDER, FlightState, StateClassifier, classify_series
from avionics.firmware.flight_state.estimator import VerticalKalmanFilter, pressure_to_altitude
from avionics.firmware.sensor_interfaces.simulated import (G0, FaultConfig, SyntheticFlightProfile, TrajectoryReplayProfile,
                                                           isa_pressure)
from avionics.firmware.simulate_flight import TRAJECTORY

from .helpers import TOL, event_times, fly, nominal_flight


class NominalFlights(unittest.TestCase):
    def check(self, r):
        ev, p = event_times(r["events"]), r["profile"]
        self.assertEqual(list(ev), ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
        apo = next(e for e in r["events"] if e.name == "APOGEE")
        truth_apogee_h = max(p.h)
        self.assertAlmostEqual(ev["LIFTOFF"], p.t_liftoff, delta=TOL["liftoff"])
        self.assertAlmostEqual(apo.detail["apogee_time_s"], p.t_apogee, delta=TOL["apogee_t"])
        self.assertAlmostEqual(apo.detail["apogee_altitude_m"], truth_apogee_h, delta=TOL["apogee_h"])
        self.assertAlmostEqual(ev["LANDING"], p.t_landing, delta=TOL["landing"])
        states = [STATE_ORDER.index(FlightState(x["flight_state"])) for x in r["records"]]
        self.assertEqual(states, sorted(states))                     # forward only
        self.assertEqual(set(states), set(range(5)))
        return ev, p

    def test_synthetic_profile(self):
        ev, p = self.check(nominal_flight())
        burn_end = p.t_liftoff + 1.5
        self.assertAlmostEqual(ev["BURNOUT"], burn_end, delta=TOL["burnout"])

    def test_replay_of_existing_simulation_trajectory(self):
        p = TrajectoryReplayProfile.from_csv(TRAJECTORY)
        ev, _ = self.check(fly(profile=p, seed=2))
        burnout = next(t for t, ph in zip(p.t, p.phase) if ph == "coast")
        self.assertAlmostEqual(ev["BURNOUT"], burnout, delta=TOL["burnout"])

    def test_estimator_velocity_tracks_truth_during_ascent(self):
        # Liftoff to apogee. After apogee the synthetic profile jumps instantly to the descent rate (an unphysical step
        # no filter can follow), so that instant is excluded.
        r = nominal_flight()
        p = r["profile"]
        errs = [abs(x["vertical_velocity"] - p.state(x["timestamp"])["vz_mps"]) for x in r["records"]
                if p.t_liftoff <= x["timestamp"] <= p.t_apogee]
        self.assertLess(max(errs), 3.0)
        self.assertLess(sum(errs) / len(errs), 1.0)


class Robustness(unittest.TestCase):
    def test_pad_knock_is_not_a_launch(self):
        clf = StateClassifier()
        t = 0.0
        for i in range(500):
            t = i * 0.01
            knock = 3.0 * G0 if 200 <= i < 203 else G0                 # 30 ms, 3 g handling knock
            clf.update(t, knock, 0.0, 0.0)
        self.assertEqual(clf.state, FlightState.PRELAUNCH)
        self.assertEqual(clf.events, [])

    def test_barometric_backup_without_accelerometer(self):
        r = fly(faults=dict(imu=FaultConfig(dropout_prob=1.0)), seed=6)
        ev = r["events"]
        names = [e.name for e in ev]
        self.assertEqual(ev[0].name, "LIFTOFF")
        self.assertEqual(ev[0].detail["detected_by"], "barometer")
        self.assertIn("BURNOUT_NOT_DETECTED", names)
        self.assertIn("APOGEE", names)
        self.assertIn("LANDING", names)
        apo = next(e for e in ev if e.name == "APOGEE")
        self.assertAlmostEqual(apo.detail["apogee_time_s"], r["profile"].t_apogee, delta=0.6)

    def test_offline_classification_of_series(self):
        p = SyntheticFlightProfile()
        ts = [i * 0.02 for i in range(int(p.duration / 0.02))]
        st = [p.state(t) for t in ts]
        states, events = classify_series(ts, [s["az_mps2"] + G0 if s["phase"] in ("pad", "ascent", "coast") else G0 * 0.5
                                              for s in st], [s["altitude_m"] for s in st], [s["vz_mps"] for s in st])
        self.assertEqual([e.name for e in events], ["LIFTOFF", "BURNOUT", "APOGEE", "LANDING"])
        self.assertEqual(states[-1], "LANDED")


class Estimator(unittest.TestCase):
    def test_isa_altitude_round_trip(self):
        for h in (0.0, 100.0, 328.0, 1000.0):
            self.assertAlmostEqual(pressure_to_altitude(isa_pressure(h), isa_pressure(0.0)), h, delta=0.05)

    def test_kalman_converges_on_constant_velocity(self):
        kf = VerticalKalmanFilter()
        for i in range(500):
            t = i * 0.02
            kf.predict(0.02, 0.0)
            kf.update(10.0 * t)
        self.assertAlmostEqual(kf.v, 10.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
