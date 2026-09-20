"""Flight-computer main loop (hardware-independent reference implementation).

Each tick (base rate = IMU rate):
    SENSOR LAYER     poll every sensor that is due                  -> SensorSample
    VALIDATION       every value checked against the schema's plausibility limits; invalid values never reach
                     processing or telemetry (the raw value still goes to the logger, which flags it)
    PROCESSING       accelerometer -> Kalman predict; barometer -> altitude -> Kalman update; state classifier
    HEALTH           per sensor: OK while a fully valid sample arrived within 3 nominal sample periods
    DATA LOGGER      every log period: frame (fresh samples only)   -> validation -> CSV / JSONL sink
    TELEMETRY        every telemetry period: summary packet (latest valid values + health bits) -> link

Outputs are the log and the telemetry link, nothing else. There is no actuator interface: the flight state is a data
label, not a command. Recovery uses the certified motor's own ejection, prepared by a mentor.
"""
import math

from .data_source import SYNTHETIC, is_real_sensor_data
from .flight_state.classifier import FlightState, StateClassifier
from .flight_state.estimator import VerticalStateEstimator
from .logging.schema import load_schema
from .sensor_interfaces.catalog import SENSOR_SPECS
from .telemetry.packet import TelemetryFrame, encode

HEALTH_FLAGS = dict(imu="imu_ok", baro="baro_ok", gnss="gnss_ok", temperature="temp_ok", battery="battery_ok")
STALE_PERIODS = 3.0          # a sensor is stale after 3 nominal sample periods without a fully valid sample (assumption)


class FlightComputer:
    def __init__(self, sensors, logger=None, telemetry_link=None, base_rate_hz=100.0, log_rate_hz=50.0,
                 telemetry_rate_hz=5.0, estimator=None, classifier=None, nominal_rates_hz=None):
        self.sensors = list(sensors)
        self.simulated = any(getattr(s, "simulated", False) for s in self.sensors)
        if logger is not None and is_real_sensor_data(logger.data_source) == self.simulated:
            raise ValueError(f"logger data source {logger.mode} does not match the sensors "
                             f"({'simulated' if self.simulated else 'real'}): synthetic sensors may only write "
                             f"{SYNTHETIC} data, and real sensors may not be labelled {SYNTHETIC}")
        self.logger, self.link = logger, telemetry_link
        self.base_us = int(round(1e6 / base_rate_hz))
        self.log_every = max(1, int(round(base_rate_hz / log_rate_hz)))
        self.tlm_every = max(1, int(round(base_rate_hz / telemetry_rate_hz)))
        self.est = estimator or VerticalStateEstimator()
        self.clf = classifier or StateClassifier()
        self.schema = load_schema()
        rates = {s.key: s.sampling_rate_hz for s in SENSOR_SPECS}
        rates.update(nominal_rates_hz or {})
        self.stale_after_s = {k: STALE_PERIODS / r for k, r in rates.items()}
        self.tick = 0
        self.seq = 0
        self.tlm_seq = 0
        self.latest = {}          # field -> latest VALID value (telemetry)
        self.fresh = {}           # field -> raw value sampled since the last logged frame (logger validates and flags)
        self._tick_values = {}    # field -> valid value sampled in the current tick
        self.last_valid_s = {}    # sensor -> time of the last fully valid sample
        self.invalid_samples = {} # sensor -> number of samples with at least one invalid value
        self.packets_sent = 0

    # -------------------------------------------------------------------------------------------------- loop
    @property
    def time_s(self):
        return self.tick * self.base_us / 1e6

    def step(self):
        t_s = self.time_s
        t_us = self.tick * self.base_us
        self._tick_values = {}
        for s in self.sensors:
            if s.due(t_us):
                smp = s.sample(t_us)
                if smp is not None:
                    self._ingest(smp, t_s)
        ready = self.est.kf.initialised
        state = self.clf.update(t_s, self._tick_values.get("imu_accel_z"),
                                self.est.altitude if ready else None, self.est.vertical_velocity if ready else None)
        if state != FlightState.PRELAUNCH:
            self.est.freeze_pad_reference()
        self.est.set_baro_only(state in (FlightState.DESCENT, FlightState.LANDED))
        if self.logger is not None and self.tick % self.log_every == 0:
            self._log(t_s, state)
        if self.link is not None and self.tick % self.tlm_every == 0:
            self._transmit(t_s, state)
        self.tick += 1
        return state

    def run(self, duration_s):
        n = int(round(duration_s * 1e6 / self.base_us))
        for _ in range(n + 1):
            self.step()
        return self.clf.events

    def health(self, t_s=None):
        """{imu_ok, baro_ok, gnss_ok, temp_ok, battery_ok}: True while the sensor delivered a fully valid sample within
        its stale limit."""
        t = self.time_s if t_s is None else t_s
        return {flag: sensor in self.last_valid_s and t - self.last_valid_s[sensor] <= self.stale_after_s[sensor] + 1e-9
                for sensor, flag in HEALTH_FLAGS.items()}

    # -------------------------------------------------------------------------------------------------- internals
    def _validate(self, values):
        """Split a sample into (clean values for processing, any_invalid). Missing values are not 'invalid'."""
        clean, bad = {}, False
        for k, raw in values.items():
            if k in self.schema.by_name:
                v, issue = self.schema.parse_value(k, raw)
                bad = bad or (issue is not None and issue != "missing")
            else:
                v = raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(raw) else None
            clean[k] = v
        return clean, bad

    def _ingest(self, smp, t_s):
        raw = dict(smp.values)
        clean, bad = self._validate(raw)
        if smp.sensor == "imu":
            self.est.on_accel(t_s, clean.get("imu_accel_z"))
        elif smp.sensor == "baro":
            h = self.est.on_pressure(t_s, clean.get("barometric_pressure"))
            raw["altitude"] = clean["altitude"] = h
        elif smp.sensor == "gnss" and not clean.get("gps_fix"):
            for k in ("latitude", "longitude", "gps_altitude"):
                raw[k] = clean[k] = None
        if bad:
            self.invalid_samples[smp.sensor] = self.invalid_samples.get(smp.sensor, 0) + 1
        elif any(v is not None for v in clean.values()):
            self.last_valid_s[smp.sensor] = t_s
        self._tick_values.update(clean)
        self.fresh.update(raw)
        self.latest.update({k: v for k, v in clean.items() if v is not None})

    def _log(self, t_s, state):
        frame = dict(self.fresh)
        frame.update(seq=self.seq, timestamp=round(t_s, 6), flight_state=state.value,
                     vertical_velocity=self.est.vertical_velocity if self.est.kf.initialised else None)
        self.logger.log(frame)
        self.seq += 1
        self.fresh = {}

    def _transmit(self, t_s, state):
        L = self.latest
        acc = [L.get(k) for k in ("imu_accel_x", "imu_accel_y", "imu_accel_z")]
        mag = math.sqrt(sum(a * a for a in acc)) if all(a is not None for a in acc) else None
        gps_ok = L.get("gps_fix", 0) >= 2
        fr = TelemetryFrame(
            seq=self.tlm_seq, time_s=t_s, simulated=self.simulated, flight_state=state.value,
            altitude_m=self.est.altitude if self.est.kf.initialised else None,
            vertical_velocity_mps=self.est.vertical_velocity if self.est.kf.initialised else None,
            accel_axial_mps2=acc[2] if mag is not None else None, accel_magnitude_mps2=mag,
            temperature_c=L.get("temperature"), latitude_deg=L.get("latitude") if gps_ok else None,
            longitude_deg=L.get("longitude") if gps_ok else None, gps_altitude_m=L.get("gps_altitude") if gps_ok else None,
            gps_fix=L.get("gps_fix"), gps_satellites=L.get("gps_satellites"),
            battery_voltage_v=L.get("battery_voltage"), separation=bool(L.get("separation_detected")),
            **self.health(t_s))
        self.link.send(encode(fr), t_s)
        self.tlm_seq = (self.tlm_seq + 1) & 0xFFFF
        self.packets_sent += 1
