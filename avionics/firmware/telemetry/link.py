"""Telemetry links.

  SimulatedTelemetryLink   SIMULATED TELEMETRY: an in-memory channel with seeded packet loss and bit errors, for
                           software development and tests.
  HardwareTelemetryLink    REAL HARDWARE TELEMETRY: interface only. It needs a radio driver object with
                           transmit(bytes) and receive() -> bytes | None. No radio has been selected
                           (COMPONENT TO BE SELECTED); without a driver it refuses to start.
"""
import random
from collections import deque

LINK_SIMULATED = "SIMULATED TELEMETRY"
LINK_HARDWARE = "REAL HARDWARE TELEMETRY"


class TelemetryHardwareUnavailable(RuntimeError):
    pass


class TelemetryLink:
    kind = None

    def send(self, packet, t_s):
        raise NotImplementedError

    def receive(self):
        """Return a list of (t_s, packet_bytes) received since the last call."""
        raise NotImplementedError


class SimulatedTelemetryLink(TelemetryLink):
    kind = LINK_SIMULATED

    def __init__(self, loss_prob=0.0, bit_error_prob=0.0, seed=21):
        self.loss_prob, self.bit_error_prob = loss_prob, bit_error_prob
        self._rng = random.Random(seed)
        self._q = deque()
        self.sent = self.lost = self.corrupted = 0

    def send(self, packet, t_s):
        self.sent += 1
        if self.loss_prob and self._rng.random() < self.loss_prob:
            self.lost += 1
            return
        data = bytearray(packet)
        if self.bit_error_prob and self._rng.random() < self.bit_error_prob:
            i = int(self._rng.random() * len(data)) % len(data)
            data[i] ^= 1 << (int(self._rng.random() * 8) % 8)
            self.corrupted += 1
        self._q.append((t_s, bytes(data)))

    def receive(self):
        out = list(self._q)
        self._q.clear()
        return out


class HardwareTelemetryLink(TelemetryLink):
    kind = LINK_HARDWARE

    def __init__(self, radio=None):
        if radio is None:
            raise TelemetryHardwareUnavailable(
                "REAL HARDWARE TELEMETRY is not available: no radio selected (COMPONENT TO BE SELECTED). "
                "Use SimulatedTelemetryLink for development.")
        for m in ("transmit", "receive"):
            if not callable(getattr(radio, m, None)):
                raise TypeError(f"radio driver must provide {m}()")
        self.radio = radio

    def send(self, packet, t_s):
        self.radio.transmit(packet)

    def receive(self):
        out = []
        while True:
            p = self.radio.receive()
            if p is None:
                return out
            out.append((None, p))
