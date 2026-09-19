"""Simulation regression tests (standard library only).

Re-runs the numerical verification suite and checks the committed simulation outputs:
placeholder flagging, report files, plots (well-formed SVG), and the motor-data interface guards.
"""
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "simulation"
sys.path.insert(0, str(SIM))
sys.path.insert(0, str(ROOT / "analysis"))

import motor as MOT  # noqa: E402
import verification  # noqa: E402


class NumericalVerification(unittest.TestCase):
    def test_all_verification_checks_pass(self):
        res = verification.run_all()
        self.assertTrue(res)
        self.assertEqual([r["check"] for r in res if not r["ok"]], [])


class Outputs(unittest.TestCase):
    summary = json.loads((SIM / "results" / "flight_summary.json").read_text(encoding="utf-8"))

    def test_reports_exist(self):
        for p in ("results/flight_summary.json", "results/stability_report.md", "results/sensitivity_report.md",
                  "results/sensitivity_table.csv", "results/trajectory_baseline.csv"):
            self.assertTrue((SIM / p).exists(), p)
        self.assertTrue((ROOT / "documentation" / "SIMULATION_VALIDATION.md").exists())

    def test_placeholder_results_are_flagged(self):
        self.assertFalse(self.summary["results_are_predictions"])
        self.assertFalse(self.summary["valid_for_flight_planning"])
        if self.summary["motor_data_status"] == "PLACEHOLDER":
            self.assertTrue(self.summary["trajectory_uses_placeholder_propulsion"])
            self.assertTrue(all("PLACEHOLDER" in v or "independent" in v for v in self.summary["placeholder_dependency"].values()))
            self.assertFalse(self.summary["valid_for_flight_planning"])
            self.assertTrue(self.summary["motor_input"]["placeholder"])
            for f in ("stability_report.md", "sensitivity_report.md"):
                self.assertIn("PLACEHOLDER TEST INPUT", (SIM / "results" / f).read_text(encoding="utf-8"))
            self.assertIn("PLACEHOLDER TEST INPUT", (ROOT / "documentation" / "SIMULATION_VALIDATION.md").read_text(encoding="utf-8"))

    def test_physical_sanity(self):
        r = self.summary["results"]
        self.assertGreater(r["apogee_m"], r["h_burnout_m"])
        self.assertGreater(r["t_apogee_s"], r["t_burnout_s"])
        self.assertLess(r["mach_max"], 0.6)
        self.assertAlmostEqual(r["mass_liftoff_g"] - r["mass_burnout_g"], self.summary["motor_input"]["prop_mass_g"], places=3)

    def test_plots_are_wellformed_svg(self):
        svgs = sorted((SIM / "plots").glob("*.svg"))
        self.assertGreaterEqual(len(svgs), 12)
        for f in svgs:
            with self.subTest(plot=f.name):
                ET.parse(f)


class Reproducibility(unittest.TestCase):
    """Re-running the baseline from the committed inputs reproduces the committed trajectory and summary."""

    def test_baseline_trajectory_is_deterministic(self):
        import csv
        import flight_simulation as FS
        run = FS.simulate(FS.SimConfig())
        with open(SIM / "results" / "trajectory_baseline.csv", encoding="utf-8") as fh:
            committed = list(csv.DictReader(fh))
        self.assertEqual(len(committed), len(run["rows"]))
        for c, r in list(zip(committed, run["rows"]))[:: max(1, len(committed) // 400)]:
            self.assertAlmostEqual(float(c["altitude_m"]), r["h"], places=2)
            self.assertAlmostEqual(float(c["velocity_mps"]), r["v"], places=2)
        s = FS.summarize(run)
        committed_s = json.loads((SIM / "results" / "flight_summary.json").read_text(encoding="utf-8"))["results"]
        for k in ("apogee_m", "v_max_mps", "a_max_g", "rail_exit_v_mps", "sm_liftoff", "descent_rate_mps"):
            self.assertAlmostEqual(s[k], committed_s[k], places=6, msg=k)


class InputValidation(unittest.TestCase):
    def test_invalid_simconfig_is_rejected(self):
        import flight_simulation as FS
        for bad in (dict(mass_scale=0), dict(cd_scale=-1), dict(payload_g=-5), dict(rail_length_m=0.01), dict(temp_offset_K=100), dict(deploy="x")):
            with self.subTest(**bad):
                with self.assertRaises(ValueError):
                    FS.simulate(FS.SimConfig(**bad))

    def test_invalid_sim_config_file_is_rejected(self):
        import config
        cfg = json.loads((SIM / "sim_config.json").read_text(encoding="utf-8"))
        cfg["integration"]["dt_burn_s"] = 0
        p = Path(tempfile.mkdtemp()) / "sim_config.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")
        with self.assertRaises(ValueError):
            config.load_sim_config(str(p))


class MotorInterfaceGuards(unittest.TestCase):
    def _cfg(self, **changes):
        cfg = json.loads((SIM / "motor_config.json").read_text(encoding="utf-8"))
        for k, v in changes.items():
            cfg[k] = v
        d = tempfile.mkdtemp()
        (Path(d) / "motors").mkdir()
        (Path(d) / "motors" / "PLACEHOLDER_TEST_INPUT.eng").write_text((SIM / "motors" / "PLACEHOLDER_TEST_INPUT.eng").read_text(encoding="utf-8"), encoding="utf-8")
        p = Path(d) / "motor_config.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")
        return str(p)

    def test_manufacturer_status_rejects_placeholder_curve(self):
        with self.assertRaises(ValueError):
            MOT.load_motor(self._cfg(status="MANUFACTURER_DATA"))

    def test_oversize_motor_is_rejected(self):
        cfg = json.loads((SIM / "motor_config.json").read_text(encoding="utf-8"))
        cfg["motor_mount"]["mmt_id_mm"] = 24.0
        with self.assertRaises(ValueError):
            MOT.load_motor(self._cfg(motor_mount=cfg["motor_mount"]))

    def test_mass_mismatch_is_rejected(self):
        cfg = json.loads((SIM / "motor_config.json").read_text(encoding="utf-8"))
        cfg["motor"]["loaded_mass_g"] += 20
        with self.assertRaises(ValueError):
            MOT.load_motor(self._cfg(motor=cfg["motor"]))


if __name__ == "__main__":
    unittest.main()
