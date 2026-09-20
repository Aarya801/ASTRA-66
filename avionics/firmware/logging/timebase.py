"""Timestamp handling.

Microcontrollers usually count microseconds in a 32-bit register that wraps every 2^32 µs (about 71.6 minutes), which
a long pad hold can exceed. `CounterUnwrapper` turns such raw readings into a monotonic 64-bit count.
`TimestampMonitor` classifies each new frame time as ok / duplicate / non-monotonic / gap.
"""


class CounterUnwrapper:
    """Unwrap a free-running counter of `bits` width. Assumes it is read at least once per wrap period."""

    def __init__(self, bits=32):
        self.modulus = 1 << bits
        self._last_raw = None
        self._offset = 0

    def __call__(self, raw):
        if not 0 <= raw < self.modulus:
            raise ValueError(f"raw counter value {raw} outside 0..2^{self.modulus.bit_length() - 1}-1")
        if self._last_raw is not None and raw < self._last_raw:
            self._offset += self.modulus
        self._last_raw = raw
        return raw + self._offset


def unwrap_counter(raw_values, bits=32):
    u = CounterUnwrapper(bits)
    return [u(r) for r in raw_values]


class TimestampMonitor:
    """Checks frame times against the previous accepted one.

    check(t_s) returns (accept, issue): issue is None, "gap" (accepted, but more than gap_factor nominal periods since
    the last frame), "duplicate" or "non_monotonic" (both rejected: a logger must never write time going backwards)."""

    def __init__(self, nominal_period_s, gap_factor=3.0):
        self.period = nominal_period_s
        self.gap_factor = gap_factor
        self.last = None
        self.counts = dict(ok=0, gap=0, duplicate=0, non_monotonic=0)

    def check(self, t_s):
        if self.last is not None:
            if t_s == self.last:
                self.counts["duplicate"] += 1
                return False, "duplicate"
            if t_s < self.last:
                self.counts["non_monotonic"] += 1
                return False, "non_monotonic"
            if t_s - self.last > self.gap_factor * self.period:
                self.last = t_s
                self.counts["gap"] += 1
                return True, "gap"
        self.last = t_s
        self.counts["ok"] += 1
        return True, None
