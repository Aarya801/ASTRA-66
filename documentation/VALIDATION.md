# ASTRA-66 — What is validated, and what is not

> **NOT FLIGHT CERTIFIED.** Everything below is software, CAD-model and numerical validation. No physical test,
> measurement or flight has taken place. Propulsion is an external, commercially certified component; its data here
> are placeholders, so every trajectory number is illustrative.

## 1. The one command

```bash
python run_validation.py          # add --with-cad --openscad <path> to re-render the CAD as well
```

| # | Step | What it proves | Current result |
|---|---|---|---|
| 1 | Engineering package build | The parameters, mass budget, BOM, drawings and package regenerate from `analysis/analysis.py` | PASS |
| 2 | CAD integration | The committed CAD validation matches every current `.scad` source and parameter (hash check); with `--with-cad` the model is re-rendered and re-measured | PASS — 147 PASS · 12 accepted WARN · 0 FAIL |
| 3 | Flight simulation | Trajectory, stability and sensitivity regenerate; numerical verification passes | PASS — 13/13 checks |
| 4 | Avionics sensor replay | A recorded sensor dataset runs through the real flight-computer pipeline and produces the expected events and validity | PASS |
| 5 | CAD fit and mass properties | Electronics envelopes fit the CAD; the CG recomputed from the mass budget matches the analysis | PASS — 11 PASS · 4 WARN · 8 UNVERIFIED · 0 FAIL |
| 6 | Project regression tests | 74 tests: package, CAD data, simulation, documentation, avionics integration | PASS |
| 7 | Avionics software tests | 81 tests: sensors, timestamps, corrupted data, state machine, telemetry, logging, analysis, safety boundary | PASS |

GitHub Actions runs exactly this on Python 3.12 and 3.14 for every push and pull request.

## 2. Automated tests (155 total)

| Suite | Count | Covers |
|---|---|---|
| `tests/` project regression | 74 | Package build outputs match the committed ones; CAD data consistency; simulation results and placeholder flags; documentation references and disclaimers; avionics integration (packets, CRC, sequence handling, sensor validity, missing GPS, impossible values, barometric conversion, estimator, state transitions, log format, replay, data-source modes, bench template, Phase 6 documents) |
| `avionics/tests/` | 81 | Schema validation, sensor scheduling and fault injection, timestamp wrap/duplicates/gaps, damaged log files, flight-state classification against a synthetic truth, telemetry encode/decode and corruption, logging formats and metadata, post-flight analysis mathematics, architecture and safety-boundary checks, ground-station server |

Two habits keep these meaningful: no test was ever relaxed to make a build pass, and the safety boundary is enforced
by a test that scans every avionics source for actuation-style identifiers and hardware-I/O imports.

## 3. CAD checks (what the model actually shows)

Measured on the **rendered meshes**, not on drawings:

- closed-manifold geometry for every part; volumes, centroids, bounding boxes;
- interference across 44 part pairs (0 interferences) and 11 interface checks;
- assembly feasibility: sled removal, nose removal, joint separation, motor insertion, fin removal with the retainer
  fitted (a real defect was found and fixed this way in an earlier revision);
- printability (overhang area, bed fit) and wall thicknesses;
- electronics: sled stack radius vs coupler bore, battery width, GPS under the hatch, switch reach;
- 15 dimensions cross-checked against the analysis.

Result: 147 PASS, 12 accepted WARN (support-needing prints, one 1.0 mm hatch wall), 0 FAIL. A full re-render with
OpenSCAD 2021.01 reproduces the same result and geometry (volumes agree to ~1e-14 relative), though the exported
files are not byte-identical (float formatting and the render date).

## 4. Simulation checks

13 numerical verification checks, each comparing the simulation against something independent:

ISA density at 0 m and 11 km, ISA speed of sound, thrust-curve impulse by fine quadrature, motor mass after burnout,
burnout altitude and apogee for a constant-thrust drag-free case (closed form), parachute terminal velocity,
time-step convergence, liftoff mass and CG against the analysis, CP by an independent Barrowman calculation on
CAD-measured geometry, and a drag-coefficient plausibility band.

These verify the **software**. They do not validate the vehicle's real behaviour, and with placeholder propulsion the
trajectory itself is not a prediction.

## 5. Avionics replay checks

A deterministic synthetic sensor dataset (2162 rows, 50 Hz, with five scripted faults) is replayed through the same
flight-computer code that would run on hardware:

- all four flight events detected close to the known truth (liftoff +0.02 s, apogee within 0.01 s and 0.04 m, landing
  −0.18 s);
- the three impossible values (NaN acceleration, 250 kPa pressure, 9.9 V battery) are rejected before processing and
  flagged in the log;
- the GNSS dropout and the silent temperature sensor show as stale and then recover;
- telemetry packets are produced, corrupted packets are rejected, and lost packets are counted.

## 6. What is **not** validated

| Area | Status |
|---|---|
| Any sensor, microcontroller, radio, battery or storage device | No component selected; nothing bought, measured or tested |
| Physical fit of real boards, wiring, connectors, antenna | UNVERIFIED — needs measurement (8 open items) |
| Masses and centre of gravity | All avionics masses are estimates; nothing has been weighed |
| Motor performance, thrust curve, ejection | Placeholder data; the real motor is a mentor's selection |
| Recovery deployment, parachute descent | Never tested |
| Structural strength | Hand calculations only; no FEA, no coupon tests |
| Aerodynamic drag | Uncalibrated build-up; no wind-tunnel or flight data |
| Radio range, link margin, legality | Not assessed |
| Real-time ground-station behaviour | Prototype on replayed data only |
| Flight behaviour of the vehicle | Nothing has flown |

Full classification: `HARDWARE_INTEGRATION_STATUS.md`. Planned physical work: `TEST_PLAN.md` and
`AVIONICS_BENCH_TEST_PLAN.md`.
