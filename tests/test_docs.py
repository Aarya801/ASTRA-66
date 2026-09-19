"""Documentation integrity: every file path quoted in the project's Markdown exists, and the key documents
carry the draft / not-flight-certified / placeholder disclaimers."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *(ROOT / "documentation").glob("*.md"), *ROOT.glob("*/README.md")]
PATH = re.compile(r"`([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+/?)`")


class DocReferences(unittest.TestCase):
    def test_quoted_paths_exist(self):
        for doc in DOCS:
            for ref in PATH.findall(doc.read_text(encoding="utf-8")):
                if ref.startswith("http"):
                    continue
                with self.subTest(doc=doc.relative_to(ROOT).as_posix(), ref=ref):
                    candidates = [ROOT / ref.rstrip("/"), doc.parent / ref.rstrip("/")]
                    self.assertTrue(any(c.exists() for c in candidates), f"missing: {ref}")


class Disclaimers(unittest.TestCase):
    def test_not_flight_certified_everywhere(self):
        for rel in ("README.md", "documentation/ENGINEERING_STATUS.md", "documentation/SIMULATION_VALIDATION.md",
                    "documentation/CAD_VALIDATION.md", "simulation/README.md"):
            with self.subTest(doc=rel):
                self.assertRegex((ROOT / rel).read_text(encoding="utf-8").lower(), r"not\s+(\*\*)?flight[ -]certified")

    def test_placeholder_propulsion_is_declared(self):
        import json
        if json.loads((ROOT / "simulation" / "motor_config.json").read_text(encoding="utf-8"))["status"] == "PLACEHOLDER":
            for rel in ("documentation/ENGINEERING_STATUS.md", "documentation/SIMULATION_VALIDATION.md", "simulation/results/stability_report.md",
                        "simulation/results/sensitivity_report.md"):
                with self.subTest(doc=rel):
                    self.assertIn("PLACEHOLDER", (ROOT / rel).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
