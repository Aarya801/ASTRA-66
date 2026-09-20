# ASTRA-66 — Reproducibility guide

> Every result in this repository can be regenerated from the sources with one command. Only commands that exist in
> the repository are listed. ASTRA-66 is an educational engineering project and is **NOT FLIGHT CERTIFIED**.

## 1. Requirements

| Item | Requirement |
|---|---|
| Python | 3.12 or newer (tested on 3.12 and 3.14, and in CI on both) |
| Packages | **none** — standard library only; `requirements.txt` documents this |
| Operating system | Windows, Linux or macOS (CI runs Ubuntu; development was on Windows) |
| Disk | about 25 MB for the repository |
| OpenSCAD | **optional**, only to re-render the CAD: version 2021.01 from openscad.org, not bundled |
| Browser | optional, to view the engineering package and the ground-station dashboard |

## 2. Setup

```bash
git clone https://github.com/Aarya801/ASTRA-66.git
cd ASTRA-66
python --version        # expect 3.12 or newer
```

Nothing to install. No environment variables are required; the only two the project reads are optional tool paths for
OpenSCAD (`OPENSCAD`, `ASTRA66_CAD_WORK`).

## 3. Commands

| Purpose | Command |
|---|---|
| **Full validation (the one that matters)** | `python run_validation.py` |
| Full validation including a CAD re-render | `python run_validation.py --with-cad --openscad "C:/path/to/openscad.com"` |
| Project regression tests only | `python -m unittest discover -s tests` |
| Avionics software tests only | `python -m unittest discover -s avionics/tests -t .` |
| Engineering package only | `python build.py` |
| Flight simulation only | `python simulation/flight_simulation.py` |
| CAD build and validation only | `python cad/build_cad.py --openscad <path>` |
| Sensor replay (synthetic dataset) | `python simulation/avionics_replay.py` |
| Regenerate the synthetic dataset | `python simulation/avionics_replay.py --make-sample` |
| Regenerate the bench-record template | `python simulation/avionics_replay.py --make-bench-example` |
| Simulated flight through the avionics software | `python -m avionics.firmware.simulate_flight` |
| Post-flight analysis of a log | `python avionics/analysis/flight_data_analysis.py avionics/data/example/example_flight_simulated.csv` |
| Ground-station prototype (replay only) | `python avionics/ground_station/server.py --sensors simulation/data/sample_flight.csv` |
| CAD fit and mass-properties check | `python avionics/integration/cad_mass_integration.py --check` |
| Standalone engineering package page | `python hosting/make_standalone.py` |

Run everything from the repository root.

## 4. Expected result

`python run_validation.py` ends with `OVERALL: PASS` (exit code 0) and these seven steps:

```
[PASS] Engineering package build (build.py)
[PASS] CAD integration (committed validation is current)     147 PASS · 12 WARN · 0 FAIL
[PASS] Flight simulation, stability, sensitivity, reports    verification 13/13 passed
[PASS] Avionics sensor replay (synthetic sample)             4 events, 3 invalid samples rejected
[PASS] Avionics CAD fit and mass-properties check            11 PASS · 4 WARN · 8 UNVERIFIED · 0 FAIL
[PASS] Regression tests                                      Ran 74 tests
[PASS] Avionics software tests (hardware-free)               Ran 81 tests
OVERALL: PASS
```

Representative numbers you should see (all with the **placeholder** motor, so illustrative only): apogee 328.2 m,
maximum speed 80.3 m/s, peak acceleration 7.4 g, rail exit 11.7 m/s, descent 5.09 m/s, liftoff mass 1210.7 g,
CG STA 696.4 mm, CP STA 870.3 mm, static margin 2.63 calibres.

Checksums: `MANIFEST.sha256` covers every tracked file.

```bash
sha256sum -c MANIFEST.sha256        # Linux/macOS or Git Bash
```

## 5. What changes between runs

- The pipeline stamps the **run date** into `documentation/ENGINEERING_STATUS.md`,
  `documentation/SIMULATION_VALIDATION.md`, `simulation/results/flight_summary.json`,
  `simulation/results/stability_report.md` and `simulation/results/pipeline_status.json`. Only those date fields
  change; the engineering values do not. After a run on a new day, those files differ from the committed copies until
  you commit them (or restore them with `git checkout --`).
- A CAD re-render (`--with-cad`) reproduces the same geometry and the same validation result, but the exported files
  are **not byte-identical** (last-bit float formatting, and the render date in the drawings and the package page).
  If you re-render, commit the regenerated CAD outputs together with the package.
- Synthetic datasets are seeded, so they regenerate to the same values.

## 6. Interpreting failures

| Symptom | Likely cause | What to do |
|---|---|---|
| `CAD SOURCES OR PARAMETERS CHANGED since the last CAD validation` | A `.scad` file or a parameter changed without re-rendering | Re-run with `--with-cad --openscad <path>` and commit the regenerated CAD outputs |
| `test_generated_files_match_committed` fails | Generated files are stale, or a CAD re-render changed the embedded date | Run `python build.py`, commit the regenerated outputs; after a re-render commit the CAD outputs too |
| Simulation verification check fails | A change altered the physics or the numerics | Read the failing check in `SIMULATION_VALIDATION.md`; fix the code, do not adjust the tolerance |
| `test_docs` path failure | A document quotes a file that does not exist (or a non-path in backticks) | Fix the reference in the document |
| Avionics test failure after editing firmware | The processing chain changed behaviour | Compare against the synthetic truth in `simulation/data/sample_flight.meta.json`; fix the code, not the expectation |
| `DataSourceNotAvailable` | Something tried to use `FLIGHT` data | Correct: no flight record exists. Only a genuine, mentor-reviewed record may enable it |
| Checksum mismatch in `MANIFEST.sha256` | Generated files were regenerated (dates) or edited by hand | Check the diff; regenerate the manifest only when the change is intentional |
| OpenSCAD "can't open file" on Windows | Path longer than 260 characters | The pipeline already works in a short temp folder; set `ASTRA66_CAD_WORK` to override it |

Rule used throughout this project: **fix the cause, never the expectation.** If a test and the code disagree, one of
them is wrong — decide which, and say so in the commit.
