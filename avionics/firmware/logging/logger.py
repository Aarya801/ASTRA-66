"""Hardware-independent data logger:  sensor frame -> timestamp check -> schema validation -> CSV / JSON-lines sink.

On the flight computer the sink would be a file on the microSD card; here it is any file or memory buffer. The logger
never drops a frame silently: rejected frames are counted and summarised in the metadata sidecar.
"""
import json
import os

from ..crc import crc16
from ..data_source import check_available, normalise
from .schema import load_schema
from .timebase import TimestampMonitor


class LogSink:
    """Destination for validated records."""

    def open(self, schema):
        self.schema = schema

    def write(self, record):
        raise NotImplementedError

    def flush(self):
        pass

    def close(self):
        pass


class MemorySink(LogSink):
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(dict(record))


class CsvLogSink(LogSink):
    """CSV with a header row; every row ends with the CRC-16 of the preceding fields."""

    def __init__(self, path, flush_every=50):
        self.path, self.flush_every = path, flush_every
        self._fh, self._n = None, 0

    def open(self, schema):
        super().open(schema)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8", newline="")
        self._fh.write(schema.csv_header() + "\n")

    def write(self, record):
        line, crc = self.schema.row_text(record)
        self._fh.write(f"{line},{crc:04X}\n")
        self._n += 1
        if self._n % self.flush_every == 0:
            self.flush()

    def flush(self):
        if self._fh:
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None


class JsonlLogSink(LogSink):
    """One JSON object per line; `crc16` covers the compact, key-sorted JSON of the other fields."""

    def __init__(self, path, flush_every=50):
        self.path, self.flush_every = path, flush_every
        self._fh, self._n = None, 0

    def open(self, schema):
        super().open(schema)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._fh = open(self.path, "w", encoding="utf-8", newline="")

    @staticmethod
    def canonical(record):
        return json.dumps({k: v for k, v in record.items() if k != "crc16"}, sort_keys=True, separators=(",", ":"))

    def write(self, record):
        body = {n: record.get(n) for n in self.schema.data_names}
        body["crc16"] = f"{crc16(self.canonical(body)):04X}"
        self._fh.write(json.dumps(body, separators=(",", ":")) + "\n")
        self._n += 1
        if self._n % self.flush_every == 0:
            self.flush()

    def flush(self):
        if self._fh:
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None


class DataLogger:
    """Validate and write frames.

    log(frame) -> (accepted, issues). A frame is rejected when a required field is missing or invalid, or when its
    timestamp is a duplicate or goes backwards. Invalid optional values are written empty and flagged."""

    def __init__(self, sink, data_source, nominal_period_s, schema=None, meta_path=None, metadata=None,
                 allow_flight=False):
        self.schema = schema or load_schema()
        if data_source not in self.schema.sources:
            raise ValueError(f"data_source must be one of {self.schema.sources}")
        self.mode = check_available(data_source, allow_flight)      # FLIGHT is disabled unless explicitly allowed
        self.sink, self.data_source = sink, data_source
        self.meta_path, self.metadata = meta_path, dict(metadata or {})
        self.clock = TimestampMonitor(nominal_period_s)
        self.counts = dict(frames_in=0, written=0, rejected=0, values_rejected=0, timestamp_gaps=0)
        self.issue_counts = {}
        self.sink.open(self.schema)

    def log(self, frame):
        self.counts["frames_in"] += 1
        frame = dict(frame)
        frame.setdefault("data_source", self.data_source)
        try:
            same = normalise(frame["data_source"]) == self.mode
        except ValueError:
            same = False
        if not same:
            return self._reject([("data_source", "source_mismatch", frame["data_source"])])
        res = self.schema.validate(frame)
        issues = [i for i in res.issues if i[1] != "unknown_field"]
        if res.rejected:
            return self._reject(issues)
        ok, t_issue = self.clock.check(res.record["timestamp"])
        if not ok:
            return self._reject(issues + [("timestamp", t_issue, res.record["timestamp"])])
        if t_issue == "gap":
            res.record["quality_flags"] |= 1 << 6
            self.counts["timestamp_gaps"] += 1
        self.counts["values_rejected"] += sum(1 for i in issues if i[1] != "missing_required")
        for f, kind, _ in issues:
            self.issue_counts[f"{f}:{kind}"] = self.issue_counts.get(f"{f}:{kind}", 0) + 1
        self.sink.write(res.record)
        self.counts["written"] += 1
        return True, issues

    def _reject(self, issues):
        self.counts["rejected"] += 1
        for f, kind, _ in issues:
            self.issue_counts[f"{f}:{kind}"] = self.issue_counts.get(f"{f}:{kind}", 0) + 1
        return False, issues

    def summary(self):
        return dict(schema=self.schema.doc["schema"], schema_version=self.schema.version, data_source=self.data_source,
                    data_source_mode=self.mode,
                    counts=dict(self.counts), issue_counts=dict(sorted(self.issue_counts.items())), **self.metadata)

    def close(self):
        self.sink.close()
        s = self.summary()
        if self.meta_path:
            with open(self.meta_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(s, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
        return s
