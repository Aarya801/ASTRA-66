"""Vertical-state estimator: a 2-state Kalman filter (altitude, vertical velocity).

Prediction uses the axial specific force minus gravity as vertical acceleration. That is only valid while the rocket
flies nose-up along the vertical (pad, ascent, coast): the same assumption as the 1-DOF simulation. After apogee the
bay hangs at an unknown angle under the parachute, so the filter switches to BAROMETER-ONLY mode (zero-acceleration
model with larger process noise). Tuning values are assumptions, to be re-tuned with bench and flight data.
"""
import math

from ..sensor_interfaces.simulated import G0

ISA_ALT_K = 44330.77          # ISA: h = K * (1 - (p/p_ref)^E), troposphere, standard temperature
ISA_ALT_E = 0.190263


def pressure_to_altitude(p_pa, p_ref_pa):
    """Barometric altitude (m) above the level where the pressure is p_ref (ISA temperature profile)."""
    return ISA_ALT_K * (1.0 - (p_pa / p_ref_pa) ** ISA_ALT_E)


class PadReference:
    """Ground reference pressure: running mean of barometer readings while on the pad; frozen at liftoff.

    It also freezes itself as soon as a reading lies more than `auto_freeze_alt_m` above the current reference.
    Otherwise, if liftoff is detected late (e.g. accelerometer failure, barometric backup), the running mean would
    follow the climbing vehicle and hide the very altitude gain that the backup detector is looking for."""

    def __init__(self, window=100, auto_freeze_alt_m=5.0):
        self.window, self.auto_freeze_alt_m = window, auto_freeze_alt_m
        self._buf = []
        self.frozen = False

    def add(self, p_pa):
        ref = self.value
        if ref is not None and not self.frozen and pressure_to_altitude(p_pa, ref) > self.auto_freeze_alt_m:
            self.frozen = True
        if not self.frozen:
            self._buf.append(p_pa)
            if len(self._buf) > self.window:
                self._buf.pop(0)

    @property
    def value(self):
        return sum(self._buf) / len(self._buf) if self._buf else None

    def freeze(self):
        self.frozen = True


class VerticalKalmanFilter:
    """State x = [h, v]; covariance P (2x2 as four floats)."""

    def __init__(self, accel_sigma=0.8, baro_only_accel_sigma=3.0, baro_sigma=0.5):
        self.sa, self.sa_baro, self.sb = accel_sigma, baro_only_accel_sigma, baro_sigma
        self.h = self.v = 0.0
        self.P = [25.0, 0.0, 0.0, 25.0]
        self.baro_only = False
        self.initialised = False

    def predict(self, dt, accel_vertical=None):
        """Advance by dt with the measured vertical acceleration (ignored in baro-only mode or when None)."""
        if dt <= 0:
            return
        a = 0.0 if (self.baro_only or accel_vertical is None) else accel_vertical
        sa = self.sa_baro if (self.baro_only or accel_vertical is None) else self.sa
        self.h += self.v * dt + 0.5 * a * dt * dt
        self.v += a * dt
        p00, p01, p10, p11 = self.P
        # P = F P F' + Q,  F = [[1, dt], [0, 1]],  Q = sa² [[dt⁴/4, dt³/2], [dt³/2, dt²]]
        q = sa * sa
        n00 = p00 + dt * (p10 + p01) + dt * dt * p11 + q * dt ** 4 / 4
        n01 = p01 + dt * p11 + q * dt ** 3 / 2
        n10 = p10 + dt * p11 + q * dt ** 3 / 2
        n11 = p11 + q * dt * dt
        self.P = [n00, n01, n10, n11]

    def update(self, h_meas):
        if not self.initialised:
            self.h, self.initialised = h_meas, True
            return
        p00, p01, p10, p11 = self.P
        s = p00 + self.sb * self.sb
        k0, k1 = p00 / s, p10 / s
        y = h_meas - self.h
        self.h += k0 * y
        self.v += k1 * y
        self.P = [(1 - k0) * p00, (1 - k0) * p01, p10 - k1 * p00, p11 - k1 * p01]


class VerticalStateEstimator:
    """Combines the pad reference, pressure-to-altitude conversion and the Kalman filter."""

    def __init__(self, kf=None, pad_window=100):
        self.kf = kf or VerticalKalmanFilter()
        self.pad = PadReference(pad_window)
        self._t_last = None

    def on_accel(self, t_s, accel_axial_mps2):
        dt = 0.0 if self._t_last is None else t_s - self._t_last
        self._t_last = t_s
        a = None if accel_axial_mps2 is None or not math.isfinite(accel_axial_mps2) else accel_axial_mps2 - G0
        self.kf.predict(dt, a)

    def on_pressure(self, t_s, p_pa):
        """Returns the barometric altitude above the pad (m), or None if the reading is unusable."""
        if p_pa is None or not math.isfinite(p_pa) or p_pa <= 0:
            return None
        if self._t_last is None:
            self._t_last = t_s
        elif t_s > self._t_last:                                 # no accelerometer sample since: widen uncertainty
            self.kf.predict(t_s - self._t_last, None)
            self._t_last = t_s
        self.pad.add(p_pa)
        h = pressure_to_altitude(p_pa, self.pad.value)
        self.kf.update(h)
        return h

    def set_baro_only(self, flag):
        self.kf.baro_only = bool(flag)

    def freeze_pad_reference(self):
        self.pad.freeze()

    @property
    def altitude(self):
        return self.kf.h

    @property
    def vertical_velocity(self):
        return self.kf.v
