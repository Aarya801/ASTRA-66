"""Ground-station receiver: decodes telemetry packets, keeps link statistics and a received-data log.

Link statistics: packets decoded, packets rejected (bad length / sync / CRC / version), lost = missing sequence
numbers (16-bit wrap aware; includes packets dropped in the air AND packets rejected as corrupted) and duplicates.
Every decoded frame keeps its SIMULATED flag, so the display can always say whether it is showing SIMULATED TELEMETRY.
"""
import csv

from avionics.firmware.telemetry.packet import PacketError, TelemetryFrame, decode

CSV_FIELDS = ["rx_time_s"] + list(TelemetryFrame.__dataclass_fields__)


def read_capture(path):
    """Read a telemetry capture file (rx_time_s,packet_hex). Returns [(rx_time_s, bytes)]; unreadable lines give b""."""
    out = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append((float(row["rx_time_s"]), bytes.fromhex(row["packet_hex"])))
            except (TypeError, ValueError, KeyError):
                out.append((float("nan"), b""))
    return out


class GroundStationReceiver:
    def __init__(self):
        self.frames = []            # [(rx_time_s, TelemetryFrame)]
        self.rejected = 0
        self.lost = 0
        self.duplicates = 0
        self.errors = {}
        self._last_seq = None

    def ingest(self, packet, rx_time_s=None):
        """Decode one packet. Returns the TelemetryFrame, or None if it was rejected or a duplicate."""
        try:
            fr = decode(packet)
        except PacketError as exc:
            self.rejected += 1
            key = str(exc).split(" ")[0] if "length" in str(exc) else str(exc)
            self.errors[key] = self.errors.get(key, 0) + 1
            return None
        if self._last_seq is not None:
            gap = (fr.seq - self._last_seq) & 0xFFFF
            if gap == 0:
                self.duplicates += 1
                return None
            if gap < 0x8000:
                self.lost += gap - 1
        self._last_seq = fr.seq
        self.frames.append((rx_time_s, fr))
        return fr

    @property
    def simulated(self):
        """True if any received frame is SIMULATED (None before the first frame)."""
        return None if not self.frames else any(f.simulated for _, f in self.frames)

    def stats(self):
        n = len(self.frames)
        total = n + self.lost
        last_rx, last = self.frames[-1] if self.frames else (None, None)
        return dict(decoded=n, rejected=self.rejected, lost=self.lost, duplicates=self.duplicates,
                    errors=dict(self.errors), packet_success_rate=None if total == 0 else round(n / total, 4),
                    packet_loss_percent=None if total == 0 else round(100.0 * self.lost / total, 2),
                    last_packet_time_s=None if last is None else last.time_s,
                    last_rx_time_s=last_rx)

    def write_csv(self, path):
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(CSV_FIELDS)
            for rx, f in self.frames:
                w.writerow([rx] + [getattr(f, k) for k in CSV_FIELDS[1:]])
