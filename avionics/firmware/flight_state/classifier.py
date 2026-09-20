"""Flight-state classifier: PRELAUNCH -> ASCENT -> COAST -> DESCENT -> LANDED (forward only).

DATA PROCESSING ONLY. The state is written to the log and telemetry and used by post-flight analysis. It drives no
output of any kind, and must never be connected to ignition, pyrotechnic, energetic or deployment hardware.

Transition rules (thresholds in ClassifierConfig; all are assumptions to be re-checked with the certified motor's data
and with bench / flight data):

  PRELAUNCH -> ASCENT   axial specific force > launch_accel_g for launch_confirm_s  (primary, accelerometer)
                        OR altitude > launch_alt_m with vertical velocity > launch_vz_mps for launch_confirm_s
                        (backup, barometer, in case the accelerometer fails)
                        A short knock on the pad is shorter than launch_confirm_s and is ignored.
  ASCENT -> COAST       axial specific force < burnout_accel_g for burnout_confirm_s, at least min_burn_s after
                        liftoff (thrust gone, drag decelerating the vehicle).
  COAST -> DESCENT      apogee: estimated vertical velocity < -apogee_vz_mps for apogee_confirm_s, OR altitude more
                        than apogee_drop_m below the maximum; never earlier than min_apogee_s after liftoff.
                        If burnout was never detected (e.g. accelerometer failure) ASCENT goes straight to DESCENT on
                        the same apogee rule, and the missing burnout event is recorded.
  DESCENT -> LANDED     |vertical velocity| < landed_vz_mps and the altitude stays within landed_band_m for
                        landed_window_s, at least min_descent_s after apogee.
"""
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from ..sensor_interfaces.simulated import G0


class FlightState(str, Enum):
    PRELAUNCH = "PRELAUNCH"
    ASCENT = "ASCENT"
    COAST = "COAST"
    DESCENT = "DESCENT"
    LANDED = "LANDED"


STATE_ORDER = [FlightState.PRELAUNCH, FlightState.ASCENT, FlightState.COAST, FlightState.DESCENT, FlightState.LANDED]


@dataclass
class ClassifierConfig:
    launch_accel_g: float = 2.0         # placeholder average T/W is 6.5, so thrust gives a clear step
    launch_confirm_s: float = 0.05
    launch_alt_m: float = 15.0
    launch_vz_mps: float = 5.0
    burnout_accel_g: float = 0.5
    burnout_confirm_s: float = 0.05
    min_burn_s: float = 0.2
    apogee_vz_mps: float = 1.0
    apogee_confirm_s: float = 0.25
    apogee_drop_m: float = 5.0
    min_apogee_s: float = 2.0
    landed_vz_mps: float = 1.0
    landed_band_m: float = 2.0
    landed_window_s: float = 3.0
    min_descent_s: float = 1.0


@dataclass
class FlightEvent:
    name: str
    time_s: float
    detail: dict = field(default_factory=dict)


class _Persist:
    """True once `cond` has held continuously for `hold_s`; remembers when it started."""

    def __init__(self, hold_s):
        self.hold, self.since = hold_s, None

    def __call__(self, t, cond):
        if not cond:
            self.since = None
            return False
        if self.since is None:
            self.since = t
        return t - self.since >= self.hold - 1e-9


class StateClassifier:
    def __init__(self, config=None):
        self.cfg = config or ClassifierConfig()
        c = self.cfg
        self.state = FlightState.PRELAUNCH
        self.events = []
        self.t_liftoff = self.t_apogee = None
        self.max_alt, self.t_max_alt = float("-inf"), None
        self._launch_acc, self._launch_baro = _Persist(c.launch_confirm_s), _Persist(c.launch_confirm_s)
        self._burnout = _Persist(c.burnout_confirm_s)
        self._apogee_v = _Persist(c.apogee_confirm_s)
        self._hist = deque()

    def _go(self, state, t, name, **detail):
        self.state = state
        self.events.append(FlightEvent(name, t, detail))

    def update(self, t_s, accel_axial_mps2, altitude_m, vz_mps):
        """Feed one processed sample. accel may be None (no fresh IMU data); altitude/vz are estimator outputs."""
        c = self.cfg
        acc_g = None if accel_axial_mps2 is None else accel_axial_mps2 / G0
        if self.state != FlightState.PRELAUNCH and altitude_m is not None and altitude_m > self.max_alt:
            self.max_alt, self.t_max_alt = altitude_m, t_s

        if self.state == FlightState.PRELAUNCH:
            by_acc = self._launch_acc(t_s, acc_g is not None and acc_g > c.launch_accel_g)
            by_baro = self._launch_baro(t_s, altitude_m is not None and vz_mps is not None
                                        and altitude_m > c.launch_alt_m and vz_mps > c.launch_vz_mps)
            if by_acc or by_baro:
                src = self._launch_acc if by_acc else self._launch_baro
                self.t_liftoff = src.since
                self.max_alt, self.t_max_alt = (altitude_m if altitude_m is not None else 0.0), t_s
                self._go(FlightState.ASCENT, src.since, "LIFTOFF", detected_by="accelerometer" if by_acc else "barometer")
            return self.state

        since_liftoff = t_s - self.t_liftoff
        if self.state == FlightState.ASCENT:
            if since_liftoff >= c.min_burn_s and self._burnout(t_s, acc_g is not None and acc_g < c.burnout_accel_g):
                self._go(FlightState.COAST, self._burnout.since, "BURNOUT")
            elif self._apogee(t_s, altitude_m, vz_mps, since_liftoff):
                self.events.append(FlightEvent("BURNOUT_NOT_DETECTED", t_s))
                self._enter_descent(t_s)
            return self.state

        if self.state == FlightState.COAST:
            if self._apogee(t_s, altitude_m, vz_mps, since_liftoff):
                self._enter_descent(t_s)
            return self.state

        if self.state == FlightState.DESCENT:
            self._hist.append((t_s, altitude_m))
            while self._hist and t_s - self._hist[0][0] > c.landed_window_s:
                self._hist.popleft()
            alts = [a for _, a in self._hist if a is not None]
            span_ok = (self._hist and t_s - self._hist[0][0] >= c.landed_window_s - 0.05 and alts
                       and max(alts) - min(alts) <= c.landed_band_m)
            if (t_s - self.t_apogee >= c.min_descent_s and vz_mps is not None and abs(vz_mps) < c.landed_vz_mps
                    and span_ok):
                self._go(FlightState.LANDED, self._hist[0][0], "LANDING")
        return self.state

    def _apogee(self, t_s, altitude_m, vz_mps, since_liftoff):
        c = self.cfg
        falling = self._apogee_v(t_s, vz_mps is not None and vz_mps < -c.apogee_vz_mps)
        dropped = altitude_m is not None and altitude_m < self.max_alt - c.apogee_drop_m
        return since_liftoff >= c.min_apogee_s and (falling or dropped)

    def _enter_descent(self, t_s):
        self.t_apogee = self.t_max_alt
        self._go(FlightState.DESCENT, t_s, "APOGEE", apogee_time_s=self.t_max_alt, apogee_altitude_m=self.max_alt)


def classify_series(times, accel_axial, altitude, vz, config=None):
    """Offline classification of already-estimated series (for post-flight analysis). Returns (states, events)."""
    clf = StateClassifier(config)
    states = [clf.update(t, a, h, v).value for t, a, h, v in zip(times, accel_axial, altitude, vz)]
    return states, clf.events
