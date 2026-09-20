"""SIMULATED sensors, so the whole data chain can be developed and tested without hardware.

A *truth profile* gives the vehicle's vertical state against time. Simulated sensors turn it into readings with
seeded noise and optional injected faults. Everything here is synthetic and is labelled SIMULATED wherever it is
logged or transmitted. Noise levels, drift, battery discharge and parachute swing are illustrative assumptions,
not properties of any real component.

Truth profiles:
  * `TrajectoryReplayProfile`: replays `simulation/results/trajectory_baseline.csv` from the existing 1-DOF
    simulation. That trajectory uses the PLACEHOLDER propulsion input, so it is not representative of a real motor.
  * `SyntheticFlightProfile`: a small analytic boost / coast / descent profile for unit tests.
"""
import bisect
import csv
import math
import random

from .base import Sensor

G0 = 9.80665                      # standard gravity, m/s²
P0 = 101325.0                     # ISA sea-level pressure, Pa
T0 = 288.15                       # ISA sea-level temperature, K
LAPSE = 0.0065                    # ISA troposphere lapse rate, K/m
ISA_EXP = 5.25588                 # g·M / (R·L)
M_PER_DEG_LAT = 111_320.0         # spherical approximation, adequate for a few hundred metres of drift

PHASES = ("pad", "ascent", "coast", "descent", "landed")


def isa_pressure(h_msl_m, temp_offset_k=0.0):
    """ISA pressure (Pa) at geometric altitude h (troposphere), with an optional temperature offset."""
    return P0 * (1.0 - LAPSE * h_msl_m / (T0 + temp_offset_k)) ** ISA_EXP


class GaussianNoise:
    """Seeded normal noise from random.random() (Box–Muller), which Python documents as reproducible across versions."""

    def __init__(self, seed):
        self._r = random.Random(seed)
        self._spare = None

    def uniform(self):
        return self._r.random()

    def __call__(self, sigma):
        if sigma == 0:
            return 0.0
        if self._spare is not None:
            z, self._spare = self._spare, None
            return z * sigma
        u1 = max(self._r.random(), 1e-300)
        u2 = self._r.random()
        rad = math.sqrt(-2.0 * math.log(u1))
        self._spare = rad * math.sin(2 * math.pi * u2)
        return rad * math.cos(2 * math.pi * u2) * sigma


# --------------------------------------------------------------------------------------------------- truth profiles
class _TableProfile:
    """Piecewise-linear table of (t, altitude AGL, vertical velocity, kinematic vertical acceleration, phase)."""

    def __init__(self, t, h, v, a, phase, t_liftoff, t_apogee, t_landing, label):
        self.t, self.h, self.v, self.a, self.phase = t, h, v, a, phase
        self.t_liftoff, self.t_apogee, self.t_landing = t_liftoff, t_apogee, t_landing
        self.label = label
        self.duration = t[-1]

    def state(self, t_s):
        """Return dict(altitude_m, vz_mps, az_mps2, phase) at time t_s (held constant outside the table)."""
        if t_s <= self.t[0]:
            i, f = 0, 0.0
        elif t_s >= self.t[-1]:
            i, f = len(self.t) - 2, 1.0
        else:
            i = bisect.bisect_right(self.t, t_s) - 1
            f = (t_s - self.t[i]) / (self.t[i + 1] - self.t[i])
        lerp = lambda arr: arr[i] + (arr[i + 1] - arr[i]) * f  # noqa: E731
        if t_s < self.t_liftoff:
            phase = "pad"
        elif t_s >= self.t_landing:
            phase = "landed"
        else:
            phase = self.phase[i + 1] if f > 0.5 else self.phase[i]
        return dict(altitude_m=max(lerp(self.h), 0.0), vz_mps=lerp(self.v), az_mps2=lerp(self.a), phase=phase)


class TrajectoryReplayProfile(_TableProfile):
    """Replay of the existing simulation trajectory (PLACEHOLDER propulsion) after `pad_time_s` on the pad."""

    @classmethod
    def from_csv(cls, path, pad_time_s=10.0, post_landing_s=8.0):
        t, h, v, a, ph = [0.0], [0.0], [0.0], [0.0], ["pad"]
        mapping = {"pad": "pad", "rail": "ascent", "powered": "ascent", "coast": "coast", "descent": "descent"}
        t_apogee = t_land = None
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ts = float(row["t_s"]) + pad_time_s
                if ts <= t[-1]:
                    continue
                p = mapping.get(row["phase"], row["phase"])
                if p == "descent" and t_apogee is None:
                    t_apogee = ts
                t.append(ts); h.append(float(row["altitude_m"])); v.append(float(row["velocity_mps"]))
                a.append(float(row["accel_mps2"])); ph.append(p)
        t_land = t[-1]
        t.append(t_land + post_landing_s); h.append(0.0); v.append(0.0); a.append(0.0); ph.append("landed")
        return cls(t, h, v, a, ph, t_liftoff=pad_time_s, t_apogee=t_apogee, t_landing=t_land,
                   label="replay of simulation/results/trajectory_baseline.csv (PLACEHOLDER propulsion input)")


class SyntheticFlightProfile(_TableProfile):
    """Analytic profile for tests: constant-acceleration boost, quadratic-drag coast, constant-rate descent.
    All numbers are synthetic test values chosen to resemble the placeholder simulation in scale only."""

    def __init__(self, pad_time_s=5.0, boost_accel=55.0, burn_time_s=1.5, drag_k=0.0012, descent_rate=5.0,
                 post_landing_s=6.0, dt=0.002):
        t, h, v, a, ph = [0.0], [0.0], [0.0], [0.0], ["pad"]
        tt, hh, vv = pad_time_s, 0.0, 0.0
        t.append(tt); h.append(0.0); v.append(0.0); a.append(0.0); ph.append("pad")
        while True:                                             # boost + coast, explicit integration
            boost = tt - pad_time_s < burn_time_s
            acc = (boost_accel if boost else 0.0) - G0 - drag_k * vv * abs(vv) * (1.0 if boost else 8.0)
            vv_new = vv + acc * dt
            if not boost and vv_new <= 0.0:
                break
            hh += vv * dt + 0.5 * acc * dt * dt
            vv = vv_new
            tt += dt
            t.append(tt); h.append(hh); v.append(vv); a.append(acc); ph.append("ascent" if boost else "coast")
        t_apogee = tt
        t_desc = hh / descent_rate
        n = max(int(t_desc / 0.05), 1)
        for k in range(1, n + 1):
            t.append(t_apogee + k * t_desc / n); h.append(hh * (1 - k / n)); v.append(-descent_rate); a.append(0.0)
            ph.append("descent")
        t_land = t[-1]
        t.append(t_land + post_landing_s); h.append(0.0); v.append(0.0); a.append(0.0); ph.append("landed")
        super().__init__(t, h, v, a, ph, t_liftoff=pad_time_s, t_apogee=t_apogee, t_landing=t_land,
                         label="synthetic analytic test profile")


# --------------------------------------------------------------------------------------------------- fault injection
class FaultConfig:
    """Injected faults for testing (all off by default).
    dropout_prob: probability a sample is missing; nan_prob: probability one value becomes NaN;
    spike_prob / spike_scale: probability of a gross outlier; stuck_after_s: sensor repeats its last sample."""

    def __init__(self, dropout_prob=0.0, nan_prob=0.0, spike_prob=0.0, spike_scale=50.0, stuck_after_s=None):
        self.dropout_prob, self.nan_prob = dropout_prob, nan_prob
        self.spike_prob, self.spike_scale, self.stuck_after_s = spike_prob, spike_scale, stuck_after_s


class SimulatedSensor(Sensor):
    simulated = True

    def __init__(self, name, rate_hz, profile, seed, faults=None):
        super().__init__(name, rate_hz)
        self.profile = profile
        self.noise = GaussianNoise(seed)
        self.faults = faults or FaultConfig()
        self._last = None

    def _read(self, t_us):
        f = self.faults
        t_s = t_us / 1e6
        if f.stuck_after_s is not None and t_s >= f.stuck_after_s and self._last is not None:
            return dict(self._last)
        if f.dropout_prob and self.noise.uniform() < f.dropout_prob:
            return None
        vals = self._measure(t_s)
        if f.nan_prob and self.noise.uniform() < f.nan_prob:
            k = sorted(vals)[int(self.noise.uniform() * len(vals)) % len(vals)]
            vals[k] = float("nan")
        if f.spike_prob and self.noise.uniform() < f.spike_prob:
            k = sorted(vals)[int(self.noise.uniform() * len(vals)) % len(vals)]
            if isinstance(vals[k], float):
                vals[k] = vals[k] * f.spike_scale + f.spike_scale
        self._last = dict(vals)
        return vals

    def _measure(self, t_s):
        raise NotImplementedError


class SimulatedIMU(SimulatedSensor):
    """Specific force = kinematic acceleration + gravity along +z while the vehicle is vertical (pad, ascent, coast).
    Under the parachute the bay hangs at a synthetic swinging tilt, so +z no longer points up."""

    def __init__(self, profile, seed=11, rate_hz=100.0, accel_sigma=0.05, gyro_sigma=0.1, full_scale_g=16.0,
                 hang_tilt_deg=60.0, faults=None):
        super().__init__("imu", rate_hz, profile, seed, faults)
        self.accel_sigma, self.gyro_sigma = accel_sigma, gyro_sigma
        self.fs = full_scale_g * G0
        self.hang_tilt = math.radians(hang_tilt_deg)

    def _measure(self, t_s):
        s = self.profile.state(t_s)
        n = self.noise
        ascent = s["phase"] == "ascent"
        if s["phase"] == "descent":
            swing = self.hang_tilt + math.radians(15.0) * math.sin(2 * math.pi * 0.4 * t_s)
            fz, fx = G0 * math.cos(swing), G0 * math.sin(swing)
            gz = 25.0 * math.sin(2 * math.pi * 0.4 * t_s)
        elif s["phase"] == "landed":
            fz, fx, gz = 0.0, G0, 0.0                               # lying on its side
        else:
            fz, fx = s["az_mps2"] + G0, 0.0
            gz = 0.0
        vib = 0.4 if ascent else 0.0                                # synthetic boost vibration
        clip = lambda x: max(-self.fs, min(self.fs, x))  # noqa: E731
        return dict(imu_accel_x=clip(fx + n(self.accel_sigma + vib)), imu_accel_y=clip(n(self.accel_sigma + vib)),
                    imu_accel_z=clip(fz + n(self.accel_sigma + vib)),
                    gyro_x=n(self.gyro_sigma), gyro_y=n(self.gyro_sigma), gyro_z=gz + n(self.gyro_sigma))


class SimulatedBarometer(SimulatedSensor):
    def __init__(self, profile, seed=12, rate_hz=50.0, site_elevation_m=0.0, temp_offset_k=0.0, pressure_sigma=3.0,
                 faults=None):
        super().__init__("baro", rate_hz, profile, seed, faults)
        self.site, self.dT, self.sigma = site_elevation_m, temp_offset_k, pressure_sigma

    def _measure(self, t_s):
        h = self.profile.state(t_s)["altitude_m"]
        return dict(barometric_pressure=isa_pressure(self.site + h, self.dT) + self.noise(self.sigma))


class SimulatedGNSS(SimulatedSensor):
    """Position from a fictitious origin (0°, 0°) plus a synthetic horizontal drift after liftoff. The 1-DOF simulation
    has no horizontal motion; the drift only exists so the ground track can be exercised."""

    def __init__(self, profile, seed=13, rate_hz=1.0, origin=(0.0, 0.0), site_elevation_m=0.0,
                 drift_mps=(2.0, 1.0), pos_sigma_m=1.5, alt_sigma_m=3.0, time_to_fix_s=2.0, satellites=9, faults=None):
        super().__init__("gnss", rate_hz, profile, seed, faults)
        self.lat0, self.lon0 = origin
        self.site = site_elevation_m
        self.drift = drift_mps                     # (east, north) m/s
        self.pos_sigma, self.alt_sigma = pos_sigma_m, alt_sigma_m
        self.ttf, self.sats = time_to_fix_s, satellites

    def _measure(self, t_s):
        if t_s < self.ttf:
            return dict(latitude=None, longitude=None, gps_altitude=None, gps_fix=0, gps_satellites=3)
        p = self.profile
        s = p.state(t_s)
        tf = min(max(t_s - p.t_liftoff, 0.0), p.t_landing - p.t_liftoff)
        east = self.drift[0] * tf + self.noise(self.pos_sigma)
        north = self.drift[1] * tf + self.noise(self.pos_sigma)
        lat = self.lat0 + north / M_PER_DEG_LAT
        lon = self.lon0 + east / (M_PER_DEG_LAT * math.cos(math.radians(self.lat0)))
        return dict(latitude=lat, longitude=lon, gps_altitude=self.site + s["altitude_m"] + self.noise(self.alt_sigma),
                    gps_fix=3, gps_satellites=self.sats)


class SimulatedTemperature(SimulatedSensor):
    """First-order lag toward the ISA air temperature at altitude, starting slightly warm (synthetic)."""

    def __init__(self, profile, seed=14, rate_hz=1.0, start_c=24.0, tau_s=120.0, sigma=0.05, temp_offset_k=0.0,
                 faults=None):
        super().__init__("temperature", rate_hz, profile, seed, faults)
        self.t_c, self.tau, self.sigma, self.dT = start_c, tau_s, sigma, temp_offset_k
        self._t_prev = None

    def _measure(self, t_s):
        air = T0 + self.dT - 273.15 - LAPSE * self.profile.state(t_s)["altitude_m"]
        if self._t_prev is not None:
            dt = t_s - self._t_prev
            self.t_c += (air - self.t_c) * (1 - math.exp(-dt / self.tau))
        self._t_prev = t_s
        return dict(temperature=self.t_c + self.noise(self.sigma))


class SimulatedBatteryMonitor(SimulatedSensor):
    """Linear synthetic discharge with measurement noise (not a model of any cell)."""

    def __init__(self, profile, seed=15, rate_hz=1.0, start_v=4.10, slope_v_per_s=-0.0008, sigma=0.004, faults=None):
        super().__init__("battery", rate_hz, profile, seed, faults)
        self.v0, self.slope, self.sigma = start_v, slope_v_per_s, sigma

    def _measure(self, t_s):
        return dict(battery_voltage=self.v0 + self.slope * t_s + self.noise(self.sigma))


class SimulatedSeparationSense(SimulatedSensor):
    """Breakwire opens `delay_s` after the profile's apogee (the simulation assumes deployment at apogee)."""

    def __init__(self, profile, seed=16, rate_hz=50.0, delay_s=0.3, faults=None):
        super().__init__("separation", rate_hz, profile, seed, faults)
        self.delay = delay_s

    def _measure(self, t_s):
        ta = self.profile.t_apogee
        return dict(separation_detected=int(ta is not None and t_s >= ta + self.delay))


def simulated_sensor_suite(profile, seed=0, faults=None, site_elevation_m=0.0, temp_offset_k=0.0):
    """The standard set of simulated sensors used by the example dataset and the ground-station demo.
    `faults` may map a sensor name to a FaultConfig."""
    f = faults or {}
    return [SimulatedIMU(profile, seed=seed + 11, faults=f.get("imu")),
            SimulatedBarometer(profile, seed=seed + 12, site_elevation_m=site_elevation_m, temp_offset_k=temp_offset_k,
                               faults=f.get("baro")),
            SimulatedGNSS(profile, seed=seed + 13, site_elevation_m=site_elevation_m, faults=f.get("gnss")),
            SimulatedTemperature(profile, seed=seed + 14, temp_offset_k=temp_offset_k, faults=f.get("temperature")),
            SimulatedBatteryMonitor(profile, seed=seed + 15, faults=f.get("battery")),
            SimulatedSeparationSense(profile, seed=seed + 16, faults=f.get("separation"))]
