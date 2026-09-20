# ASTRA-66 — Avionics and flight-data system design (Phase 4)

> **Draft student design. NOT flight certified.** This phase covers sensing, data logging, telemetry, ground-station
> visualisation and post-flight analysis only. The avionics have **no output of any kind** that could drive an
> igniter, pyrotechnic, energetic or deployment device. Propulsion is an external, commercially certified component,
> never designed here; recovery uses the certified motor's own ejection, prepared by a mentor. No avionics component has
> been selected, built or tested: every hardware item is **COMPONENT TO BE SELECTED**, and every dataset in this phase
> is **SIMULATED**. Any use in flight requires hardware testing and review by a qualified mentor and the range.

## 1. Scope and status

| Area | Status | Basis |
|---|---|---|
| Architecture (6 layers) | Defined | `avionics/architecture/system_architecture.md`, block diagram `avionics/architecture/avionics_block_diagram.svg` |
| Interfaces | Specified as requirements | `avionics/architecture/interface_spec.md` |
| Flight-data schema | Version 1.1.0, draft (1.0.0 in Phase 4; Phase 6 added the data-source modes) | `avionics/data/schema/flight_data_schema.json` |
| Flight-computer software | Implemented in Python, simulated sensors only | `avionics/firmware/` |
| Ground station | Prototype, simulated / replayed data only | `avionics/ground_station/` |
| Post-flight analysis | Implemented | `avionics/analysis/flight_data_analysis.py` |
| Tests | Hardware-free, run by `python run_validation.py` and CI | `avionics/tests/` |
| Hardware | **Nothing selected** | — |

Value classes as in the rest of ASTRA-66: the software's behaviour is **verified by test** on simulated data; sensor
ranges, rates, thresholds and filter tuning are **assumptions** (class C); simulated sensor noise, drift, discharge and
swing are **placeholders** (class D); nothing is **measured**.

## 2. Architecture

Six layers, each behind a hardware-independent interface (details in `avionics/architecture/system_architecture.md`):

1. **SENSOR LAYER**: `Sensor` interface, fixed-rate scheduling, simulated sensors with fault injection.
2. **FLIGHT-DATA PROCESSING**: pad reference, pressure → altitude, Kalman filter, flight-state classifier.
3. **DATA LOGGER**: timestamp checks, schema validation, quality flags, CSV / JSON-lines with CRC-16.
4. **TELEMETRY**: 41-byte packet, simulated link, hardware-link interface.
5. **GROUND-STATION VISUALIZATION**: receiver with link statistics, local server, dashboard.
6. **POST-FLIGHT ANALYSIS**: tolerant reader, plots, derived statistics.

The flight computer (`avionics/firmware/flight_computer.py`) ticks at 100 Hz, logs at 50 Hz (example; ≥ 100 Hz is
the hardware target) and sends telemetry at 5 Hz. Its only outputs are the log and the telemetry link.

## 3. Sensor strategy

| Sensor | Why it is needed | Primary / backup role | Requirement (assumption) |
|---|---|---|---|
| IMU | Liftoff, burnout, acceleration record | Primary for liftoff and burnout | accel ≥ ±16 g, gyro ≥ ±1000 deg/s, 100 Hz |
| Barometer | Altitude, apogee, landing | Primary for apogee and landing; **backup for liftoff** | 30–110 kPa, 50 Hz |
| GPS / GNSS | Recovery position, ground track | Independent altitude cross-check | ≥ 1 Hz |
| Temperature | Environment record | — | −20 to +60 °C, 1 Hz |
| Battery monitor | Endurance, brown-out diagnosis | — | 0–5 V ADC input, 1 Hz |
| Separation breakwire | Confirms separation at I-03 | Independent of the barometer | GPIO input, 50 Hz |

Redundancy is by **physics**, not duplication: liftoff can be detected by the accelerometer or, if it fails, by the
barometer; apogee by velocity sign or altitude drop; separation by the breakwire. All ranges derived from the
simulation use the **PLACEHOLDER** propulsion input (peak 7.4 g) and must be re-derived with the certified motor's
published data. The required ranges are not manufacturer specifications; candidate classes come from
`avionics/electronics.csv` and their datasheets have not been checked.

## 4. Data flow

Sensor → acquisition (µs timestamp) → processing (estimator, classifier) → logger (validation → CSV + CRC) → SD card
→ post-flight analysis; in parallel, latest values → telemetry packet → link → ground station. Frames carry only
samples taken since the previous frame (slow sensors appear about once per second); telemetry always carries the
latest values. Full description, rates and the error-handling table: `avionics/architecture/data_flow.md`.

## 5. Software architecture

| Package | Modules |
|---|---|
| `avionics/firmware/sensor_interfaces/` | `base.py` (interface), `catalog.py` (requirements), `simulated.py` (truth profiles, simulated sensors, faults) |
| `avionics/firmware/flight_state/` | `estimator.py` (Kalman filter), `classifier.py` (states) |
| `avionics/firmware/logging/` | `schema.py`, `timebase.py`, `logger.py`, `reader.py` |
| `avionics/firmware/telemetry/` | `packet.py`, `link.py` |
| `avionics/firmware/` | `flight_computer.py`, `simulate_flight.py`, `crc.py` |
| `avionics/ground_station/` | `receiver.py`, `server.py`, `avionics/ground_station/dashboard/index.html` |
| `avionics/analysis/` | `flight_data_analysis.py` |

**State estimator.** A 2-state Kalman filter (altitude, vertical velocity) predicts with the axial specific force minus
gravity and corrects with barometric altitude. This assumes nose-up vertical flight, as in the 1-DOF simulation. After
apogee the filter becomes barometer-only because the bay hangs at an unknown angle under the parachute. The pad
reference pressure is a running mean on the pad, frozen at liftoff or as soon as a reading is more than 5 m above it.

**Flight states (data processing only).** Forward-only sequence PRELAUNCH → ASCENT → COAST → DESCENT → LANDED. The
state is written to the log and telemetry and used by the analysis; it drives nothing.

| Transition | Rule (all thresholds are assumptions) | Rationale |
|---|---|---|
| PRELAUNCH → ASCENT | axial specific force > 2.0 g for 0.05 s, or altitude > 15 m with vertical velocity > 5 m/s for 0.05 s | thrust gives a clear step (placeholder average T/W 6.5); the time filter rejects handling knocks; barometric backup if the IMU fails |
| ASCENT → COAST | axial specific force < 0.5 g for 0.05 s, ≥ 0.2 s after liftoff | thrust gone, drag decelerates the vehicle |
| COAST → DESCENT | vertical velocity < −1 m/s for 0.25 s, or altitude 5 m below maximum; ≥ 2 s after liftoff | apogee; lockout against early transients |
| DESCENT → LANDED | abs(vertical velocity) < 1 m/s and altitude within 2 m for 3 s; ≥ 1 s after apogee | stationary on the ground |

If burnout is never seen (accelerometer failure), ASCENT goes directly to DESCENT on the apogee rule and the event
"BURNOUT_NOT_DETECTED" is recorded. Labels appear after the confirmation time; the analysis subtracts it to estimate
the event times.

## 6. Data schema

`avionics/data/schema/flight_data_schema.json`, version 1.1.0 (draft; 1.0.0 in Phase 4). One CSV row per logged frame; column order as
below; an empty cell means no fresh sample or a rejected value. `valid_range` values are **plausibility limits used by
validation, not sensor specifications**.

| Field | Type | Unit | Nominal rate | Source | Description |
|---|---|---|---|---|---|
| `seq` | int | count | log rate | flight computer | frame counter (gaps reveal lost frames) |
| `timestamp` | float | s | log rate | µs clock | time since clock start (required) |
| `data_source` | enum | — | log rate | flight computer | SIMULATED or HARDWARE (required) |
| `flight_state` | enum | — | log rate | classifier | PRELAUNCH / ASCENT / COAST / DESCENT / LANDED (data label only) |
| `imu_accel_x` | float | m/s² | 100 Hz | IMU | specific force, body x |
| `imu_accel_y` | float | m/s² | 100 Hz | IMU | specific force, body y |
| `imu_accel_z` | float | m/s² | 100 Hz | IMU | specific force, body z (axial, toward the nose; +9.81 on the pad) |
| `gyro_x` | float | deg/s | 100 Hz | IMU | angular rate about x |
| `gyro_y` | float | deg/s | 100 Hz | IMU | angular rate about y |
| `gyro_z` | float | deg/s | 100 Hz | IMU | angular rate about z (roll) |
| `barometric_pressure` | float | Pa | 50 Hz | barometer | static pressure |
| `altitude` | float | m | 50 Hz | barometer (derived) | altitude above the pad reference (ISA) |
| `vertical_velocity` | float | m/s | log rate | estimator | Kalman-filter vertical velocity |
| `temperature` | float | °C | 1 Hz | temperature sensor | bay temperature |
| `latitude` | float | deg | 1 Hz | GNSS | WGS84 (empty without fix) |
| `longitude` | float | deg | 1 Hz | GNSS | WGS84 (empty without fix) |
| `gps_altitude` | float | m | 1 Hz | GNSS | altitude above mean sea level |
| `gps_fix` | int | — | 1 Hz | GNSS | 0 none, 2 = 2D, 3 = 3D |
| `gps_satellites` | int | count | 1 Hz | GNSS | satellites used |
| `battery_voltage` | float | V | 1 Hz | battery monitor | 1S LiPo terminal voltage |
| `separation_detected` | int | 0/1 | 50 Hz | breakwire | separation at I-03 (logging only) |
| `quality_flags` | int | bitmask | log rate | logger | bit 0 accel, 1 gyro, 2 baro, 3 temperature, 4 GNSS, 5 battery value rejected; 6 timestamp gap |
| `crc16` | hex | — | log rate | logger | CRC-16/CCITT-FALSE of the row's other fields |

Example dataset: `avionics/data/example/example_flight_simulated.csv` (4547 frames, SIMULATED, replay of the existing
trajectory with the PLACEHOLDER propulsion input) with `avionics/data/example/example_flight_simulated.meta.json` and a
telemetry capture.

## 7. Telemetry

Packet v2 (41 bytes, little-endian, fixed point, CRC-16; Phase 5 added sensor-health flags, v1 still decodes): time,
sequence number, flags (SIMULATED, GPS valid, separation, IMU / barometer / GNSS / temperature / battery health), flight
state, altitude, vertical velocity, axial and total acceleration, temperature, latitude, longitude, GNSS altitude, fix,
satellites, battery voltage. Missing values have sentinels; out-of-range values saturate.
**SIMULATED TELEMETRY** (`SimulatedTelemetryLink`, seeded loss and bit errors) is implemented and used by the ground
station. **REAL HARDWARE TELEMETRY** (`HardwareTelemetryLink`) is an interface only and refuses to start without a
radio driver; no radio has been selected, and any radio must use a legal band and power level.

## 8. Ground station and post-flight analysis

- **Ground station** (`avionics/ground_station/`): decodes packets, counts rejected / missing / duplicate packets and
  shows flight state, altitude, vertical velocity, acceleration, temperature, GPS position and track, and battery
  voltage. Sources: a telemetry capture or a fresh simulated flight. Prototype only; **real-time flight capability is
  not claimed** and has not been tested.
- **Post-flight analysis** (`avionics/analysis/flight_data_analysis.py`): reads a log tolerantly and produces
  altitude, velocity, acceleration, temperature and battery plots against time, a GPS track, and derived statistics
  (apogee, maximum velocity and acceleration, descent rate, event times and durations, temperature and battery ranges,
  GNSS distances, data quality). Example output: `avionics/analysis/results/example_flight_simulated/flight_report.md`.

Example results (**SIMULATED, PLACEHOLDER propulsion; they show that the software works, not how a real flight would
behave**): detected apogee 328.3 m against 328.2 m in the source trajectory; liftoff, burnout, apogee and landing
detected within 0.05, 0.03, 0.01 and 0.2 s of the trajectory's events; descent rate 5.12 m/s against 5.09 m/s.

## 9. Testing strategy

All tests run without hardware (`python -m unittest discover -s avionics/tests -t .`, also step 5 of
`python run_validation.py` and therefore GitHub Actions).

| Test module | Covers |
|---|---|
| `avionics/tests/test_sensor_validation.py` | schema validation (non-finite, out-of-range, unparseable, enum, required fields), sensor catalogue, simulated sensors, fault injection, scheduling |
| `avionics/tests/test_timestamps.py` | 32-/16-bit counter unwrap, duplicate / backwards / gap detection, periodic frame times |
| `avionics/tests/test_missing_corrupt.py` | CRC-detected bit flips, truncated and garbage lines, out-of-order and duplicate rows, bad values, missing columns, sensor dropouts and NaNs in flight, barometer failure |
| `avionics/tests/test_flight_state.py` | state sequence and event timing on the synthetic profile and on the replayed trajectory, forward-only states, pad knock rejection, barometric backup, offline classification, estimator accuracy |
| `avionics/tests/test_telemetry.py` | CRC check value, packet round trip and quantisation, missing values, saturation, corruption detection, seeded link, hardware-link refusal, receiver statistics and sequence wrap |
| `avionics/tests/test_logger.py` | CSV and JSON-lines output with CRC, metadata sidecar, source labelling, freshness rule, validity and reproducibility of the committed example |
| `avionics/tests/test_analysis.py` | numerical helpers, derived statistics against the truth profile, output files, missing GNSS, offline states, committed example results |
| `avionics/tests/test_architecture.py` | **safety boundary** (no actuation identifiers, no hardware-I/O libraries), documentation paths and disclaimers, block diagram, ground-station server |

Tests compare with known truth (the simulated trajectory) using stated tolerances; none of them uses flight data,
because none exists.

## 10. Hardware-selection criteria (for the next phase, with a mentor)

1. **Safety boundary first:** no part may add an output able to drive an energetic or deployment device; the avionics
   stay sense-and-record only.
2. **Measurement range with margin** over the certified motor's data (re-derive the ≥ 16 g accelerometer requirement).
3. **Rates:** IMU ≥ 100 Hz, barometer ≥ 20 Hz (50 Hz preferred), GNSS ≥ 1 Hz, with a microcontroller that sustains the
   loop and SD writes with margin.
4. **Fit:** within the CAD placeholder envelopes and existing bosses (`avionics/architecture/interface_spec.md` §3), and
   within the mass allocation (EL-AV 59 g, EL-GPS 20 g, EL-BAT 27 g, assumptions); otherwise update the CAD and the
   analysis through the normal pipeline.
5. **Power:** 1S LiPo endurance for the pad hold with margin (measure; test T-10 in the engineering package).
6. **Availability and documentation:** student-accessible modules with published datasheets and open drivers; verify
   every figure from the datasheet, never from this repository.
7. **Radio legality:** only a band and power level legal where it is operated.

## 11. Limitations

- No hardware exists; every sensor, the microcontroller, the SD card and the radio are COMPONENT TO BE SELECTED.
- All data are SIMULATED. Sensor noise, drift, parachute swing, GNSS drift and battery discharge are illustrative
  placeholders; the truth trajectory uses the PLACEHOLDER propulsion input.
- Thresholds and filter tuning are assumptions, checked only against simulated data.
- The estimator assumes vertical flight until apogee (as the 1-DOF simulation); tilt, weathercocking and wind are not
  modelled; the gyroscopes are logged but not used for attitude estimation.
- The derived velocity in the analysis is smoothed and underestimates sharp peaks by a few m/s.
- The Python reference implementation has not been ported or timed on a microcontroller; SD-card write latency, radio
  range, power consumption and electromagnetic compatibility are not assessed.
- The ground station has not been tested with a real radio or in real time.
- The temperature sensor and battery divider have no CAD envelope yet.

## 12. Future hardware integration

1. Select components with a mentor against §10; record the selected part numbers and datasheet values (class A/C) in
   `avionics/firmware/sensor_interfaces/catalog.py` and `avionics/architecture/interface_spec.md`.
2. Update the CAD envelopes in `cad/parts/COTS_envelopes.scad` and the masses in `analysis/analysis.py`, then run the
   normal CAD and validation pipeline.
3. Write one driver per sensor behind the `Sensor` interface, an SD-card `LogSink` and a radio driver for
   `HardwareTelemetryLink`, keeping the data-source label HARDWARE only for real sensors.
4. Bench tests (engineering package T-10, T-14, T-15): sensor plausibility, logging rate, SD integrity, link range,
   breakwire logging. Compare against the simulation with the same analysis tool.
5. Re-derive thresholds with the certified motor's published thrust data; re-run all tests.
6. Mentor and range review before any flight consideration. The avionics remain a data system with no command outputs.
