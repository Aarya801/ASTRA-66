"""Tests for the ASTRA-66 visualisation data adapter.

These tests check the one property that matters most: the visualiser must not invent
engineering data. Every exported number is compared against the ASTRA-66 file it came from,
and the honesty markers (NOT FLIGHT CERTIFIED, PLACEHOLDER propulsion, SYNTHETIC sensor data,
documented limitations) must survive the export.

Run:  python -m unittest discover -s visualization/tests -v
"""
import csv
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

VIS = Path(__file__).resolve().parents[1]
REPO = VIS.parent
DATA = VIS / "public" / "data"


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ExportFreshness(unittest.TestCase):
    """The exported data must exist and be regenerable from the repository."""

    def test_data_files_exist(self):
        for name in ("vehicle.json", "trajectory.json", "replay.json", "project.json"):
            with self.subTest(file=name):
                self.assertTrue((DATA / name).exists(),
                                f"{name} missing - run: python visualization/tools/export_flight_data.py")

    def test_adapter_runs_and_is_deterministic(self):
        before = {p.name: p.read_bytes() for p in DATA.glob("*.json")}
        res = subprocess.run([sys.executable, str(VIS / "tools" / "export_flight_data.py")],
                             capture_output=True, text=True, cwd=REPO)
        self.assertEqual(res.returncode, 0, res.stderr)
        for name, blob in before.items():
            with self.subTest(file=name):
                self.assertEqual((DATA / name).read_bytes(), blob,
                                 f"{name} changed although the repository did not")

    def test_adapter_does_not_write_into_the_project(self):
        """Static check: the adapter may only open repository files for reading."""
        src = (VIS / "tools" / "export_flight_data.py").read_text(encoding="utf-8")
        for bad in ("REPO /", "REPO.joinpath"):
            for line in src.splitlines():
                if bad in line and any(w in line for w in ("write_text", "write_bytes", '"w"', "'w'", "open(")):
                    self.assertIn("read", line.lower(), f"possible write into the project: {line.strip()}")


class VehicleMatchesEngineering(unittest.TestCase):
    def setUp(self):
        self.v = jload(DATA / "vehicle.json")
        self.a = jload(REPO / "analysis" / "results" / "analysis.json")

    def test_mass_and_stability_are_copied_not_recomputed(self):
        self.assertAlmostEqual(self.v["mass"]["liftoff_g"]["v"], self.a["M0"], places=6)
        self.assertAlmostEqual(self.v["mass"]["burnout_g"]["v"], self.a["Mb"], places=6)
        self.assertAlmostEqual(self.v["stability"]["cg_liftoff_mm"]["v"], self.a["cg0"], places=6)
        self.assertAlmostEqual(self.v["stability"]["cp_mm"]["v"], self.a["cp"], places=6)
        self.assertAlmostEqual(self.v["stability"]["sm_liftoff_cal"]["v"], self.a["sm0"], places=6)
        self.assertAlmostEqual(self.v["geometry"]["length_mm"]["v"], self.a["L"], places=6)

    def test_geometry_matches_the_generated_cad_parameters(self):
        params = (REPO / "cad" / "astra66_params.scad").read_text(encoding="utf-8")

        def param(name):
            m = re.search(rf"^{name}\s*=\s*([-\d.]+);", params, re.M)
            return float(m.group(1))

        g = self.v["geometry"]
        self.assertEqual(g["body_od_mm"]["v"], param("BODY_OD"))
        self.assertEqual(g["nose_len_mm"]["v"], param("NC_L"))
        self.assertEqual(g["booster_len_mm"]["v"], param("BO_L"))
        self.assertEqual(g["fin"]["root_chord_mm"]["v"], param("FIN_CR"))
        self.assertEqual(g["fin"]["semi_span_mm"]["v"], param("FIN_S"))
        self.assertEqual(g["fin"]["count"]["v"], int(param("FIN_N")))
        self.assertEqual(g["rail_length_m"]["v"], param("RAIL_L"))

    def test_every_value_carries_a_provenance_class(self):
        allowed = {"CALCULATED", "ASSUMPTION", "USER-SUPPLIED", "COMMERCIAL SPEC", "PLACEHOLDER", "SIMULATED"}

        def walk(node, path=""):
            if isinstance(node, dict):
                if set(node) >= {"v", "class"}:
                    self.assertIn(node["class"], allowed, f"{path}: unexpected class {node['class']}")
                else:
                    for k, val in node.items():
                        walk(val, f"{path}/{k}")

        walk(self.v["geometry"])
        walk(self.v["mass"])
        walk(self.v["stability"])

    def test_components_match_the_mass_budget(self):
        with (REPO / "analysis" / "results" / "mass_budget.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        exported = [c for items in self.v["modules"].values() for c in items]
        self.assertEqual(len(exported), len(rows))
        by_id = {c["id"]: c for c in exported}
        for row in rows:
            with self.subTest(part=row["id"]):
                c = by_id[row["id"]]
                self.assertAlmostEqual(c["mass_g"], float(row["mass_g"]), places=6)
                self.assertAlmostEqual(c["station_mm"], float(row["cg_station_mm"]), places=6)
                self.assertEqual(c["provenance"], row["provenance"])

    def test_motor_is_still_a_placeholder(self):
        self.assertEqual(self.v["motor_status"], "PLACEHOLDER")


class TrajectoryMatchesSimulation(unittest.TestCase):
    def setUp(self):
        self.t = jload(DATA / "trajectory.json")
        self.f = jload(REPO / "simulation" / "results" / "flight_summary.json")
        self.col = {c: i for i, c in enumerate(self.t["columns"])}

    def test_results_block_is_the_projects_own(self):
        self.assertEqual(self.t["results"], self.f["results"])
        self.assertEqual(self.t["model"], self.f["model"])
        self.assertEqual(self.t["motor_data_status"], "PLACEHOLDER")

    def test_time_is_monotonic_and_starts_at_zero(self):
        times = [s[self.col["t_s"]] for s in self.t["samples"]]
        self.assertEqual(times[0], 0.0)
        self.assertTrue(all(b > a for a, b in zip(times, times[1:])), "trajectory time must increase")

    def test_peaks_survive_decimation(self):
        res = self.f["results"]
        alt = max(s[self.col["altitude_m"]] for s in self.t["samples"])
        vel = max(s[self.col["velocity_mps"]] for s in self.t["samples"])
        acc = max(s[self.col["accel_mps2"]] for s in self.t["samples"])
        self.assertAlmostEqual(alt, res["apogee_m"], delta=0.05)
        self.assertAlmostEqual(vel, res["v_max_mps"], delta=0.05)
        self.assertAlmostEqual(acc / 9.80665, res["a_max_g"], delta=0.01)

    def test_samples_are_a_subset_of_the_real_trajectory_rows(self):
        """Every exported sample must exist in trajectory_baseline.csv - nothing is synthesised."""
        with (REPO / "simulation" / "results" / "trajectory_baseline.csv").open(encoding="utf-8", newline="") as fh:
            rows = {round(float(r["t_s"]), 4): r for r in csv.DictReader(fh)}
        for s in self.t["samples"][::17]:
            t = round(s[self.col["t_s"]], 4)
            with self.subTest(t=t):
                self.assertIn(t, rows)
                self.assertAlmostEqual(s[self.col["altitude_m"]], float(rows[t]["altitude_m"]), places=3)
                self.assertAlmostEqual(s[self.col["velocity_mps"]], float(rows[t]["velocity_mps"]), places=3)

    def test_phase_labels_come_from_the_simulation(self):
        with (REPO / "simulation" / "results" / "trajectory_baseline.csv").open(encoding="utf-8", newline="") as fh:
            phases = {r["phase"] for r in csv.DictReader(fh)}
        self.assertEqual(set(self.t["phases"]), phases)
        self.assertIn("simulation", self.t["phase_source"])

    def test_placeholder_dependency_is_preserved(self):
        self.assertEqual(self.t["placeholder_dependency"], self.f["placeholder_dependency"])
        self.assertIn("PLACEHOLDER", self.t["disclaimer"])


class ReplayMatchesAvionics(unittest.TestCase):
    def setUp(self):
        self.r = jload(DATA / "replay.json")
        self.e = jload(REPO / "simulation" / "results" / "avionics_replay" / "replay_events.json")

    def test_data_is_labelled_synthetic(self):
        self.assertEqual(self.r["data_class"], "SYNTHETIC")
        self.assertEqual(self.r["data_source_mode"], self.e["summary"]["data_source_mode"])
        self.assertIn("SYNTHETIC", self.r["data_source_mode"])

    def test_events_match_the_replay_output(self):
        self.assertEqual(self.r["events"], self.e["summary"]["flight_events"])

    def test_phase_comes_from_the_flight_computer(self):
        self.assertIn("classifier", self.r["phase_source"])

    def test_sensor_channels_are_only_those_that_exist(self):
        sample = self.r["samples"][len(self.r["samples"]) // 2]
        self.assertIn("pressure", sample)
        self.assertNotIn("thrust", sample, "the sensor replay has no thrust channel and must not invent one")
        self.assertNotIn("mach", sample)

    def test_health_flags_are_carried(self):
        self.assertEqual(self.r["health_fields"], ["imu", "baro", "gnss", "temp", "battery"])
        self.assertTrue(all(len(s["health"]) == 5 for s in self.r["samples"]))


class ProjectStatusHonesty(unittest.TestCase):
    def setUp(self):
        self.p = jload(DATA / "project.json")

    def test_not_flight_certified(self):
        self.assertFalse(self.p["flight_certified"])

    def test_validation_counts_come_from_the_pipeline(self):
        pipe = jload(REPO / "simulation" / "results" / "pipeline_status.json")
        text = " ".join(" ".join(s["tail"]) for s in pipe["steps"])
        v = self.p["software_validation"]
        self.assertIn(f"Ran {v['regression_tests']} tests", text)
        self.assertIn(f"Ran {v['avionics_tests']} tests", text)
        self.assertEqual(v["total_tests"], v["regression_tests"] + v["avionics_tests"])
        self.assertIn(f"verification {v['simulation_checks'][0]}/{v['simulation_checks'][1]} passed", text)

    def test_cad_counts_match_the_committed_validation(self):
        cad = jload(REPO / "cad" / "exports" / "validation_results.json")
        self.assertEqual(self.p["software_validation"]["cad_checks"], cad["summary"])

    def test_software_validation_is_labelled_as_such(self):
        v = self.p["software_validation"]
        self.assertEqual(v["label"], "DIGITAL / SOFTWARE VALIDATION")
        self.assertIn("not constitute physical flight certification", v["caveat"])

    def test_limitations_are_not_empty(self):
        self.assertGreaterEqual(len(self.p["limitations"]), 5)

    def test_simulation_basis_states_the_model_honestly(self):
        b = self.p["simulation_basis"]
        self.assertIn("1-DOF", b["degrees_of_freedom"])
        self.assertIn("SIMULATED", b["trajectory_is"])
        self.assertIn("SYNTHETIC", b["sensor_data_is"])
        self.assertIn("NOT MODELLED", b["attitude_is"])
        self.assertIn("wind and weathercocking", b["not_modelled"])

    def test_sources_are_recorded_with_hashes(self):
        import hashlib
        self.assertGreaterEqual(len(self.p["sources"]), 10)
        for s in self.p["sources"][:4]:
            path = REPO / s["path"]
            with self.subTest(path=s["path"]):
                self.assertTrue(path.exists())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), s["sha256"])


class FrontEndHonesty(unittest.TestCase):
    """The shipped page must carry the project's status markers."""

    def setUp(self):
        self.html = (VIS / "index.html").read_text(encoding="utf-8")

    def test_page_states_not_flight_certified(self):
        self.assertIn("NOT FLIGHT CERTIFIED", self.html)

    def test_page_is_labelled_a_digital_visualisation(self):
        upper = self.html.upper()
        self.assertTrue("DIGITAL FLIGHT VISUALIZATION" in upper or "DIGITAL FLIGHT VISUALISATION" in upper)

    def test_panels_for_basis_limitations_and_validation_exist(self):
        for pid in ("panel-basis", "panel-limits", "panel-validation", "panel-engineering", "panel-sources"):
            self.assertIn(pid, self.html)

    def test_no_claim_of_measured_flight(self):
        lowered = self.html.lower()
        for claim in ("flight proven", "flight tested", "flight certified rocket", "measured flight data"):
            self.assertNotIn(claim, lowered)

    def test_ui_renders_missing_values_as_not_available(self):
        ui = (VIS / "src" / "ui.js").read_text(encoding="utf-8")
        self.assertIn("NOT AVAILABLE", ui)
        site = (VIS / "src" / "site.js").read_text(encoding="utf-8")
        self.assertIn("N/A — NOT AVAILABLE IN CURRENT MODEL", site)

    def test_github_links_are_safe_and_correct(self):
        self.assertIn('href="https://github.com/Aarya801/ASTRA-66"', self.html)
        for m in re.finditer(r'<a [^>]*target="_blank"[^>]*>', self.html):
            self.assertIn("noopener", m.group(0), f"unsafe new-tab link: {m.group(0)[:90]}")

    def test_website_sections_exist(self):
        for sid in ("simulator", "flight-data", "system", "validation", "limitations", "about"):
            self.assertIn(f'id="{sid}"', self.html)

    def test_no_developer_machine_paths_anywhere_in_the_app(self):
        bad = re.compile(r"localhost|127\.0\.0\.1|file:///|[A-Za-z]:\\Users")
        for path in [VIS / "index.html", *(VIS / "src").glob("*.js"), (VIS / "src" / "styles.css")]:
            with self.subTest(file=path.name):
                self.assertIsNone(bad.search(path.read_text(encoding="utf-8")),
                                  f"developer-machine reference in {path.name}")


class EngineeringProjectUntouched(unittest.TestCase):
    """The visualiser must not have modified the engineering project."""

    def test_only_visualization_files_are_new(self):
        res = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
        if res.returncode != 0:
            self.skipTest("not a git checkout")
        changed = [line[3:].strip().strip('"') for line in res.stdout.splitlines() if line.strip()]
        # vercel.json is the deployment descriptor for this site; it is the only file the
        # visualiser is allowed to add outside its own directory.
        allowed = ("visualization/", ".claude/", "vercel.json")
        outside = [c for c in changed if not c.startswith(allowed)]
        self.assertEqual(outside, [], f"files outside visualization/ changed: {outside}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
