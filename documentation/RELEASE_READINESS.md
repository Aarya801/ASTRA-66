# ASTRA-66 — Release readiness

> **ASTRA-66 is an educational engineering project and is NOT FLIGHT CERTIFIED.** This report states what the
> repository contains, what has actually been validated, and what has not. It is the freeze record for the first
> public release. Nothing has been built or flown; no avionics hardware has been selected, bought, weighed or tested;
> propulsion is an external, commercially certified component, used here only as placeholder data and handled in
> reality only by a certified person under qualified supervision.

## 1. Project scope

**In scope (and complete for this release)**

- A parametric CAD model of a 66 mm-class, 1144 mm modular student rocket airframe, with validation measured on the
  rendered meshes.
- Non-propulsion engineering analysis: mass budget, CG, Barrowman CP, static margin, structural loads, recovery sizing.
- A 1-DOF flight simulation with stability and sensitivity studies, and its own numerical verification.
- A data-only avionics software framework: sensor interfaces, validation, state estimation, flight-state labelling,
  logging, telemetry, ground-station prototype, post-flight analysis.
- Synthetic datasets and a sensor-replay path that exercises the real processing chain.
- An automated validation pipeline, CI on two Python versions, a checksum manifest, and the documentation set.

**Explicitly out of scope, permanently**

- Design, modification, manufacture or description of motors, propellant, igniters, pyrotechnics or any energetic
  device.
- Any avionics output capable of driving such a device; any autonomous flight-control function.
- Claims of flight certification, flight readiness, or validated hardware performance.

## 2. What is implemented

| Area | Implementation |
|---|---|
| CAD | 25 parametric parts + master assembly; 15 print STLs, 8 DXF + 8 SVG cut profiles, 31 drawing sheets, 4 renders; commercial items as envelopes only |
| Analysis | `analysis/analysis.py` as the single source of truth, every value provenance-tagged; CAD-derived structural masses |
| Simulation | RK4 1-DOF trajectory, ISA atmosphere, drag build-up, stability through flight, 8-parameter sensitivity study, plots and reports |
| Avionics firmware | Sensor interface, schema validation before processing, 2-state Kalman estimator, forward-only flight-state classifier, CSV/JSON-lines logger with CRC-16, telemetry packet v2 with sensor-health bits |
| Ground station | Packet receiver with loss/duplicate/reject statistics, local server, browser dashboard (replay only) |
| Data | Flight-data schema v1.1.0 (23 fields), data-source modes SYNTHETIC / BENCH / FLIGHT, three synthetic datasets, bench-record template |
| Replay | `simulation/avionics_replay.py` drives the real flight-computer code from a recorded dataset |
| Integration checks | CAD fit and avionics mass-properties report generated read-only from the CAD and the analysis |
| Validation | `run_validation.py` (7 steps), 155 automated tests, GitHub Actions on Python 3.12 and 3.14, `MANIFEST.sha256` |
| Documentation | Project overview, engineering method, validation, hardware integration and status, selection checklist, bench-test plan, mass procedure, test plan, reproducibility, roadmap, visual index, architecture diagrams |

## 3. What has been validated

All validation in this release is **computational**: software behaviour, the CAD model, numerical correctness and
documentation integrity. Nothing physical has been measured or tested. The categories below are deliberately kept
apart, because they prove different things.

### 3.1 Computational validation (the pipeline as a whole)

`python run_validation.py` runs seven steps and ends with `OVERALL: PASS`. It rebuilds the engineering package from
the parameters, checks the CAD is current, re-runs the simulation, replays a synthetic sensor dataset through the
flight-computer code, regenerates the CAD-fit and mass report, and runs both test suites. `MANIFEST.sha256`
checksums every tracked file, so the committed artefacts are provably the ones the pipeline produced.

*Proves:* the repository is internally consistent and reproducible from its sources.
*Does not prove:* anything about physical hardware or flight.

### 3.2 Software tests (155 automated tests)

| Suite | Count | Scope |
|---|---|---|
| Project regression (`tests/`) | 74 | Package outputs match the committed ones; CAD data consistency; simulation results and placeholder flags; documentation references; avionics integration (packets, CRC, sequence handling, sensor validity, missing GPS, impossible values, barometric conversion, estimator, state transitions, logging, replay, data-source modes) |
| Avionics software (`avionics/tests/`) | 81 | Schema validation, sensor scheduling and fault injection, timestamp wrap/duplicate/gap handling, damaged log files, flight-state classification against synthetic truth, telemetry encode/decode and corruption rejection, logging formats, analysis mathematics, ground-station server, and the safety-boundary scan |

All tests run without hardware, on synthetic data only. No test was ever relaxed to make a build pass.

*Proves:* the software behaves as specified on synthetic inputs, including its failure paths.
*Does not prove:* that any sensor, radio, storage device or the vehicle works.

### 3.3 CAD integration checks (147 PASS · 12 accepted WARN · 0 FAIL)

Measured on the **rendered meshes**, not asserted from drawings: closed-manifold geometry, volumes and centroids,
44 interference pairs (0 interferences), 11 interface checks, assembly feasibility (sled removal, joint separation,
fin removal with the retainer fitted, motor-envelope insertion), printability and wall thickness, electronics-envelope
fit, and 15 dimensions cross-checked against the analysis. A full OpenSCAD 2021.01 re-render reproduces the same
result and the same geometry (volumes agree to about 1e-14 relative), though export files are not byte-identical.

The separate CAD-fit and mass-properties check reports **11 PASS · 4 WARN · 8 UNVERIFIED · 0 FAIL**, and recomputes
the centre of gravity from the mass budget independently of the analysis: the two agree exactly.

*Proves:* the model is geometrically consistent and assemblable **as modelled**, with placeholder envelopes.
*Does not prove:* that real parts fit, because no real part has been measured.

### 3.4 Simulation verification (13/13 checks)

The simulation is checked against independent references, not merely executed: ISA density at two altitudes and the
speed of sound, thrust-curve impulse by fine quadrature, motor mass after burnout, burnout altitude and apogee for a
constant-thrust drag-free case (closed form), parachute terminal velocity, time-step convergence, liftoff mass and CG
against the analysis, an independent Barrowman CP on CAD-measured geometry, and a drag-coefficient plausibility band.

*Proves:* the trajectory code solves the equations correctly.
*Does not prove:* that the trajectory is what the vehicle would fly — the motor data are placeholders, so every
altitude, speed and acceleration figure is illustrative.

### 3.5 Avionics replay checks

A deterministic synthetic sensor dataset (2162 rows at 50 Hz, with five scripted faults) is replayed through exactly
the code a flight computer would run. All four flight events are detected close to the known truth; the three
impossible values (non-finite acceleration, 250 kPa pressure, 9.9 V battery) are rejected before processing and
flagged in the log; the GNSS dropout and the silent temperature sensor are reported stale and then recover;
telemetry packets are produced, corrupted packets rejected and lost packets counted.

*Proves:* the processing chain handles good and bad data as designed.
*Does not prove:* anything about real sensors — the data are generated.

### 3.6 Documentation and link checks

Automated: every file path quoted in the documentation exists, the required disclaimers are present, and documents
are checked for unqualified claims about measurements or selected hardware. Repository-wide: all Markdown links
resolve, and every command quoted in the README and the reproducibility guide maps to a real script and flag.

*Proves:* the documentation matches the repository and makes no unsupported claim.

### 3.7 Continuous integration

GitHub Actions runs the same `python run_validation.py` on **Python 3.12 and 3.14** for every push and pull request,
uploads the status artefacts, and drives the README badge. A green badge therefore means the whole computational
pipeline passed on a clean machine — not that any hardware was tested.

### 3.8 What none of this establishes

No physical validation has taken place: no component measured or weighed, no bench test, no radio link, no recovery
deployment, no motor performance and no flight. Those items are listed individually in §4 and classified in
`HARDWARE_INTEGRATION_STATUS.md`. ASTRA-66 remains **NOT FLIGHT CERTIFIED**.

## 4. What has *not* been validated

- **Propulsion:** motor data are placeholders. Every trajectory value and any margin including the motor is
  provisional. No motor has been selected, and none is designed here.
- **Hardware:** no microcontroller, IMU, barometer, GNSS, temperature sensor, battery monitor, battery, regulator,
  storage, radio or annunciator has been selected, bought, measured, weighed or tested.
- **Physical fit:** real board outlines, wiring, connectors, antenna routing, bay sealing, SD and battery access —
  eight open items requiring measurement.
- **Masses and CG:** every avionics mass is an estimate; nothing has been weighed; no balance measurement exists.
- **Structures:** hand calculations with conservative allowables only; no FEA, no coupon tests.
- **Aerodynamics:** uncalibrated drag build-up; no wind-tunnel or flight data; 1-DOF model without wind,
  weathercocking or dynamic stability.
- **Recovery:** never deployed or drop-tested.
- **Radio:** range, link margin and legality not assessed.
- **Ground station:** never run against a real radio; real-time performance not demonstrated.
- **Flight:** nothing has flown.

Full item-by-item classification: `HARDWARE_INTEGRATION_STATUS.md`; evidence and gaps: `VALIDATION.md`.

## 5. Known engineering limitations (carried into the release)

1. Placeholder propulsion data throughout.
2. Rail-exit speed 11.7 m/s on the 1.0 m planning rail, below the 15 m/s guideline (placeholder input).
3. Payload margin limit: about 100 g extra in the payload bay pushes the static margin above 3.0 calibres.
4. Four open CAD integration warnings: incomplete electronics envelopes (buzzer, LED, regulator, temperature sensor,
   battery divider, wiring); IMU placeholder 20.5 mm off the roll axis; steel M4 rods beside the radio envelope;
   0.40 mm sled-removal margin on placeholder envelopes.
5. Twelve accepted CAD warnings: 11 printed parts need support in the documented pose; the hatch panel wall is 1.0 mm.
6. Barometric altitude is biased above an elevated pad (≈1.1 % at 500 m); the planning site is at 0 m.
7. State-transition thresholds, filter tuning and sensor requirements are assumptions checked only on synthetic data.
8. Printability judged by a 45° overhang rule, not in a slicer.
9. Generated reports carry their run date; a CAD re-render reproduces the same geometry but not byte-identical files.

## 6. Safety boundaries held in this release

- No propulsion, propellant, igniter, pyrotechnic or energetic-device content of any kind.
- The avionics sense, log and transmit only. No actuator or deployment output exists, and a test fails the build if an
  actuation-style identifier or hardware-I/O import appears in the avionics code.
- Recovery relies on the certified motor's own ejection, prepared by a mentor.
- Telemetry radio use requires a legal band and power level and range frequency coordination.
- `FLIGHT` data mode is disabled in software; synthetic and bench data can never be presented as flight data.
- The NOT FLIGHT CERTIFIED statement appears in the README, the engineering status and every avionics document.

## 7. Release contents and reproducibility

| Item | Value |
|---|---|
| Tracked files | 281 |
| Repository content | about 21 MB (CAD exports, drawings, plots and datasets committed so the work can be reviewed without OpenSCAD) |
| Automated tests | 155 (74 project regression + 81 avionics software) |
| CI | GitHub Actions, Python 3.12 and 3.14, on every push and pull request; badge in the README |
| One-command validation | `python run_validation.py` → `OVERALL: PASS` |
| Checksums | `MANIFEST.sha256` over every tracked file |
| Licence | MIT, with the project safety notice retained |

Guide: `REPRODUCIBILITY.md`.

## 8. Release checklist

| Item | Status |
|---|---|
| Full pipeline passes from a clean copy | Yes |
| CAD re-render reproduces the committed validation | Yes (OpenSCAD 2021.01) |
| All documentation links and quoted paths resolve | Yes |
| Documented commands exist and run | Yes |
| No secrets, credentials, private links or local paths | Yes |
| No caches, temporary files or session artefacts tracked | Yes |
| No duplicate or orphaned files | Yes |
| Placeholder and synthetic data labelled everywhere | Yes |
| No hardware presented as selected, measured or tested | Yes |
| NOT FLIGHT CERTIFIED statement present and prominent | Yes |
| Engineering limitations documented | Yes (§5) |
| Manifest regenerated and verified | Yes |

## 9. Position of this release

ASTRA-66 is released as a **design, software and validation project**: a complete, reproducible engineering pipeline
with honest labelling of what is verified, assumed, placeholder and unknown. It is not a flight-ready vehicle, not a
validated avionics product, and not a source of flight performance data.

The next stage is physical and begins with mentor-approved component selection and measurement, followed by bench
testing (`ROADMAP.md`, `TEST_PLAN.md`, `HARDWARE_SELECTION_CHECKLIST.md`). Any flight activity would require a
qualified rocketry mentor or institution, a legally obtained certified motor handled by a certified person, a
complete flight-readiness review and range safety officer approval.
