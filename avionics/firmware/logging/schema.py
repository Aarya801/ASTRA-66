"""Loads avionics/data/schema/flight_data_schema.json and validates / formats / parses flight-data records with it.

Validation never "repairs" a value: anything missing, non-finite, unparseable or outside the plausibility range
becomes None (empty in CSV) and is reported, and its sensor group's bit is set in `quality_flags`.
"""
import json
import math
import os
from dataclasses import dataclass, field

from ..crc import crc16

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCHEMA_PATH = os.path.join(ROOT, "avionics", "data", "schema", "flight_data_schema.json")


@dataclass(frozen=True)
class FieldDef:
    name: str
    type: str
    unit: str
    description: str
    required: bool = False
    decimals: int = None
    valid_range: tuple = None
    values: tuple = None
    quality_bit: int = None


@dataclass
class ValidationResult:
    record: dict
    issues: list = field(default_factory=list)       # [(field, kind, raw)]
    quality_flags: int = 0
    rejected: bool = False


class FlightDataSchema:
    def __init__(self, doc):
        self.doc = doc
        self.version = doc["version"]
        self.fields = []
        for f in doc["fields"]:
            self.fields.append(FieldDef(
                name=f["name"], type=f["type"], unit=f["unit"], description=f["description"], required=f.get("required", False),
                decimals=f.get("decimals"), valid_range=tuple(f["valid_range"]) if "valid_range" in f else None,
                values=tuple(f["values"]) if "values" in f else None, quality_bit=f.get("quality_bit")))
        self.by_name = {f.name: f for f in self.fields}
        self.names = [f.name for f in self.fields]
        self.data_names = [n for n in self.names if n != "crc16"]
        self.sources = tuple(doc["data_sources"])

    @classmethod
    def load(cls, path=SCHEMA_PATH):
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    # ------------------------------------------------------------------------------------------ single values
    def parse_value(self, name, raw):
        """Return (value, issue_kind or None). `raw` may be a Python value or a CSV string ('' = missing)."""
        f = self.by_name[name]
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            return None, "missing"
        try:
            if f.type == "float":
                v = float(raw)
                if not math.isfinite(v):
                    return None, "non_finite"
            elif f.type == "int":
                if isinstance(raw, bool):
                    v = int(raw)
                elif isinstance(raw, float):
                    if not math.isfinite(raw) or raw != int(raw):
                        return None, "unparseable"
                    v = int(raw)
                else:
                    v = int(str(raw).strip())
            elif f.type == "enum":
                v = str(raw).strip()
                if v not in f.values:
                    return None, "invalid_enum"
                return v, None
            elif f.type == "hex16":
                v = int(str(raw), 16)
                return (v, None) if 0 <= v <= 0xFFFF else (None, "unparseable")
            else:
                raise ValueError(f"unknown type {f.type}")
        except (TypeError, ValueError):
            return None, "unparseable"
        if f.valid_range and not (f.valid_range[0] <= v <= f.valid_range[1]):
            return None, "out_of_range"
        return v, None

    def format_value(self, name, v):
        if v is None:
            return ""
        f = self.by_name[name]
        if f.type == "float":
            s = f"{v:.{f.decimals}f}" if f.decimals is not None else repr(float(v))
            return s[1:] if s.startswith("-") and float(s) == 0 else s      # no "-0.000"
        if f.type == "hex16":
            return f"{v:04X}"
        return str(v)

    # ------------------------------------------------------------------------------------------ records
    def validate(self, record):
        """Validate a record dict (python values or CSV strings). Missing optional fields are simply None."""
        out = {}
        res = ValidationResult(record=out)
        for key in record:
            if key not in self.by_name:
                res.issues.append((key, "unknown_field", record[key]))
        for f in self.fields:
            if f.name == "crc16":
                continue
            raw = record.get(f.name)
            v, kind = self.parse_value(f.name, raw)
            if f.name == "quality_flags":
                v = v or 0
                kind = None
            out[f.name] = v
            if kind and kind != "missing":
                res.issues.append((f.name, kind, raw))
                if f.quality_bit is not None:
                    res.quality_flags |= 1 << f.quality_bit
            if f.required and v is None:
                res.rejected = True
                if kind == "missing":
                    res.issues.append((f.name, "missing_required", raw))
        out["quality_flags"] = (out.get("quality_flags") or 0) | res.quality_flags
        return res

    def row_text(self, record):
        """CSV text of a validated record WITHOUT the crc16 column, and its CRC."""
        line = ",".join(self.format_value(n, record.get(n)) for n in self.data_names)
        return line, crc16(line)

    def csv_header(self):
        return ",".join(self.names)


def load_schema(path=SCHEMA_PATH):
    return FlightDataSchema.load(path)
