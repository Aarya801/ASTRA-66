"""Architecture and safety-boundary checks, documentation integrity and the ground-station server."""
import glob
import io
import json
import os
import re
import threading
import tokenize
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from avionics.firmware.logging.schema import load_schema
from avionics.firmware.sensor_interfaces.catalog import SENSOR_SPECS
from avionics.ground_station.receiver import read_capture
from avionics.ground_station.server import DEFAULT_CAPTURE, TelemetryFeed, make_server

from .helpers import ROOT

AV = os.path.join(ROOT, "avionics")
PY = glob.glob(os.path.join(AV, "**", "*.py"), recursive=True) + [os.path.join(ROOT, "simulation", "avionics_replay.py")]
# Identifier words that would indicate an actuation / energetic-device interface. None may exist in the avionics code.
# Identifiers are split into words (snake_case and CamelCase) so that e.g. "rejected" does not match "eject".
FORBIDDEN_STEMS = ("ignit", "pyro", "detonat", "squib", "ematch", "deploy", "eject", "actuat", "servo", "relay", "mosfet")
FORBIDDEN_WORDS = {"charge", "charges", "fire", "fires", "fired", "firing", "arm", "armed", "arming", "trigger"}


def identifier_words(name):
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+", name)]


def forbidden(name):
    return any(w.startswith(FORBIDDEN_STEMS) or w in FORBIDDEN_WORDS for w in identifier_words(name))


HARDWARE_MODULES = {"machine", "RPi", "gpiozero", "serial", "spidev", "smbus", "smbus2", "board", "busio", "digitalio"}
DOCS = [*glob.glob(os.path.join(AV, "*.md")), *glob.glob(os.path.join(AV, "*", "README.md")),
        *glob.glob(os.path.join(AV, "architecture", "*.md")), *glob.glob(os.path.join(AV, "integration", "*.md")),
        *(os.path.join(ROOT, "documentation", f) for f in ("AVIONICS_DESIGN.md", "AVIONICS_ARCHITECTURE.md", "PHASE_5_STATUS.md"))]
PATH_REF = re.compile(r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+/?)`")
NOT_CERTIFIED = re.compile(r"not\s+(\*\*)?flight[ -]certified", re.I)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


class SafetyBoundary(unittest.TestCase):
    def test_code_has_no_command_output_identifiers(self):
        hits = []
        for p in PY:
            for tok in tokenize.generate_tokens(io.StringIO(read(p)).readline):
                if tok.type == tokenize.NAME and forbidden(tok.string):
                    hits.append(f"{os.path.relpath(p, ROOT)}:{tok.start[0]} {tok.string}")
        self.assertEqual(hits, [])

    def test_word_splitting_catches_what_it_should(self):
        for bad in ("fire_channel", "IgniterPin", "deployDrogue", "arm", "ARM_STATE", "pyro_out", "eject_charge"):
            self.assertTrue(forbidden(bad), bad)
        for ok in ("rejected", "discharge_slope", "firmware", "alarm", "harmonic", "gyro_x"):
            self.assertFalse(forbidden(ok), ok)

    def test_no_hardware_io_libraries_imported(self):
        for p in PY:
            for m in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z0-9_]+)", read(p), re.M):
                self.assertNotIn(m.group(1), HARDWARE_MODULES, p)

    def test_flight_state_has_no_output_side(self):
        src = read(os.path.join(AV, "firmware", "flight_state", "classifier.py"))
        self.assertIn("DATA PROCESSING ONLY", src)
        self.assertNotRegex(src, r"\bimport\s+(os|socket|subprocess)\b")


class Documentation(unittest.TestCase):
    def test_all_documents_exist(self):
        for rel in ("avionics/README.md", "avionics/architecture/system_architecture.md", "avionics/architecture/data_flow.md",
                    "avionics/architecture/interface_spec.md", "avionics/firmware/README.md",
                    "avionics/ground_station/README.md", "avionics/analysis/README.md", "documentation/AVIONICS_DESIGN.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)

    def test_quoted_paths_exist(self):
        for doc in DOCS:
            for ref in PATH_REF.findall(read(doc)):
                if ref.startswith("http"):
                    continue
                with self.subTest(doc=os.path.relpath(doc, ROOT), ref=ref):
                    cands = [os.path.join(ROOT, ref.rstrip("/")), os.path.join(os.path.dirname(doc), ref.rstrip("/"))]
                    self.assertTrue(any(os.path.exists(c) for c in cands), f"missing: {ref}")

    def test_not_flight_certified_statements(self):
        for rel in ("avionics/README.md", "avionics/architecture/system_architecture.md", "documentation/AVIONICS_DESIGN.md",
                    "avionics/ground_station/README.md"):
            self.assertRegex(read(os.path.join(ROOT, rel)), NOT_CERTIFIED, rel)

    def test_interface_spec_covers_every_sensor_unselected(self):
        spec = read(os.path.join(AV, "architecture", "interface_spec.md"))
        for s in SENSOR_SPECS:
            self.assertIn(s.sensor, spec)
        self.assertGreaterEqual(spec.count("COMPONENT TO BE SELECTED"), len(SENSOR_SPECS))

    def test_design_document_lists_every_schema_field(self):
        doc = read(os.path.join(ROOT, "documentation", "AVIONICS_DESIGN.md"))
        for f in load_schema().names:
            self.assertIn(f"`{f}`", doc)

    def test_block_diagram_is_valid_svg(self):
        root = ET.parse(os.path.join(AV, "architecture", "avionics_block_diagram.svg")).getroot()
        self.assertTrue(root.tag.endswith("svg"))
        text = "".join(root.itertext())
        for label in ("SENSOR LAYER", "FLIGHT-DATA PROCESSING", "DATA LOGGER", "TELEMETRY", "GROUND STATION",
                      "POST-FLIGHT ANALYSIS"):
            self.assertIn(label, text)


class GroundStationServer(unittest.TestCase):
    def test_serves_dashboard_and_simulated_telemetry(self):
        now = [0.0]
        feed = TelemetryFeed(read_capture(DEFAULT_CAPTURE), "test", speed=1.0, clock=lambda: now[0])
        srv = make_server(feed, "127.0.0.1", 0)
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base = f"http://127.0.0.1:{srv.server_address[1]}"
            html = urllib.request.urlopen(base + "/", timeout=5).read().decode("utf-8")
            self.assertIn("SIMULATED TELEMETRY", html)
            self.assertIn("Not validated for real-time flight use", html)
            now[0] = 30.0
            d = json.loads(urllib.request.urlopen(base + "/api/telemetry?after=-1", timeout=5).read())
            self.assertEqual(d["link"], "SIMULATED TELEMETRY")
            self.assertTrue(d["simulated"])
            self.assertGreater(len(d["frames"]), 100)
            self.assertTrue(all(f["simulated"] for f in d["frames"]))
            last = d["frames"][-1]["index"]
            d2 = json.loads(urllib.request.urlopen(base + f"/api/telemetry?after={last}", timeout=5).read())
            self.assertEqual(d2["frames"], [])
            now[0] = 1000.0
            d3 = json.loads(urllib.request.urlopen(base + "/api/telemetry?after=-1", timeout=5).read())
            self.assertTrue(d3["complete"])
            self.assertEqual(d3["frames"][-1]["flight_state"], "LANDED")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(base + "/nope", timeout=5)
            self.assertEqual(cm.exception.code, 404)
            cm.exception.close()
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
