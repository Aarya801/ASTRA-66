"""Tolerant reader for flight-data CSV logs (as written by CsvLogSink, or recovered from an SD card).

Real logs can be damaged: a power loss truncates the last line, a card error flips bits, a firmware bug writes time
backwards. The reader keeps every row it can trust and reports exactly what it dropped and why:
  * malformed      wrong number of columns (e.g. truncated last line)
  * crc_mismatch   row text does not match its CRC-16 (corrupted row)
  * rejected       required field (seq / timestamp / data_source) missing or invalid
  * non_monotonic / duplicate timestamps
Individual bad values (NaN, out of range, unparseable) become None and are counted per field.
"""
import csv

from ..crc import crc16
from .schema import load_schema
from .timebase import TimestampMonitor


class LogReadReport:
    def __init__(self):
        self.rows_total = 0
        self.rows_ok = 0
        self.dropped = dict(malformed=0, crc_mismatch=0, rejected=0, non_monotonic=0, duplicate=0)
        self.value_issues = {}
        self.timestamp_gaps = []
        self.header_missing = []
        self.header_unknown = []
        self.crc_checked = False
        self.data_sources = set()

    def as_dict(self):
        return dict(rows_total=self.rows_total, rows_ok=self.rows_ok, dropped=dict(self.dropped),
                    value_issues=dict(sorted(self.value_issues.items())), timestamp_gaps=len(self.timestamp_gaps),
                    header_missing=self.header_missing, header_unknown=self.header_unknown, crc_checked=self.crc_checked,
                    data_sources=sorted(self.data_sources))


def read_flight_log(path, schema=None, nominal_period_s=None, verify_crc=True):
    """Return (records, report). Records are dicts of parsed values keyed by schema field name."""
    schema = schema or load_schema()
    rep = LogReadReport()
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return [], rep
    header = [h.strip() for h in rows[0]]
    rep.header_missing = [n for n in schema.names if n not in header]
    rep.header_unknown = [h for h in header if h not in schema.by_name]
    use_crc = verify_crc and "crc16" in header and header[:-1] == schema.data_names and header[-1] == "crc16"
    rep.crc_checked = use_crc
    parsed = []
    for raw in rows[1:]:
        if not raw or (len(raw) == 1 and raw[0].strip() == ""):
            continue
        rep.rows_total += 1
        if len(raw) != len(header):
            rep.dropped["malformed"] += 1
            continue
        if use_crc:
            try:
                ok = int(raw[-1], 16) == crc16(",".join(raw[:-1]))
            except ValueError:
                ok = False
            if not ok:
                rep.dropped["crc_mismatch"] += 1
                continue
        res = schema.validate(dict(zip(header, raw)))
        for f, kind, _ in res.issues:
            if kind != "unknown_field":
                rep.value_issues[f"{f}:{kind}"] = rep.value_issues.get(f"{f}:{kind}", 0) + 1
        if res.rejected:
            rep.dropped["rejected"] += 1
            continue
        parsed.append(res.record)
    if nominal_period_s is None:
        ts = sorted(r["timestamp"] for r in parsed)
        d = sorted(b - a for a, b in zip(ts, ts[1:]) if b > a)
        nominal_period_s = d[len(d) // 2] if d else 1.0
    mon = TimestampMonitor(nominal_period_s)
    records = []
    for r in parsed:
        ok, issue = mon.check(r["timestamp"])
        if not ok:
            rep.dropped[issue] += 1
            continue
        if issue == "gap":
            rep.timestamp_gaps.append(r["timestamp"])
        rep.data_sources.add(r["data_source"])
        records.append(r)
    rep.rows_ok = len(records)
    return records, rep
