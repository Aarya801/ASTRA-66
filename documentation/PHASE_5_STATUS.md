# ASTRA-66 — Phase 5 status: avionics integration and hardware-agnostic verification

> **NOT FLIGHT CERTIFIED. Draft student engineering design.** Phase 5 is software, documentation and read-only checks
> against the existing CAD and analysis. No avionics hardware has been selected, built, weighed or tested; no sensor,
> radio, parachute deployment or motor performance has been validated; no flight has taken place. Every avionics
> dataset is SIMULATED or synthetic. Propulsion remains an external, commercially certified component represented only
> by the existing PLACEHOLDER data. The avionics have no actuator, igniter, pyrotechnic, energetic-device or deployment
> output and no autonomous flight-control function.

## 1. What was implemented

| Item | Result |
|---|---|
| 1. Avionics audit | `documentation/AVIONICS_ARCHITECTURE.md`: block diagram and audit of 15 items. Found and fixed: invalid-but-finite sensor values could reach the estimator; telemetry could not show a silent sensor. Documented: barometric-altitude bias above an elevated pad, IMU placement conflict, no central configuration file |
| 2. Hardware map | `avionics/HARDWARE_MAPPING.md`: every logical component → generic hardware class, existing candidate classes kept, Required / Optional / Prototype assumption / Needs bench validation / Needs flight/range approval, interface-requirement shortlist. No part selected |
| 3. Data model | `avionics/DATA_FORMAT.md`: onboard log, replay input and outputs, telemetry packet v2; units, decimals, expected ranges, validation limits, validity flags, determinism rules |
| 4. Testing | `tests/test_avionics.py`: 23 integration tests on synthetic data at the end of Phase 5 (34 today) (packets, CRC, corruption, sequence, validity, missing GPS, impossible values, altitude conversion, estimator, state transitions, log format, replay) |
| 5. Sensor replay | `simulation/avionics_replay.py` + deterministic synthetic dataset `simulation/data/sample_flight.csv` (2162 rows, 50 Hz, 5 scripted faults); outputs in `simulation/results/avionics_replay/` |
| 6. Ground-station view | existing dashboard extended: sensor health, GPS status, battery status, packet count and loss, flight state, latest telemetry time; new `--sensors` replay source. Simulation / replay only |
| 7. CAD ↔ avionics | `avionics/integration/cad_mass_integration.py` → `documentation/CAD_AVIONICS_INTEGRATION.md` (read-only against the CAD) |
| 8. Mass properties | avionics mass table `avionics/integration/avionics_mass_properties.csv` (component, mass, source, location, confidence, CG and margin effect); CG recomputed from the mass budget and confirmed equal to the analysis. No mass changed (nothing has been weighed) |
| 9. Pipeline | `run_validation.py` gains the replay and the CAD / mass check (7 steps); GitHub Actions runs it unchanged |

Software changes to existing Phase 4 code (integration fixes, no redesign): validation of every sample against the
schema before processing, per-sensor health, telemetry packet v2 (health bits in previously unused flag bits; v1 still
decodes), receiver loss percentage and latest time, dashboard status panel. The Phase 4 example telemetry capture was
regenerated in the v2 format; the example flight log and all analysis outputs are byte-identical to Phase 4.

## 2. Files

**Added (16):**

- `documentation/AVIONICS_ARCHITECTURE.md`
- `documentation/PHASE_5_STATUS.md`
- `avionics/HARDWARE_MAPPING.md`
- `avionics/DATA_FORMAT.md`
- `avionics/integration/__init__.py`
- `avionics/integration/cad_mass_integration.py`
- `documentation/CAD_AVIONICS_INTEGRATION.md`
- `avionics/integration/avionics_mass_properties.csv`
- `simulation/avionics_replay.py`
- `simulation/data/sample_flight.csv`
- `simulation/data/sample_flight.meta.json`
- `simulation/results/avionics_replay/replay_estimates.csv`
- `simulation/results/avionics_replay/replay_events.json`
- `simulation/results/avionics_replay/replay_log.csv`
- `simulation/results/avionics_replay/replay_telemetry.csv`
- `tests/test_avionics.py`

**Changed:**

- Code: `avionics/firmware/flight_computer.py`, `avionics/firmware/telemetry/packet.py`,
  `avionics/ground_station/receiver.py`, `avionics/ground_station/server.py`,
  `avionics/ground_station/dashboard/index.html`, `run_validation.py`, `avionics/tests/test_architecture.py`
  (checks extended to the new documents and the replay script).
- Data: `avionics/data/example/example_flight_simulated_telemetry_capture.csv` (packet v2).
- Documentation: `README.md`, `avionics/README.md`, `avionics/ground_station/README.md`, `avionics/firmware/README.md`,
  `avionics/architecture/system_architecture.md`, `avionics/architecture/data_flow.md`,
  `avionics/architecture/interface_spec.md`, `avionics/architecture/avionics_block_diagram.svg`,
  `documentation/AVIONICS_DESIGN.md`.
- Generated: `documentation/ENGINEERING_STATUS.md`, `simulation/results/pipeline_status.json`, `MANIFEST.sha256`.

**Not changed:** every CAD source and export, `analysis/analysis.py` and its results, the flight simulation and its
results, the motor configuration, the BOM.

## 3. Tests executed and results

| Step (`python run_validation.py`) | Result | Detail |
|---|---|---|
| Engineering package build | PASS | |
| CAD integration | PASS | committed CAD validation current: 147 PASS · 12 WARN (accepted, unchanged) · 0 FAIL |
| Flight simulation | PASS | 13/13 numerical verification checks (PLACEHOLDER propulsion) |
| Avionics sensor replay | PASS | 4 flight events detected; 3 invalid samples rejected; 217 telemetry packets |
| CAD fit and mass-properties check | PASS (no FAIL) | 11 PASS · 4 WARN · 8 UNVERIFIED — PHYSICAL MEASUREMENT REQUIRED · 0 FAIL |
| Regression tests (`tests/`) | PASS | 63 tests at the end of Phase 5 (40 existing + 23 in `tests/test_avionics.py`), incl. documentation checks; Phase 6 added 11 more (74 today) |
| Avionics software tests (`avionics/tests/`) | PASS | 81 tests |
| Checksum manifest | PASS | every tracked file matches `MANIFEST.sha256` (checked after regeneration) |

**Counts:** FAIL 0. WARN 16: 12 accepted CAD-validation warnings (unchanged from rev B) and 4 avionics integration
warnings (§5). UNVERIFIED 8 (§6). These tests show that the software behaves as specified on synthetic data; they are
not evidence of flight readiness.

## 4. Hardware assumptions

- Every avionics component is **COMPONENT TO BE SELECTED**; candidate classes from `avionics/electronics.csv` are kept,
  datasheets not checked (`avionics/HARDWARE_MAPPING.md`).
- Sensor ranges and rates are requirements (class C): accelerometer ≥ ±16 g (2× the PLACEHOLDER peak), gyro
  ≥ ±1000 deg/s, barometer 30–110 kPa at 50 Hz, GNSS ≥ 1 Hz, temperature and battery 1 Hz.
- Sensor health: stale after 3 nominal sample periods without a valid sample (assumption).
- Battery status thresholds on the ground station (LOW < 3.6 V, CRITICAL < 3.4 V) are planning assumptions.
- Avionics masses EL-AV 59 g, EL-GPS 20 g, EL-BAT 27 g, camera 35 g and switch allowance 12 g are estimates.

## 5. CAD integration status

The CAD holds PLACEHOLDER electronics envelopes; they fit (sled stack 30.10 mm vs 30.50 mm coupler bore, no
interference, battery width 28.0 ≤ 28.8 mm, GPS under the hatch, switch reachable). Warnings:

1. Envelope completeness: buzzer, LED, regulator, temperature sensor, battery divider, connectors and wiring have no
   envelope.
2. IMU placeholder is 20.5 mm off the roll axis; the interface specification asks for near-axis mounting (up to
   6.3 m/s² centripetal reading at 1000 deg/s).
3. Steel M4 rods run alongside the radio envelope; no antenna is modelled.
4. Sled removal margin is 0.40 mm on the placeholder envelopes.

Mass properties: avionics and payload items total 262.7 g at STA 472.4 mm (21.7 % of liftoff mass). With the assumed
masses varied by ±25 % (illustrative) the liftoff margin stays within 2.52–2.74 cal (target 1.5–3.0; includes the
PLACEHOLDER motor).

## 6. Remaining physical validation (UNVERIFIED — PHYSICAL MEASUREMENT REQUIRED)

1. Real module dimensions (with headers and connectors) vs the placeholder envelopes.
2. Avionics-bay sealing and static-port pressure lag, once a barometer has been selected.
3. Real battery size, strap retention and charging access.
4. Harness: connector passage through the ⌀8 mm grommet, wire count, bend radius, lengths.
5. Radio / GNSS interference and antenna placement.
6. RF transparency of the kraft / phenolic airframe (range test T-14).
7. SD-card and battery-connector access.
8. Mass of every avionics and payload item (weigh; then update the analysis through the normal pipeline).

Also required on the bench: sensor noise and bias, loop timing on the selected microcontroller, SD write latency,
power budget and endurance (T-10), breakwire logging (T-15), and a re-check of the state-transition thresholds and the
barometric-altitude reference temperature at the real launch-site elevation.

## 7. Remaining safety review

- Confirm that the selected hardware adds no output able to drive any energetic or deployment device (the software
  has none; `avionics/tests/test_architecture.py` guards the code).
- Radio: legal band and power, frequency coordination with the range.
- LiPo battery handling, charging and transport under the range's rules.
- Power switch AV-307 (the BOM calls it an "arming switch"): it only powers the electronics; confirm this in the
  wiring and in the range procedure.
- Mass and CG after weighing, with the certified motor installed.

## 8. Items requiring qualified rocketry mentor / range approval

- Selection of a legally obtainable certified motor and entry of its published data (replacing the PLACEHOLDER).
- Avionics component selection and installation in the flight-readiness review.
- Radio operation (legality, power, frequency coordination).
- Battery type and handling procedure at the range.
- Static margin with the real motor and a measured CG; rail-exit speed on the range's rail.
- Recovery system (certified motor ejection, prepared by a mentor), proof loads, and the complete flight-readiness
  review and range safety officer approval on the day.
