# ASTRA-66 — Engineering method

> How this project is actually worked on, and what evidence each stage produces. **NOT FLIGHT CERTIFIED**: stages 6
> and 7 (hardware integration and physical testing) have not started. Propulsion is an external, commercially
> certified component, never designed here.

```
requirements → CAD → analysis → simulation → validation → hardware integration → testing
    (1)        (2)     (3)         (4)          (5)              (6)                (7)
                └──────── automated, reproducible today ────────┘   └─ not yet performed ─┘
```

## 1. Requirements

Written as engineering objectives, not wishes: static margin 1.5–3.0 calibres, modular sections, student-buildable
manufacture, data-only avionics, external certified motor, and full traceability of every number.

Each parameter gets a **provenance tag** when it enters `analysis/analysis.py`:

| Tag | Meaning |
|---|---|
| `CALC` | derived here from other values |
| `ASM` | engineering assumption; must be verified or measured |
| `USER` | user-supplied, for example a measured part or range data |
| `COTS` | commercial component specification, taken from the maker's documents |

*Evidence:* the parameter table and mass budget in `analysis/results/`.

## 2. CAD

The CAD is **downstream of the parameters**, never a parallel source of truth: the analysis writes
`cad/astra66_params.scad`, and every part references it. A change to a diameter therefore propagates to the parts,
drawings, exports and mass budget in one run.

*Evidence:* `CAD_VALIDATION.md` (147 PASS · 12 WARN · 0 FAIL), the exports in `cad/exports/`, the drawing sheets in
`cad/drawings/`.

## 3. Analysis

Mass budget, CG, Barrowman CP, static margin, structural loads and recovery sizing — all in one standard-library
module, all re-derived from the parameters. Structural masses use volumes **measured from the rendered CAD meshes**,
not hand estimates, so the analysis and the model cannot drift apart.

*Evidence:* `analysis/results/analysis.json` and `mass_budget.csv`; the CAD cross-check in
`CAD_AVIONICS_INTEGRATION.md` recomputes the CG independently and confirms it matches.

## 4. Simulation

A 1-DOF flight simulation with an ISA atmosphere and a drag build-up, plus a sensitivity study over the
non-propulsion parameters. The motor is external data with a status flag; while it says `PLACEHOLDER`, every report
prints that the trajectory is illustrative.

The simulation is **verified**, not just run: 13 checks compare it against closed-form solutions (ISA density and
speed of sound, impulse quadrature, constant-thrust burnout altitude and apogee, terminal velocity, time-step
convergence) and against the analysis (liftoff mass, CG, CP).

*Evidence:* `SIMULATION_VALIDATION.md`, `simulation/results/`, `simulation/plots/`.

## 5. Validation

Nothing is "done" until one command reproduces it:

```bash
python run_validation.py
```

Seven steps: package build → CAD currency (or full re-render with `--with-cad`) → simulation → sensor replay →
CAD-fit and mass check → project regression tests → avionics software tests. The same command runs in GitHub Actions
on Python 3.12 and 3.14, and `MANIFEST.sha256` covers every tracked file.

Two rules keep this honest:

1. **Tests are never weakened to pass.** When a test fails, either the code or the documented expectation was wrong.
   Several defects in this repository were found exactly this way (invalid sensor values reaching the estimator; a
   dead sensor looking alive in telemetry; barometric liftoff detection failing without the accelerometer).
2. **Generated files are regenerated, not edited.** Reports, exports and status files come from the pipeline.

*Evidence:* `VALIDATION.md`, `ENGINEERING_STATUS.md` (generated), the CI badge in the README.

## 6. Hardware integration — not started

The plan exists and the interfaces are defined, but no component has been selected, bought, measured or weighed.
The sequence is fixed: select with a mentor against the interface requirements → measure and weigh the real parts →
update the CAD envelopes and the mass budget → re-run the whole pipeline → only then bench-test.

*Planned in:* `HARDWARE_SELECTION_CHECKLIST.md`, `MASS_MEASUREMENT_PROCEDURE.md`, `HARDWARE_INTEGRATION.md`.

## 7. Testing — software only so far

Software tests exist and pass (155 of them). Bench tests are written down but **have not been performed**, and no
flight or range activity has taken place. Anything involving a motor is a mentor's and the range's decision, not this
repository's.

*Planned in:* `TEST_PLAN.md`, `AVIONICS_BENCH_TEST_PLAN.md`.

## Working rules used throughout

- Every value is verified, calculated, assumed, placeholder or unverified — and says which.
- Placeholders are labelled in the data, not only in prose (`motor_config.json` status, `data_source` column,
  `COMPONENT TO BE SELECTED`).
- Safety boundaries are enforced by tests, not by good intentions.
- Synthetic data are never presented as measurements; `FLIGHT` data mode stays disabled until a real record exists.
- Large generated artefacts (exports, drawings, plots) are committed so the work can be reviewed without installing
  OpenSCAD, and regenerated by the pipeline to prove they are current.
