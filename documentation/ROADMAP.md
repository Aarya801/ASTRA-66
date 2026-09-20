# ASTRA-66 — Engineering roadmap

> No dates: this is a student project and the next stages depend on a mentor, on parts and on range access. Stages
> are ordered by dependency, not by calendar. ASTRA-66 is **NOT FLIGHT CERTIFIED**, and propulsion remains an
> external, commercially certified component throughout.

## COMPLETED (in the repository, reproducible, in CI)

| Item | Evidence |
|---|---|
| Engineering package: requirements, parameters with provenance, BOM, drawings, checklists | `ASTRA-66_Engineering_Package.html`, `analysis/results/`, `bom/` |
| Parametric CAD: 25 parts + master assembly, exports, 32 drawing sheets | `cad/`, `CAD_VALIDATION.md` — 147 PASS · 12 WARN · 0 FAIL |
| Engineering analysis: mass budget, CG, Barrowman CP, static margin, loads, recovery | `analysis/`, cross-checked in `CAD_AVIONICS_INTEGRATION.md` |
| Flight simulation: 1-DOF trajectory, stability, sensitivity, 13/13 verification checks | `simulation/`, `SIMULATION_VALIDATION.md` |
| Avionics software architecture: sensor interface, validation, estimator, flight-state logic, logging, telemetry | `avionics/firmware/`, `AVIONICS_DESIGN.md`, `AVIONICS_ARCHITECTURE.md` |
| Ground-station prototype and post-flight analysis tool | `avionics/ground_station/`, `avionics/analysis/` |
| Synthetic data and sensor replay through the real pipeline | `simulation/avionics_replay.py`, `simulation/data/sample_flight.csv` |
| Data-source modes SYNTHETIC / BENCH / FLIGHT, with FLIGHT disabled | `avionics/firmware/data_source.py` |
| CAD ↔ avionics fit and mass-properties integration check | `CAD_AVIONICS_INTEGRATION.md` |
| Automated validation: one command, 7 steps, 155 tests, checksum manifest | `run_validation.py`, `VALIDATION.md` |
| GitHub Actions on Python 3.12 and 3.14, with a status badge | `.github/workflows/validation.yml` |
| Hardware-integration readiness review, selection checklist, bench plan, mass procedure | `HARDWARE_INTEGRATION_STATUS.md` and the Phase 6 documents |

## NEXT PHYSICAL STAGE (nothing here has started)

1. **Mentor-approved hardware selection** — work through `HARDWARE_SELECTION_CHECKLIST.md` subsystem by subsystem,
   recording the part and its datasheet. Start with the microcontroller, IMU and barometer, because the buses and
   voltage decide the rest. Radio choice must satisfy local band and power law.
2. **Physical component measurement** — measure each board with headers and connectors; weigh every item on a 0.1 g
   scale (`MASS_MEASUREMENT_PROCEDURE.md`). Also measure the purchased tube, coupler and motor-tube stock.
3. **CAD envelope update** — replace the placeholder envelopes in `cad/parts/COTS_envelopes.scad` with the measured
   sizes, resolve the four open warnings (envelope completeness, IMU position relative to the roll axis, antenna
   routing past the steel rods, sled-removal margin), and re-run the CAD validation with OpenSCAD.
4. **Mass and CG update** — enter the measured masses into `analysis/analysis.py`, re-run the pipeline, and compare
   the recomputed CG with a measured balance-point CG.
5. **Bench testing** — B-01…B-14 in `AVIONICS_BENCH_TEST_PLAN.md`: power-up, sensor detection, IMU and pressure
   sanity, GNSS acquisition, logging, packets, link, timestamps, battery, endurance, power-loss behaviour.
6. **Real sensor data collection** — record bench data as `BENCH`, with a meta file, and replay it through the same
   software (`avionics/bench_data/README.md`).

## FUTURE (after the bench stage, in this order)

- **Hardware-in-the-loop validation** — drive the flight-computer software from the real sensors on the bench,
  including fault injection (disconnect a sensor, pull power mid-log) and confirm the health, validation and CRC
  behaviour that is currently only shown on synthetic data.
- **Experimental data comparison** — compare measured sensor noise, timing and endurance against the assumptions in
  `avionics/firmware/sensor_interfaces/catalog.py`, and re-derive the state-transition thresholds from real data.
- **Certified motor data** — once a mentor selects a legally obtainable certified motor, replace the placeholder
  thrust curve with its published data and re-run the stability, rail-exit and trajectory analysis.
- **Supervised range testing, where legally and organisationally appropriate** — only under a qualified rocketry
  mentor or institution, with a complete flight-readiness review and range safety officer approval. Motor handling
  and preparation are done by a certified person; this repository never describes them.
- **Post-flight comparison** — if a supervised flight ever happens, enable the `FLIGHT` data mode for that record and
  compare measured altitude, velocity and events against the simulation with the existing analysis tool.

## Explicitly out of scope, permanently

Designing, modifying or manufacturing motors, propellant, igniters, pyrotechnics or any energetic device; any
avionics output able to drive one; autonomous flight control. The avionics sense, log and transmit — nothing else.
