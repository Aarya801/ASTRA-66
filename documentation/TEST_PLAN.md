# ASTRA-66 — Test plan (master index)

> What is tested today, and what is planned but **not performed**. No physical test, bench measurement or flight has
> taken place; no result below is invented. Propulsion is an external, commercially certified component and is not
> tested here in any form. ASTRA-66 is NOT FLIGHT CERTIFIED.

Status vocabulary: **DONE** (automated, reproducible, in CI) · **PLANNED** (written down, not performed) ·
**BLOCKED** (needs hardware or a qualified mentor first).

## 1. Software tests — DONE (155 automated tests)

| Group | Where | Examples of what is checked |
|---|---|---|
| Package and data consistency | `tests/test_export.py`, `tests/test_cad.py` | Rebuilt outputs match the committed ones; CAD data and drawings are consistent and parse |
| Simulation | `tests/test_simulation.py` | Verification checks pass; placeholder status is flagged in the results |
| Documentation | `tests/test_docs.py` | Every quoted file path exists; disclaimers present in the key documents |
| Avionics integration | `tests/test_avionics.py` | Packet encode/decode, CRC, every single-bit corruption rejected, sequence and loss accounting, sensor validity and staleness, missing GPS, impossible values, barometric conversion, estimator behaviour, state transitions, logging format, replay of recorded data, data-source modes, bench template, documentation claims |
| Avionics software | `avionics/tests/` (8 modules) | Schema validation, sensor scheduling and fault injection, timestamp wrap/duplicate/gap, damaged log files, classifier against synthetic truth, telemetry, logging, analysis mathematics, ground-station server, and the safety-boundary scan |

Run: `python -m unittest discover -s tests` and `python -m unittest discover -s avionics/tests -t .`

## 2. CAD checks — DONE (147 PASS · 12 accepted WARN · 0 FAIL)

Measured on the rendered meshes: manifold geometry, volumes and centroids, 44 interference pairs, 11 interface
checks, assembly feasibility (sled removal, joint separation, fin removal with the retainer fitted, motor insertion),
printability and wall thickness, electronics fit, and 15 dimensions cross-checked against the analysis.

Run: `python run_validation.py --with-cad --openscad <path>` (needs OpenSCAD 2021.01; the default run verifies that
the committed validation is still current).

The 12 warnings are accepted and documented: 11 printed parts need support in the chosen pose, and the hatch panel
wall is 1.0 mm (0.25 mm nozzle recommended).

## 3. Simulation checks — DONE (13/13)

Closed-form and independent cross-checks: ISA density and speed of sound, impulse quadrature, motor mass after
burnout, constant-thrust burnout altitude and apogee, parachute terminal velocity, time-step convergence, liftoff
mass and CG against the analysis, independent Barrowman CP, and a drag plausibility band.

These verify the software. With placeholder propulsion the trajectory is illustrative, not a prediction.

## 4. Avionics replay checks — DONE

A synthetic sensor dataset with five scripted faults is replayed through the real pipeline: events detected close to
the known truth, impossible values rejected before processing, sensor staleness and recovery observed, telemetry
generated, corrupted packets rejected, lost packets counted.

Run: `python simulation/avionics_replay.py`

## 5. Bench tests — PLANNED / BLOCKED (no hardware exists)

Fourteen electronics-and-software tests, B-01…B-14, are specified in `AVIONICS_BENCH_TEST_PLAN.md`: power-up,
sensor detection, IMU sanity, pressure sanity, GNSS acquisition, data logging, packet generation, packet integrity,
ground-station link, packet-loss handling, timestamp consistency, battery monitoring, long-duration logging,
power-down data preservation.

Blocked until components are selected with a mentor (`HARDWARE_SELECTION_CHECKLIST.md`). Each test records raw data
as `BENCH` with a meta file (`../avionics/bench_data/README.md`) and is processed by the same software as synthetic
data, so bench and simulation results can be compared directly.

## 6. Hardware integration tests — PLANNED / BLOCKED

After the bench phase, still without flying:

| Test | Purpose |
|---|---|
| Physical fit | Real boards, wiring and connectors in the printed sled and bay; sled removal margin re-checked |
| Mass and CG | Weigh every item and each module; measure the vehicle CG (`MASS_MEASUREMENT_PROCEDURE.md`) |
| Structural fit coupons | Printed shoulder, fin guide slot and heat-set inserts |
| Bay sealing | Static-port response and leak behaviour with the selected barometer |
| Harness | Continuity, strain relief, connector passage through the ⌀8 mm grommet |
| Separation sense | Breakwire continuity and logging when the joint is separated by hand |
| Hardware-in-the-loop | Bench data replayed against the simulation; estimator and classifier behaviour compared |
| Pipeline re-validation | Update the CAD envelopes and masses, re-run `run_validation.py --with-cad` |

## 7. Supervised physical testing — BLOCKED (mentor and range)

Not a software decision and not planned in detail here. It requires, at minimum: a legally obtainable certified motor
selected and handled by a certified person; its published data replacing the placeholders, with the stability and
rail-exit checks redone; recovery hardware proof loads; a complete flight-readiness review; and range safety officer
approval on the day. Radio operation needs a legal band and power and range frequency coordination.

Nothing in this repository authorises or describes motor preparation, ignition or any energetic device.

## 8. Current results summary

| Category | Status | Evidence |
|---|---|---|
| Software tests | 155 pass | CI on Python 3.12 and 3.14 |
| CAD checks | 147 PASS · 12 WARN · 0 FAIL | `CAD_VALIDATION.md` |
| Simulation checks | 13/13 | `SIMULATION_VALIDATION.md` |
| Replay checks | pass | `simulation/results/avionics_replay/replay_events.json` |
| CAD fit / mass check | 11 PASS · 4 WARN · 8 UNVERIFIED · 0 FAIL | `CAD_AVIONICS_INTEGRATION.md` |
| Bench tests | **not performed** | — |
| Hardware integration tests | **not performed** | — |
| Flight testing | **not performed** | — |
