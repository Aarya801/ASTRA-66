"""Hardware-independent sensor interface.

Every sensor, real or simulated, is a `Sensor`: it has a name, a nominal sampling rate and a `sample(t_us)` method that
returns a `SensorSample` (or None when no data are available, e.g. a dropout). The flight computer only talks to this
interface, so a hardware driver can later replace a simulated sensor without touching processing, logging or telemetry.

Sensors are input-only. There is deliberately no method for writing to a device other than its own configuration.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

COMPONENT_TO_BE_SELECTED = "COMPONENT TO BE SELECTED"


@dataclass(frozen=True)
class SensorSample:
    sensor: str                 # sensor name, e.g. "imu"
    t_us: int                   # acquisition time on the flight computer's microsecond clock
    values: dict = field(default_factory=dict)   # schema field name -> value (None = not available)


class Sensor(ABC):
    """Base class. Subclasses implement `_read(t_us)` and may set `simulated`."""

    simulated = False

    def __init__(self, name, rate_hz):
        if rate_hz <= 0:
            raise ValueError("rate_hz must be positive")
        self.name = name
        self.rate_hz = float(rate_hz)
        self.period_us = int(round(1e6 / rate_hz))
        self._next_due_us = None

    def due(self, t_us):
        """True when a new sample should be taken at `t_us` (fixed-rate scheduling, no drift accumulation)."""
        if self._next_due_us is None:
            self._next_due_us = t_us
        return t_us >= self._next_due_us

    def sample(self, t_us):
        """Take one sample and schedule the next one. Returns a SensorSample or None (no data this time)."""
        if self._next_due_us is None:
            self._next_due_us = t_us
        while self._next_due_us <= t_us:
            self._next_due_us += self.period_us
        values = self._read(t_us)
        return None if values is None else SensorSample(self.name, int(t_us), values)

    @abstractmethod
    def _read(self, t_us):
        """Return a dict of schema field values, or None when the sensor produced no data."""


class HardwareSensorNotSelected(RuntimeError):
    pass


class HardwareSensorPlaceholder(Sensor):
    """Stands in for a real driver until the component is selected. Any attempt to read it fails loudly, so simulated
    and real data can never be confused."""

    def __init__(self, name, rate_hz, component=COMPONENT_TO_BE_SELECTED):
        super().__init__(name, rate_hz)
        self.component = component

    def _read(self, t_us):
        raise HardwareSensorNotSelected(f"{self.name}: no hardware driver ({self.component}); use a simulated sensor")
