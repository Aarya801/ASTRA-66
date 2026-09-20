"""Data-source modes: where a dataset came from, and whether the software may consume it.

The same processing pipeline (validation → estimator → classifier → logger → telemetry) runs on all three modes; only
the label and the availability differ.

    SYNTHETIC   computer-generated data (simulated sensors or a truth profile). Not flight data, not a prediction.
    BENCH       recorded from real hardware on the bench (electronics only; the vehicle is not flying).
    FLIGHT      recorded in flight. **Disabled**: no real flight data exist in this repository. Enable only when an
                actual flight record is added and reviewed with a qualified mentor; the project is NOT flight
                certified and nothing here has ever flown.

Legacy labels in the Phase 4 datasets map onto these modes: SIMULATED → SYNTHETIC, HARDWARE → BENCH. Files keep the
label they were written with; the mode is what the software reasons about.
"""
SYNTHETIC, BENCH, FLIGHT = "SYNTHETIC", "BENCH", "FLIGHT"
MODES = (SYNTHETIC, BENCH, FLIGHT)
ALIASES = {"SIMULATED": SYNTHETIC, "HARDWARE": BENCH}
ACCEPTED = tuple(MODES) + tuple(ALIASES)
REAL_SENSOR_MODES = (BENCH, FLIGHT)
ENABLED = {SYNTHETIC: True, BENCH: True, FLIGHT: False}
FLIGHT_DISABLED_REASON = ("FLIGHT data are not available: no real flight record exists in this repository and nothing "
                          "has flown. Pass allow_flight=True only for a reviewed, genuine flight record.")


class DataSourceNotAvailable(RuntimeError):
    """Raised when a disabled data-source mode (FLIGHT) is used."""


def normalise(value):
    """Canonical mode for a label ('SIMULATED' → 'SYNTHETIC'). Raises ValueError for anything else."""
    if value is None:
        raise ValueError("data_source is required")
    v = str(value).strip().upper()
    v = ALIASES.get(v, v)
    if v not in MODES:
        raise ValueError(f"unknown data_source {value!r}; expected one of {', '.join(ACCEPTED)}")
    return v


def is_real_sensor_data(value):
    """True for data recorded from real hardware (BENCH, FLIGHT)."""
    return normalise(value) in REAL_SENSOR_MODES


def check_available(value, allow_flight=False):
    """Return the canonical mode, refusing modes that are disabled."""
    mode = normalise(value)
    if not ENABLED[mode] and not (mode == FLIGHT and allow_flight):
        raise DataSourceNotAvailable(FLIGHT_DISABLED_REASON)
    return mode


def label(value):
    """Short label for plots, reports and displays."""
    mode = normalise(value)
    return {SYNTHETIC: "SYNTHETIC DATA (not flight data)",
            BENCH: "BENCH DATA: real hardware on the bench (not flight data)",
            FLIGHT: "FLIGHT DATA"}[mode]
