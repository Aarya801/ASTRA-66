# ASTRA-66 — Avionics architecture (Phase 5 audit and integration)

> **Draft student design. NOT flight certified.** The avionics are a data system only: they read sensors, estimate the
> vertical state, log, transmit telemetry and support analysis. There is no actuator, igniter, pyrotechnic, energetic
> or deployment output, no autonomous flight control, and no propulsion design; propulsion is an external,
> commercially certified component. No avionics hardware has been selected or tested, and every dataset is SIMULATED
> or synthetic. Phase 4 design: `documentation/AVIONICS_DESIGN.md`. Phase 5 status: `documentation/PHASE_5_STATUS.md`.

## 1. Block diagram

```
 SENSORS  IMU · barometer · GNSS · temperature · battery monitor · breakwire       (all COMPONENT TO BE SELECTED)
   │        today: simulated sensors (avionics/firmware/sensor_interfaces/simulated.py)
   │        or recorded / synthetic data (simulation/avionics_replay.py → ReplaySensor)
   ▼
 SENSOR ABSTRACTION        Sensor.sample(t_us) → SensorSample                        sensor_interfaces/base.py
   ▼
 FILTERING / VALIDATION    schema plausibility limits; NaN, inf, unparseable,       flight_computer.py (_validate)
                           out-of-range → rejected before processing; per-sensor
                           health = valid sample within 3 nominal periods
   ▼
 STATE ESTIMATION          pad reference pressure → ISA altitude → 2-state          flight_state/estimator.py
                           Kalman filter (altitude, vertical velocity);
                           barometer-only after apogee
   ▼
 FLIGHT-STATE / EVENT      PRELAUNCH → ASCENT → COAST → DESCENT → LANDED,           flight_state/classifier.py
 LOGIC                     events LIFTOFF / BURNOUT / APOGEE / LANDING (data labels; they drive nothing)
   ├──────────────────────────────────────────────┐
   ▼                                              ▼
 DATA LOGGER                                    TELEMETRY PACKET
 timestamp check, schema validation,            v2, 41 bytes, CRC-16, sequence number,
 quality flags, CSV / JSON-lines,               SIMULATED flag, sensor-health bits
 CRC-16 per row          logging/               → SimulatedTelemetryLink            telemetry/
   │                                            (hardware link: interface only)
   ▼                                              ▼
 microSD (hardware) / file (today)              GROUND STATION
   │ copied after recovery                      receiver (CRC, loss, duplicates, latest time) →
   ▼                                            server (JSON API) → dashboard       ground_station/
 POST-FLIGHT ANALYSIS          analysis/flight_data_analysis.py
```

The logger and the telemetry are parallel branches after the flight-state logic: the log keeps every frame at the log
rate; telemetry sends summaries of the latest valid values at 5 Hz. The graphic version of the same architecture is
`avionics/architecture/avionics_block_diagram.svg`.

## 2. Audit of the Phase 4 implementation

| Item | What exists | Where | Finding |
|---|---|---|---|
| Sensor interfaces | `Sensor` base class (fixed-rate scheduling, `sample(t_us)`), `HardwareSensorPlaceholder` that refuses to read, simulated sensors with fault injection | `avionics/firmware/sensor_interfaces/` | Sound. Phase 5 adds `ReplaySensor` for recorded data (no second interface) |
| IMU data model | 3-axis specific force (m/s²) and 3-axis rate (deg/s), body frame +z toward the nose, 100 Hz | schema, `simulated.py` | Sound. The CAD places the IMU envelope 20.5 mm off the roll axis, conflicting with the "near-axis" requirement (WARN in the CAD check) |
| Barometer data model | pressure (Pa) → altitude above the pad (ISA); pad reference = running mean, frozen at liftoff or when > 5 m above it | `estimator.py` | Sound. **New finding:** sea-level ISA temperature overestimates height above an elevated pad by ≈ 1.1 % at 500 m (documented in `avionics/DATA_FORMAT.md` §6; planning site is at 0 m) |
| GPS data model | latitude / longitude (deg), altitude MSL, fix, satellites at 1 Hz; position nulled without fix | schema, `avionics/firmware/flight_computer.py` | Sound; GNSS health (message received) is kept separate from fix quality |
| Temperature sensing | bay temperature (°C) at 1 Hz, logged and transmitted | schema | Logged only; not used in processing (it could later set the barometric reference temperature) |
| Battery-voltage monitoring | voltage (V) at 1 Hz, logged and transmitted | schema | No low-voltage logic on board (correct for a data system); Phase 5 ground station shows OK / LOW / CRITICAL with planning thresholds (assumptions) |
| SD / data logging | `DataLogger` + CSV / JSON-lines / memory sinks, metadata sidecar, tolerant reader | `avionics/firmware/logging/` | Sound. No SD-card driver (needs hardware) |
| CRC / checksum | CRC-16/CCITT-FALSE shared by log rows, JSON lines and packets | `avionics/firmware/crc.py` | Sound. Phase 5 test: every single-bit error in a packet is rejected |
| Packet / frame format | log frame = schema row; telemetry packet v1 (41 bytes, as built in Phase 4) | schema, `avionics/firmware/telemetry/packet.py` | Flag bits 3–7 were unused. **Phase 5: packet v2** carries sensor-health bits in them (same size; v1 still decodes) |
| Telemetry model | `SimulatedTelemetryLink` (seeded loss, bit errors), `HardwareTelemetryLink` (interface only), 5 Hz, latest values | `avionics/firmware/telemetry/link.py`, `avionics/firmware/flight_computer.py` | **Gap:** latest values were repeated when a sensor went silent, so a dead sensor looked alive. Fixed by the v2 health bits |
| Ground-station interface | receiver, HTTP JSON API, browser dashboard; capture replay and live simulation | `avionics/ground_station/` | Phase 5 adds sensor health, GPS / battery status, packet count and loss, latest telemetry time, and a sensor-replay source |
| State estimator | 2-state Kalman filter, accelerometer predict / barometer update, barometer-only after apogee | `estimator.py` | Sound. **Defect found:** only NaN / inf were filtered before processing, so a finite but impossible value (e.g. 250 kPa) would have corrupted the altitude estimate. Fixed: values are validated against the schema before processing |
| Event / state machine | forward-only classifier with confirmation times, barometric launch backup, BURNOUT_NOT_DETECTED | `classifier.py` | Sound; thresholds remain assumptions |
| Configuration system | fields and limits in `flight_data_schema.json`; sensor requirements and nominal rates in `catalog.py`; thresholds in `ClassifierConfig`; filter tuning in `VerticalKalmanFilter`; rates as `FlightComputer` arguments | several files | **Gap (documented, not changed):** no single avionics configuration file. A central config is recommended once hardware is selected; adding one now would only move assumptions around |
| Test coverage | 81 hardware-free tests in `avionics/tests/` | `avionics/tests/` | Phase 5 adds `tests/test_avionics.py` (integration: packets v2, validity, replay, ground station, CAD / mass report, documents) |

## 3. Phase 5 changes to the architecture (no redesign)

1. **Validation before processing** (`avionics/firmware/flight_computer.py`): every sample is checked against the
   schema; invalid values never reach the estimator, classifier or telemetry, while the raw value still goes to the
   logger, which writes it empty and flags it.
2. **Sensor health** (`FlightComputer.health()`): OK while a fully valid sample arrived within 3 nominal sample periods
   (assumption). Carried in telemetry packet v2 and in the replay outputs.
3. **Packet v2** (`avionics/firmware/telemetry/packet.py`): health bits in the previously unused flag bits; the
   decoder accepts v1 and v2.
4. **Receiver statistics** (`avionics/ground_station/receiver.py`): packet-loss percentage and latest packet time.
5. **Sensor replay** (`simulation/avionics_replay.py`): recorded / synthetic sensor data through the unchanged pipeline;
   deterministic sample `simulation/data/sample_flight.csv` (synthetic test data, not flight data).
6. **Ground-station data view** (`avionics/ground_station/dashboard/index.html`, `server.py --sensors`).
7. **CAD ↔ avionics and mass check** (`avionics/integration/cad_mass_integration.py`), read-only against the CAD and
   the analysis.

## 4. Value classes in this architecture

Nothing here is a measurement: the software behaviour is **verified by tests on synthetic data**, the sensor ranges,
rates and thresholds are **assumptions**, every component is **COMPONENT TO BE SELECTED**, and the physical fit and
masses are **UNVERIFIED until measured**. Which items sit in which class:
`documentation/HARDWARE_INTEGRATION_STATUS.md`.

## 5. Interfaces and formats

- Hardware classes, required / optional status and validation needs: `avionics/HARDWARE_MAPPING.md`.
- Every file and packet format with units and ranges: `avionics/DATA_FORMAT.md`.
- Sensor, software and physical interfaces: `avionics/architecture/interface_spec.md`.
- CAD fit and mass properties: `documentation/CAD_AVIONICS_INTEGRATION.md`.
