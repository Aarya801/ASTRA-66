# simulation/

A transparent, standard-library-only flight-simulation and engineering-validation pipeline. It uses the CAD-derived
mass properties and geometry as its source of truth.

**Draft student design, not flight certified.** Propulsion is an external, commercially certified component. This
folder only *reads* motor data (masses and a thrust-time table). It never designs, modifies or optimises a motor.

## Reproduce everything: one command

Requirements: Python 3.12+ (tested 3.12.10 and 3.14.6); no third-party packages; no network.

```bash
git clone <repository> ASTRA-66
cd ASTRA-66
python run_validation.py
```

Expected console result (numbers are for the committed inputs):
```
  wrote documentation/ENGINEERING_STATUS.md
ASTRA-66 validation pipeline
  [PASS] Engineering package build (build.py)
  [PASS] CAD integration (committed validation is current)
  [PASS] Flight simulation, stability, sensitivity, reports
         apogee 328.2 m (PLACEHOLDER TEST INPUT)  v_max 80.3 m/s  a_max 7.4 g  rail exit 11.7 m/s  SM rail 2.67 cal  descent 5.09 m/s
         verification 13/13 passed; ...
  [PASS] Regression tests
OVERALL: PASS
```
The exit code is 0 on PASS and 1 on any failure.

Optional full CAD regeneration (external OpenSCAD 2021.01, about 3 minutes):
`python run_validation.py --with-cad --openscad "C:/path/to/openscad.com"`.

### Files the command (re)generates

| File | Content |
|---|---|
| `simulation/results/flight_summary.json` | inputs, results, events, envelope checks, verification, placeholder-dependence map |
| `simulation/results/stability_report.md` | CP (CAD cross-check), CG, static margin vs time/mass/payload/CG, requirement check |
| `simulation/results/sensitivity_report.md` | one-at-a-time sensitivity tables and ranking |
| `simulation/results/sensitivity_table.csv` | all sensitivity runs |
| `simulation/results/trajectory_baseline.csv` | baseline time history (units in the header) |
| `simulation/results/pipeline_status.json` | step-by-step PASS/FAIL of the last run |
| `simulation/plots/*.svg` | 16 labelled plots (trajectory, stability, drag, sensitivity) |
| `documentation/SIMULATION_VALIDATION.md` | full simulation validation report |
| `documentation/ENGINEERING_STATUS.md` | project-wide engineering status |
| `documentation/ASTRA-66_Engineering_Package.html`, `analysis/results/`, `bom/`, `avionics/` | from `build.py` |

**Determinism:** the same inputs give the same numbers. The simulation is a fixed-step RK4 with no random elements,
checked by `tests/test_simulation.py::Reproducibility`. Only the run-date fields in reports change between runs.

## Inputs (the only files to edit)

| File | Holds | Status |
|---|---|---|
| `simulation/motor_config.json` | motor / retainer / MMT data and `thrust_curve_file` | **PLACEHOLDER** |
| `simulation/motors/PLACEHOLDER_TEST_INPUT.eng` | synthetic thrust signal (**not a real motor**) | PLACEHOLDER |
| `simulation/sim_config.json` | launch site, rail length override, drag assumptions, time steps | planning defaults / ASSUMPTION |
| `analysis/analysis.py` | airframe parameters (the CAD reads them too) | see parameter provenance tags |

All inputs are validated. The pipeline stops with an explanatory error in any of these cases:
- a value is out of range;
- `MANUFACTURER_DATA` is claimed without source, verifier and date;
- the placeholder curve is still referenced;
- the `.eng` masses, length or diameter disagree with the config or the MMT bore.

## Modules

| Module | Purpose |
|---|---|
| `flight_simulation.py` | 1-DOF vertical RK4 simulation and pipeline entry point |
| `stability.py` | Barrowman CP re-implemented independently; static margin; requirements REQ-STAB-1..3 |
| `mass_properties.py` | vehicle mass/CG from `analysis/analysis.py` (21 CAD-derived items); data classes A–D |
| `atmosphere.py` | ISO 2533 standard atmosphere |
| `aerodynamics.py` | drag build-up (ASSUMPTION model) |
| `motor.py` | RASP `.eng` reader, impulse-proportional mass, cross-checks |
| `config.py` | `sim_config.json` loader and validator |
| `sensitivity.py` | one-at-a-time non-propulsion sensitivity study |
| `verification.py` | 13 numerical verification checks (closed-form solutions and cross-checks) |
| `plotting.py`, `report.py` | dependency-free SVG plots; JSON/Markdown/CSV writers |

## What depends on placeholder propulsion data

While `motor_config.json` is `PLACEHOLDER`, **every trajectory, acceleration, altitude, apogee, rail-exit speed,
descent-rate and with-motor static-margin value is illustrative only and not representative of any real motor.**

Two things are also affected, less obviously:
- The "no-motor" margin (3.23 cal) excludes the motor, but still contains the placeholder retainer mass and the MMT sized from placeholder data.
- Burn-phase base drag uses the placeholder MMT bore.

The CP and the coast drag model are independent of propulsion data. `flight_summary.json` carries the full map under `placeholder_dependency`.

## Replacing the placeholder with a certified motor

The mentor selects a legally obtainable certified motor. Then:
1. Put the motor's **published** RASP `.eng` file (from the manufacturer or the certifying organisation) in `simulation/motors/`.
2. In `motor_config.json`:
   - set `thrust_curve_file`;
   - copy the published masses, length, diameter and retainer/MMT dimensions;
   - fill in `designation`, `manufacturer`, `certification`, `data_source`, `retainer.model`, `retainer.data_source`, `verification.verified_by` and `verification.date`;
   - set `"status": "MANUFACTURER_DATA"`.
3. Run `python run_validation.py --with-cad --openscad <path>`. This re-sizes the MMT, retainer envelope, lock ring and fin tabs, then re-validates the CAD and re-runs the simulation.
4. Review the regenerated reports with the mentor. Pay particular attention to:
   - rail-exit speed on the range's rail (15 m/s guideline);
   - static margin 1.5–3.0 cal;
   - coast time against the motor's delay options.

## OpenRocket cross-check
Build the OpenRocket model from `simulation/openrocket_inputs.csv`, using weighed masses. Compare its no-motor CG and CP
with `analysis/results/analysis.json` (±10 / ±15 mm). Then compare its drag and apogee with this pipeline for the same
certified motor.
