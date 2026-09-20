"""Shared fixtures: short simulated flights on the synthetic test profile (no hardware, no files unless asked)."""
import functools
import os

from avionics.firmware.flight_computer import FlightComputer
from avionics.firmware.logging.logger import CsvLogSink, DataLogger, MemorySink
from avionics.firmware.sensor_interfaces.simulated import SyntheticFlightProfile, simulated_sensor_suite
from avionics.firmware.telemetry.link import SimulatedTelemetryLink

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOL = dict(liftoff=0.1, burnout=0.12, apogee_t=0.3, apogee_h=2.0, landing=1.0)


def fly(profile=None, faults=None, seed=0, csv_path=None, log_rate_hz=50.0, loss=0.0, bit_errors=0.0, sensors=None):
    """Run the flight computer on simulated sensors. Returns dict(records|csv_path, events, fc, link, logger, profile)."""
    profile = profile or SyntheticFlightProfile()
    sink = CsvLogSink(csv_path) if csv_path else MemorySink()
    logger = DataLogger(sink, "SIMULATED", 1.0 / log_rate_hz)
    link = SimulatedTelemetryLink(loss_prob=loss, bit_error_prob=bit_errors, seed=seed + 21)
    fc = FlightComputer(sensors or simulated_sensor_suite(profile, seed=seed, faults=faults), logger=logger,
                        telemetry_link=link, log_rate_hz=log_rate_hz)
    events = fc.run(profile.duration)
    logger.close()
    return dict(records=getattr(sink, "records", None), csv_path=csv_path, events=events, fc=fc, link=link, logger=logger,
                profile=profile)


@functools.lru_cache(maxsize=1)
def nominal_flight():
    """One cached nominal synthetic flight (read-only use)."""
    return fly()


def event_times(events):
    return {e.name: e.time_s for e in events}
