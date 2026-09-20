# ASTRA-66 — Hardware-integration readiness status (Phase 6)

> **NOT FLIGHT CERTIFIED.** Nothing in ASTRA-66 has flown, no avionics hardware has been bought, built, weighed or
> tested, and no propulsion is designed here: the motor is an external, commercially certified component represented by
> PLACEHOLDER data. This document classifies what the repository actually establishes today, so a bench-validation
> phase can start without mistaking software results for measurements.

Categories used below:

| Tag | Meaning |
|---|---|
| **PASS** | Implemented and verified by the automated software tests (on synthetic data) |
| **ASSUMED** | Engineering assumption or requirement; defensible, but not measured |
| **UNVERIFIED** | Needs a physical measurement of the existing design |
| **REQUIRES HARDWARE** | Cannot be established at all until components exist on a bench |
| **REQUIRES MENTOR/RANGE REVIEW** | Needs a qualified rocketry mentor, or range / regulatory approval |

## 1. avionics/

| Item | Status | Evidence / next step |
|---|---|---|
| Sensor interface, scheduling, sample model | PASS | `avionics/tests/test_sensor_validation.py`; fixed-rate scheduling without drift |
| Schema validation (types, ranges, NaN, enums, required fields) | PASS | schema-driven; invalid values rejected before processing |
| Timestamp handling (wrap, duplicates, backwards, gaps) | PASS | `avionics/tests/test_timestamps.py` |
| Kalman estimator, barometer-only after apogee | PASS | tracks the synthetic truth within the documented tolerances |
| Flight-state classifier and events | PASS | forward-only; pad-knock and accelerometer-failure cases covered |
| Sensor health (stale detection) | PASS | `tests/test_avionics.py`; telemetry packet v2 carries the bits |
| Data logger, CSV / JSON-lines, CRC-16 rows, metadata | PASS | round trip and damaged-file handling tested |
| Telemetry packet v2, encode / decode, saturation, sentinels | PASS | every single-bit error rejected |
| Link statistics: loss, duplicates, rejects, wrap | PASS | `avionics/ground_station/receiver.py` + tests |
| Ground-station display and API | PASS (software) | prototype only; **REQUIRES HARDWARE** for real-time use |
| Post-flight analysis and derived statistics | PASS | checked against the synthetic truth profile |
| Data-source modes SYNTHETIC / BENCH / FLIGHT | PASS | `avionics/firmware/data_source.py`; FLIGHT disabled until real data exist |
| Sensor ranges, rates, thresholds, filter tuning | ASSUMED | `avionics/HARDWARE_MAPPING.md`, `avionics/firmware/sensor_interfaces/catalog.py` |
| Simulated noise, drift, discharge, parachute swing | ASSUMED (illustrative) | not properties of any component |
| Every component choice | REQUIRES HARDWARE | all COMPONENT TO BE SELECTED |
| Loop timing, SD write latency, power budget, radio range | REQUIRES HARDWARE | `documentation/AVIONICS_BENCH_TEST_PLAN.md` |
| Radio band, power and frequency coordination | REQUIRES MENTOR/RANGE REVIEW | must be legal where operated |

## 2. analysis/

| Item | Status | Evidence / next step |
|---|---|---|
| Parameter provenance tags and single source of truth | PASS | `analysis/analysis.py` is the only source of geometry and masses |
| Mass budget arithmetic, CG, CP (Barrowman), static margin | PASS | recomputed independently in `avionics/integration/cad_mass_integration.py`: identical |
| Structural part masses (CAD volume × assumed density × fill) | ASSUMED | densities and fill factors are assumptions; weigh the printed parts |
| Avionics masses EL-AV 59 g, EL-GPS 20 g, EL-BAT 27 g, camera 35 g, AV-309/310 12 g | ASSUMED / UNVERIFIED | weigh: `documentation/MASS_MEASUREMENT_PROCEDURE.md` |
| Measured CG of the built vehicle | UNVERIFIED | balance measurement after assembly |
| Static margin with a real motor | REQUIRES MENTOR/RANGE REVIEW | needs the certified motor's published data |

## 3. simulation/

| Item | Status | Evidence / next step |
|---|---|---|
| 1-DOF trajectory, ISA atmosphere, numerical verification | PASS | 13/13 verification checks |
| Sensor replay through the flight-computer pipeline | PASS | `simulation/avionics_replay.py` + synthetic sample dataset |
| Drag build-up coefficients | ASSUMED | cross-check with OpenRocket / RASAero; flight data would be needed to calibrate |
| Motor thrust curve, mass, burn time | ASSUMED (PLACEHOLDER) | replace with the certified motor's published data |
| Wind, weathercocking, angle of attack, dynamic stability | not modelled | out of scope of the 1-DOF model |
| Real trajectory behaviour | REQUIRES MENTOR/RANGE REVIEW | only a supervised flight can show it |

## 4. cad/

| Item | Status | Evidence / next step |
|---|---|---|
| Geometry, manifold meshes, interference, assembly feasibility | PASS | committed CAD validation: 147 PASS / 12 WARN / 0 FAIL |
| Electronics fit of the PLACEHOLDER envelopes (sled, battery, GPS, switch) | PASS | `documentation/CAD_AVIONICS_INTEGRATION.md` |
| Envelope completeness (buzzer, LED, regulator, temperature sensor, divider, wiring) | UNVERIFIED (WARN) | add envelopes when the parts are selected |
| IMU position relative to the roll axis | UNVERIFIED (WARN) | placeholder is 20.5 mm off axis; decide with the real board |
| Antenna routing and metal proximity | UNVERIFIED (WARN) | no antenna geometry modelled |
| Sled removal margin (0.40 mm on placeholders) | UNVERIFIED (WARN) | re-check with real boards, wires and connectors |
| Tube, coupler and MMT dimensions | UNVERIFIED | measure the purchased stock (3 stations × 2 axes) |
| Printed-part fit (shoulder, guide slot, inserts) | REQUIRES HARDWARE | print fit coupons |

## 5. documentation/

| Item | Status | Evidence / next step |
|---|---|---|
| File references and disclaimers in every document | PASS | `tests/test_docs.py`, `avionics/tests/test_architecture.py` |
| Engineering status generated from the result files | PASS | `documentation/ENGINEERING_STATUS.md` is regenerated by the pipeline |
| Hardware mapping, data format, bench plan, mass procedure | complete as plans | they describe work that has **not** been done yet |
| Flight-readiness review, range approval | REQUIRES MENTOR/RANGE REVIEW | the project is NOT flight certified |

## 6. tests/

| Item | Status | Evidence / next step |
|---|---|---|
| 40 project regression tests (package, CAD data, simulation, documentation) | PASS | `python -m unittest discover -s tests` |
| 34 avionics integration tests | PASS | `tests/test_avionics.py` |
| 81 avionics software tests | PASS | `python -m unittest discover -s avionics/tests -t .` |
| Safety-boundary guard (no actuation identifiers, no hardware-I/O imports) | PASS | `avionics/tests/test_architecture.py` |
| Any test against real sensors, radio or flight data | REQUIRES HARDWARE | the FLIGHT data-source mode stays disabled until a real record exists |

## 7. Summary

- **Software behaviour:** verified by 155 automated tests on synthetic data (74 project regression tests including
  34 avionics integration tests, plus 81 avionics software tests). This says nothing about hardware.
- **Physical properties:** every avionics mass, dimension and sensor property is ASSUMED or UNVERIFIED.
- **Bench validation:** planned in `documentation/AVIONICS_BENCH_TEST_PLAN.md`; needs components that do not exist yet.
- **Mentor / range review:** motor selection and data, radio legality, battery handling, mass and CG with the motor
  fitted, and the flight-readiness review.
