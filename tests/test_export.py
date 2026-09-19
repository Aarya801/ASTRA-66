"""Regression tests for the ASTRA-66 engineering package (standard library only).

They prove the committed generated files rebuild identically from the sources, pin the key engineering
results of CAD rev B, and check that the page keeps every section, sheet and interactive feature.

Run from the project root:
    python -m unittest discover -s tests -v
"""
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

import analysis  # noqa: E402

# inputs build.py needs (relative paths are preserved in the temporary copy)
SOURCES = ["build.py", "analysis/analysis.py", "documentation/generator/drawings.py", "documentation/generator/data_tables.py",
           "documentation/generator/template_a.html", "documentation/generator/template_b.html", "simulation/motor_config.json",
           "cad/exports/cad_mass_properties.json", "cad/exports/validation_results.json"]
DRAWING_KEYS = ["ga", "ex", "sa", "sb", "fn", "nc", "av"]
DIAGRAM_KEYS = ["arch", "elec", "fsm"]
GENERATED_TEXT = (["documentation/ASTRA-66_Engineering_Package.html", "cad/astra66_params.scad", "analysis/results/parameters.csv",
                   "analysis/results/mass_budget.csv", "bom/bom.csv", "bom/fasteners.csv", "bom/materials.csv",
                   "avionics/electronics.csv", "simulation/openrocket_inputs.csv"]
                  + [f"documentation/drawings/{k}.svg" for k in DRAWING_KEYS] + [f"avionics/diagrams/{k}.svg" for k in DIAGRAM_KEYS])
PAGE = ROOT / "documentation" / "ASTRA-66_Engineering_Package.html"


def norm(path):
    # build.py writes platform line endings; content is compared independent of CRLF/LF.
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def assert_close(a, b, path="$"):
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ"
        for k in a:
            assert_close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b)):
            assert_close(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9), f"{path}: {a} != {b}"
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


class RebuildMatchesCommitted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="astra66_"))
        for s in SOURCES:
            (cls.tmp / s).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / s, cls.tmp / s)
        cls.run_result = subprocess.run([sys.executable, "build.py"], cwd=cls.tmp, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_succeeds_without_missing_placeholders(self):
        self.assertEqual(self.run_result.returncode, 0, self.run_result.stderr)
        self.assertIn("missing placeholders: none", self.run_result.stdout)

    def test_generated_files_match_committed(self):
        for rel in GENERATED_TEXT:
            with self.subTest(file=rel):
                self.assertEqual(norm(self.tmp / rel), norm(ROOT / rel))

    def test_analysis_json_matches_committed(self):
        new = json.loads((self.tmp / "analysis" / "results" / "analysis.json").read_text(encoding="utf-8"))
        old = json.loads((ROOT / "analysis" / "results" / "analysis.json").read_text(encoding="utf-8"))
        assert_close(new, old)


class KeyEngineeringResults(unittest.TestCase):
    """CAD rev B values (CAD-derived structural masses, placeholder motor)."""

    @classmethod
    def setUpClass(cls):
        cls.R = analysis.run()

    def test_geometry_mass_stability(self):
        R = self.R
        self.assertAlmostEqual(R["L"], 1144.0)
        self.assertEqual(round(R["M0"]), 1211)
        self.assertEqual(f'{R["cg0"]:.0f}', "696")
        self.assertEqual(f'{R["bw"]["xcp"]:.0f}', "870")
        self.assertAlmostEqual(R["sm0"], 2.635, delta=0.002)     # displayed as 2.63
        self.assertAlmostEqual(R["smb"], 2.920, delta=0.002)
        self.assertAlmostEqual(R["sme"], 3.233, delta=0.002)

    def test_recovery_and_loads(self):
        rec, ld = self.R["recovery"], self.R["loads"]
        self.assertEqual(f'{rec["v_sel"]:.1f}', "5.1")
        self.assertEqual(f'{ld["sf_flutter"]:.1f}', "3.2")

    def test_motor_data_is_placeholder_and_flagged(self):
        self.assertEqual(analysis.MOTOR_STATUS, "PLACEHOLDER")
        for name in ("MOTOR_L", "MOTOR_M0", "MOTOR_MB", "MMT_ID", "RET_CLEAR_D"):
            self.assertIn("PLACEHOLDER", analysis.P[name]["note"])
        self.assertIn("PLACEHOLDER MOTOR", PAGE.read_text(encoding="utf-8"))


class PageStructure(unittest.TestCase):
    html = PAGE.read_text(encoding="utf-8")

    def test_no_unresolved_placeholders(self):
        self.assertIsNone(re.search(r"\{\{[VTS]:", self.html))
        self.assertIsNone(re.search(r"\[\[[VTS]:", self.html))
        self.assertNotIn("{{CHART}}", self.html)

    def test_all_sections_and_nav_links(self):
        for sid in ["scope", "spec", "objectives", "architecture", "cad", "assumptions", "drawings", "analysis", "avionics",
                    "parts", "manufacturing", "assembly", "testing", "simulation", "checklists", "risk", "cost",
                    "software", "route", "future"]:
            with self.subTest(section=sid):
                self.assertIn(f'<section id="{sid}"', self.html)
                self.assertIn(f'href="#{sid}"', self.html)

    def test_drawing_sheets_diagrams_and_chart(self):
        for n in range(1, 8):
            self.assertIn(f'id="A-00{n}"', self.html)
        self.assertEqual(self.html.count("<svg viewBox"), 11)  # 7 sheets + 3 diagrams + 1 chart

    def test_interactive_features_present(self):
        for lst in ("validation", "preflight", "postflight"):
            self.assertIn(f'data-list="{lst}"', self.html)
        self.assertIn("localStorage", self.html)
        self.assertIn('class="hit"', self.html)
        self.assertIn("IntersectionObserver", self.html)

    def test_reports_cad_validation(self):
        self.assertIn("CAD rev B: rendered and checked", self.html)


class StandaloneShell(unittest.TestCase):
    def test_wrapper_embeds_page_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "index.html"
            r = subprocess.run([sys.executable, str(ROOT / "hosting" / "make_standalone.py"), "--out", str(out)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = out.read_text(encoding="utf-8")
            self.assertTrue(doc.startswith("<!doctype html>"))
            self.assertIn('name="viewport"', doc)
            self.assertIn(PAGE.read_text(encoding="utf-8"), doc)


if __name__ == "__main__":
    unittest.main()
