# ASTRA-66 — Project overview

> **Educational engineering project. NOT FLIGHT CERTIFIED.** Nothing here has flown, no avionics hardware has been
> selected, built, weighed or tested, and propulsion is an external, commercially certified component that is never
> designed in this repository (its data are placeholders). Every avionics dataset is synthetic.

![ASTRA-66 system architecture](images/astra66_system_architecture.svg)

## 1. What ASTRA-66 is

ASTRA-66 is a 66 mm-class, 1144 mm modular student rocket airframe developed as a complete engineering project:
a parametric CAD model, a non-propulsion engineering analysis, a flight simulation, an avionics and flight-data
software framework, and an automated validation pipeline that ties them together. It is a **design and software
project**: the vehicle has not been built.

The repository is meant to be read as engineering work, not as a product. Every number carries its provenance, and
results that depend on assumptions or placeholders say so.

## 2. The engineering problem

Design a student-buildable rocket airframe that:

- stays statically stable through the flight (target 1.5–3.0 calibres of static margin);
- can be manufactured with a hobby FDM printer, laser-cut plywood and purchased tube stock;
- carries a data-only avionics payload (sensing, logging, telemetry) with **no** connection to anything energetic;
- uses an external, commercially certified motor chosen and handled by a qualified mentor;
- and can be checked automatically, so that a change to one parameter re-validates the whole design.

The hard part for a student project is not drawing the rocket: it is keeping analysis, CAD, simulation and software
consistent, and being honest about which numbers are verified, assumed or placeholders.

## 3. System architecture

| Layer | What it does | Where |
|---|---|---|
| Parameters | Single source of truth: geometry, materials, masses, with a provenance tag on every value | `analysis/analysis.py` |
| CAD | Parametric OpenSCAD model driven by the generated parameter file; exports meshes, cut files and drawings | `cad/` |
| Analysis | Mass budget, CG, Barrowman CP, static margin, loads, recovery sizing | `analysis/` |
| Simulation | 1-DOF trajectory, stability, sensitivity, numerical verification | `simulation/` |
| Avionics software | Sensor interface → validation → state estimation → flight state → logging and telemetry | `avionics/firmware/` |
| Ground station | Packet receiver, link statistics, browser dashboard (prototype, replay only) | `avionics/ground_station/` |
| Analysis of flight data | Tolerant log reader, plots, derived statistics | `avionics/analysis/` |
| Validation | One command that rebuilds, re-checks and tests everything; runs in CI | `run_validation.py` |

## 4. Software architecture

The avionics software is layered so that each layer talks to an interface, not to hardware:

```
Sensor (interface)  →  validation against the data schema  →  Kalman vertical-state estimator
                    →  flight-state classifier (labels only)  →  data logger (CSV/JSONL + CRC-16)
                                                              →  telemetry packet v2 → link → ground station
```

- Today the sensors are **simulated** or **replayed** from a recorded dataset; a real driver would implement the same
  `Sensor` interface, and nothing above it would change.
- The flight state is a **data label**. There is no actuator interface, and a test fails the build if an
  actuation-style identifier or a hardware-I/O import appears in the avionics code.
- Data carry a mode: `SYNTHETIC`, `BENCH` or `FLIGHT`. `FLIGHT` is disabled in software because no flight record
  exists.

Details: `AVIONICS_ARCHITECTURE.md`, `AVIONICS_DESIGN.md`, `../avionics/DATA_FORMAT.md`.

## 5. CAD workflow

1. `analysis/analysis.py` computes the geometry and writes `cad/astra66_params.scad`.
2. `cad/build_cad.py` renders the master assembly and every part with OpenSCAD, then measures the **rendered meshes**:
   volumes, centroids, bounding boxes, manifold checks, interference, assembly feasibility (for example whether the
   sled still slides out, or whether a fin can be removed with the retainer fitted).
3. It exports print and cut files, generates drawing sheets from true mesh sections, and writes
   `CAD_VALIDATION.md` plus a machine-readable validation record.
4. CAD-derived masses are handed back to the analysis, so the mass budget uses measured mesh volumes rather than
   hand estimates.

Current result: **147 PASS, 12 accepted WARN, 0 FAIL, 0 interferences**.

## 6. Simulation workflow

`simulation/flight_simulation.py` integrates a 1-DOF vertical trajectory (RK4, ISA atmosphere, drag build-up),
computes stability through the flight, runs a sensitivity study, and writes plots and reports. A separate
verification module checks the code against closed-form solutions and independent calculations: **13/13 checks pass**.

The motor is external data (`simulation/motor_config.json`). Its status is `PLACEHOLDER`, so the trajectory numbers
demonstrate the software and the sensitivities — they are **not predictions**.

## 7. Avionics and data workflow

1. A sensor source (simulated, or a recorded dataset replayed through `simulation/avionics_replay.py`) produces
   samples.
2. Every value is validated against the schema before processing: NaN, unparseable and out-of-range values never
   reach the estimator.
3. The estimator and classifier produce altitude, vertical velocity, flight state and events.
4. The logger writes schema-conformant CSV rows with a CRC-16 per row; the telemetry layer emits 41-byte packets with
   sequence numbers, CRC and sensor-health bits.
5. The ground station decodes packets, counts loss and shows the data; the post-flight tool re-reads a log tolerantly
   and produces plots and statistics.

## 8. Validation methodology

- **One command** (`python run_validation.py`) runs seven steps: package build, CAD currency (or a full re-render),
  simulation, sensor replay, CAD-fit and mass check, project regression tests, avionics software tests.
- **CI** runs the same command on Python 3.12 and 3.14 for every push and pull request.
- **Checksums** (`MANIFEST.sha256`) cover every tracked file.
- **Reproducibility** is a design rule: standard library only, deterministic formats, seeded synthetic data, no dates
  inside data files.

What this does and does not show is spelled out in `VALIDATION.md`.

## 9. Current limitations

- Propulsion data are placeholders; every trajectory value and any margin that includes the motor is provisional.
- No avionics hardware has been selected, built, weighed or tested; all avionics masses are estimates.
- Rail-exit speed (11.7 m/s with the placeholder motor) is below the usual 15 m/s guideline on the 1.0 m planning rail.
- Four CAD integration warnings remain (incomplete electronics envelopes, IMU placeholder off the roll axis, metal
  beside the radio, a 0.40 mm sled-removal margin), plus eight items that need physical measurement.
- The drag model is uncalibrated; the flight model is 1-DOF (no wind, weathercocking or dynamic stability).
- Structures rest on hand calculations with conservative allowables: no FEA, no coupon tests.
- Nothing physical has been verified. See `HARDWARE_INTEGRATION_STATUS.md` for the complete classification.
