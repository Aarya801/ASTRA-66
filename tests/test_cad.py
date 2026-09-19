"""CAD rev B regression tests (standard library only; OpenSCAD is NOT needed to run them).

They check the committed CAD outputs produced by `python cad/build_cad.py`:
parameter coverage of the OpenSCAD sources, exported STL/DXF files, the validation summary and the
CAD-derived mass hand-off to analysis.py.

    python -m unittest discover -s tests -v
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "documentation" / "generator"))
sys.path.insert(0, str(ROOT / "cad"))

import analysis  # noqa: E402
import cad_parts  # noqa: E402
from cadtools import mesh  # noqa: E402

CAD = ROOT / "cad"
TOKEN = re.compile(r"\b[A-Z][A-Z0-9_]{1,}\b")


def strip(src):
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"(?m)^\s*(use|include)\s*<[^>]*>", "", src)     # file paths contain part numbers, not identifiers
    return re.sub(r'"[^"\n]*"', "", src)


class ScadSources(unittest.TestCase):
    def test_every_uppercase_identifier_is_defined(self):
        defined = set()
        files = [CAD / "astra66_params.scad", CAD / "lib" / "astra66_core.scad", CAD / "astra66.scad",
                 CAD / "assembly" / "astra66_assembly.scad", *sorted((CAD / "parts").glob("*.scad"))]
        for f in files:
            defined |= set(re.findall(r"^\s*([A-Z][A-Z0-9_]*)\s*=", f.read_text(encoding="utf-8"), re.M))
        defined |= {"X", "Y", "Z"}
        for f in files[1:]:
            used = set(TOKEN.findall(strip(f.read_text(encoding="utf-8"))))
            with self.subTest(file=f.name):
                self.assertEqual(sorted(used - defined), [])

    def test_parameters_generated_from_analysis(self):
        params = (CAD / "astra66_params.scad").read_text(encoding="utf-8")
        for name, p in analysis.P.items():
            if isinstance(p["v"], (int, float, list)):
                self.assertRegex(params, rf"(?m)^{name}\s*=")

    def test_one_source_file_per_registered_part(self):
        for p in cad_parts.PARTS:
            self.assertTrue((CAD / "parts" / p["file"]).exists(), p["file"])


class CadExports(unittest.TestCase):
    def test_print_stls_exist_and_are_closed(self):
        for p in cad_parts.PARTS:
            if p["kind"] != "print":
                continue
            files = sorted((CAD / "exports" / "stl").glob(f"{p['id']}*_*.stl"))
            with self.subTest(part=p["id"]):
                self.assertTrue(files, "no STL exported")
                for f in files:
                    tris = mesh.read_stl(f)
                    self.assertTrue(mesh.manifold(tris)["ok"], f.name)
                    self.assertGreater(mesh.props(tris)["volume"], 0)
                    self.assertAlmostEqual(mesh.props(tris)["bbox_min"][2], 0.0, places=3)   # on the bed

    def test_cut_profiles_exist(self):
        for p in cad_parts.PARTS:
            if p["kind"] in ("ply", "foam"):
                for s in p.get("subs", [None]):
                    stem = f"{p['id']}{'-' + s if s else ''}_"
                    with self.subTest(part=stem):
                        self.assertTrue(list((CAD / "exports" / "dxf").glob(stem + "*.dxf")))

    def test_drawings_generated(self):
        svgs = list((CAD / "drawings").glob("CAD-*.svg"))
        self.assertGreaterEqual(len(svgs), 6 + len(cad_parts.PARTS))

    def test_every_svg_is_well_formed_xml(self):
        import xml.etree.ElementTree as ET
        files = [*(CAD / "drawings").glob("*.svg"), *(CAD / "exports" / "dxf").glob("*.svg"),
                 *(ROOT / "documentation" / "drawings").glob("*.svg"), *(ROOT / "avionics" / "diagrams").glob("*.svg")]
        self.assertTrue(files)
        for f in files:
            with self.subTest(svg=f.name):
                ET.parse(f)


class ValidationReport(unittest.TestCase):
    rep = json.loads((CAD / "exports" / "validation_results.json").read_text(encoding="utf-8"))

    def test_no_failures(self):
        self.assertEqual(self.rep["summary"]["FAIL"], 0, [r for k in ("geometry", "interfaces", "feasibility", "rail", "fasteners", "dimensions")
                                                          for r in self.rep[k] if r.get("status") == "FAIL"])

    def test_no_interference(self):
        self.assertFalse([i for i in self.rep["interference"] if i["result"] == "INTERFERENCE"])

    def test_dimensions_match_analysis(self):
        for d in self.rep["dimensions"]:
            if d["delta"] is not None:
                with self.subTest(dim=d["dimension"]):
                    self.assertLess(abs(d["delta"]), 0.05)

    def test_report_written(self):
        self.assertIn("CAD validation report", (ROOT / "documentation" / "CAD_VALIDATION.md").read_text(encoding="utf-8"))

    def test_placeholder_motor_is_flagged(self):
        md = (ROOT / "documentation" / "CAD_VALIDATION.md").read_text(encoding="utf-8")
        if analysis.MOTOR_STATUS == "PLACEHOLDER":
            self.assertIn("Placeholder motor", md)


class MotorConfig(unittest.TestCase):
    def test_manufacturer_status_requires_provenance(self):
        import copy
        import tempfile
        cfg = copy.deepcopy(analysis.MOTOR_CFG)
        cfg["status"] = "MANUFACTURER_DATA"
        orig = analysis.MOTOR_CONFIG_FILE
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "motor_config.json"
            f.write_text(json.dumps(cfg), encoding="utf-8")
            analysis.MOTOR_CONFIG_FILE = str(f)
            try:
                with self.assertRaises(ValueError):
                    analysis._load_motor_config()
            finally:
                analysis.MOTOR_CONFIG_FILE = orig


class MassHandOff(unittest.TestCase):
    def test_analysis_uses_cad_masses(self):
        data = json.loads((CAD / "exports" / "cad_mass_properties.json").read_text(encoding="utf-8"))
        items = {i["id"]: i for i in analysis.build_mass_items()}
        for k, v in data["analysis_overrides"].items():
            with self.subTest(item=k):
                self.assertAlmostEqual(items[k]["m"], v["m"], places=3)
                self.assertTrue(items[k]["note"].startswith("CAD:"))


if __name__ == "__main__":
    unittest.main()
