# ASTRA-66 avionics — data format

> Draft. Every dataset in this repository is **SYNTHETIC** (computer-generated); no bench or flight data exist yet.
> The avionics are NOT flight certified. Machine-readable definition of the log format:
> `avionics/data/schema/flight_data_schema.json` (version 1.1.0). This document adds the replay formats, the telemetry
> packet and the analysis conventions.

Value classes: the **formats** below are fixed and verified by tests; the **expected ranges** come from the
PLACEHOLDER simulation and are assumptions; the **validation limits** are plausibility limits, not sensor
specifications; no sensor has been selected or measured (`documentation/HARDWARE_INTEGRATION_STATUS.md`).

## 1. Determinism rules (all CSV files)

- UTF-8, LF line endings, comma separator, `.` as decimal point, no thousands separators, no quoting needed.
- A header row with fixed column order; the column order is part of the format.
- Every numeric field has a fixed number of decimals (listed below), so the same data always produce the same bytes.
- An **empty cell means "no value"** (no fresh sample, sensor absent, or value rejected); it is never written as 0.
- No wall-clock dates inside data files: time is the flight computer's clock (`timestamp`, seconds since start).
- Files that can be damaged in storage carry a per-row CRC-16 (`crc16`).
- `data_source` is in every row. Modes (`avionics/firmware/data_source.py`): **SYNTHETIC** (computer-generated),
  **BENCH** (recorded from real hardware on the bench) and **FLIGHT** (recorded in flight; **disabled in software**
  because no real flight record exists). The Phase 4 labels `SIMULATED` and `HARDWARE` are accepted as aliases of
  SYNTHETIC and BENCH. Synthetic and bench data must never be presented as flight data.

Load in Python:

```python
from avionics.firmware.logging.reader import read_flight_log     # tolerant reader: CRC, types, ranges, time order
records, report = read_flight_log("avionics/data/example/example_flight_simulated.csv")
```

or with the standard `csv` module (empty strings → missing values).

## 2. Onboard flight-data log (`*.csv`, schema v1.1.0)

One row per logged frame (50 Hz in the example; ≥ 100 Hz hardware target). "Expected range" is what the
**PLACEHOLDER** simulation produces; "Validation limit" is the plausibility limit that rejects a value (not a sensor
specification).

| Column | Type | Unit | Decimals | Expected range (placeholder simulation) | Validation limit | Rate |
|---|---|---|---|---|---|---|
| `seq` | int | count | 0 | 0 … n, +1 per frame | 0 … 2³²−1 | log rate |
| `timestamp` | float | s | 6 | 0 … ~95 | 0 … 10⁶ (required) | log rate |
| `data_source` | enum | — | — | SYNTHETIC | SYNTHETIC / BENCH / FLIGHT (+ legacy SIMULATED, HARDWARE; required) | log rate |
| `flight_state` | enum | — | — | PRELAUNCH → LANDED | 5 states | log rate |
| `imu_accel_x` | float | m/s² | 3 | −10 … +10 | ±400 | 100 Hz |
| `imu_accel_y` | float | m/s² | 3 | −2 … +2 | ±400 | 100 Hz |
| `imu_accel_z` | float | m/s² | 3 | −15 … +83 (≈ −1.5 … +8.5 g specific force) | ±400 | 100 Hz |
| `gyro_x` | float | deg/s | 3 | ±1 (roll not simulated) | ±5000 | 100 Hz |
| `gyro_y` | float | deg/s | 3 | ±1 | ±5000 | 100 Hz |
| `gyro_z` | float | deg/s | 3 | ±30 (synthetic parachute swing) | ±5000 | 100 Hz |
| `barometric_pressure` | float | Pa | 1 | ~97 400 … 101 330 | 10 000 … 120 000 | 50 Hz |
| `altitude` | float | m | 2 | 0 … ~330 (above pad) | −200 … 10 000 | 50 Hz |
| `vertical_velocity` | float | m/s | 2 | −6 … +81 | ±500 | log rate |
| `temperature` | float | °C | 2 | 18 … 24 (synthetic) | −60 … 125 | 1 Hz |
| `latitude` | float | deg | 7 | fictitious origin 0° ± 0.002° | ±90 | 1 Hz |
| `longitude` | float | deg | 7 | fictitious origin 0° ± 0.002° | ±180 | 1 Hz |
| `gps_altitude` | float | m (MSL) | 1 | site + 0 … ~340 | −500 … 20 000 | 1 Hz |
| `gps_fix` | int | — | 0 | 0 (no fix), 3 | 0 … 3 | 1 Hz |
| `gps_satellites` | int | count | 0 | 3 … 9 | 0 … 64 | 1 Hz |
| `battery_voltage` | float | V | 3 | 4.03 … 4.10 (synthetic discharge) | 0 … 5.5 | 1 Hz |
| `separation_detected` | int | 0/1 | 0 | 0 → 1 after apogee | 0 … 1 | 50 Hz |
| `quality_flags` | int | bitmask | 0 | 0 | 0 … 65535 | log rate |
| `crc16` | hex | — | 4 hex digits | — | CRC-16/CCITT-FALSE of the row's other fields as written | log rate |

**Validity / status flags** (`quality_flags`): bit 0 accelerometer, 1 gyro, 2 barometer, 3 temperature, 4 GNSS,
5 battery value rejected in this frame; bit 6 timestamp gap (> 3 nominal periods). A rejected value is written empty
and its bit is set; the raw value is not kept.

**Freshness:** slow sensors appear only in frames where a new sample arrived (about once per second).

## 3. Sensor-level replay input (`simulation/data/sample_flight.csv`)

Raw sensor samples on a uniform time grid, for `simulation/avionics_replay.py`. Columns (in this order):
`timestamp`, `data_source`, then the sensor fields of §2 (`imu_accel_x` … `gyro_z`, `barometric_pressure`,
`temperature`, `latitude`, `longitude`, `gps_altitude`, `gps_fix`, `gps_satellites`, `battery_voltage`,
`separation_detected`). Rules:

- One row per grid tick (50 Hz in the sample; the grid period is the median time step). `timestamp` has 3 decimals.
- An empty cell = that sensor produced no sample at that tick. A sensor whose columns are all absent is treated as not
  installed (e.g. no GNSS).
- Values are written as the sensor produced them, **including invalid ones** (`nan`, out-of-range): validation is the
  flight computer's job and is part of what the replay tests.
- Rows with unreadable, duplicate or backwards timestamps, or off the grid, are skipped and counted.
- `data_source` must be identical in every row, and a FLIGHT dataset is refused unless flight data are explicitly
  enabled (`--allow-flight`), which is only appropriate for a genuine, mentor-reviewed flight record.
- Bench recordings use the same format and live in `avionics/bench_data/` (see that folder's README).

The sample is a **synthetic software test dataset, not flight data**. Its truth events and scripted faults are listed in
`simulation/data/sample_flight.meta.json`.

## 4. Replay outputs (`simulation/results/avionics_replay/`)

`replay_estimates.csv`, one row per tick:

| Column | Type | Unit | Decimals | Meaning |
|---|---|---|---|---|
| `timestamp` | float | s | 3 | tick time |
| `flight_state` | enum | — | — | classifier state after this tick |
| `est_altitude_m` | float | m | 2 | Kalman-filter altitude above the pad |
| `est_vertical_velocity_mps` | float | m/s | 2 | Kalman-filter vertical velocity |
| `baro_altitude_m` | float | m | 2 | barometric altitude of a valid sample in this tick (empty otherwise) |
| `imu_ok` | 0/1 | — | 0 | valid IMU sample within 3 nominal periods |
| `baro_ok` | 0/1 | — | 0 | same, barometer |
| `gnss_ok` | 0/1 | — | 0 | same, GNSS message (independent of fix) |
| `temp_ok` | 0/1 | — | 0 | same, temperature |
| `battery_ok` | 0/1 | — | 0 | same, battery monitor |
| `gps_fix` | int | — | 0 | latest valid fix type |

`replay_log.csv` is an onboard log in the §2 format. `replay_telemetry.csv` lists the telemetry frames as decoded by the
ground-station receiver (the §5 fields plus `rx_time_s`). `replay_events.json` holds the summary and the event timeline:
flight events (`LIFTOFF`, `BURNOUT`, `APOGEE`, `LANDING`), sensor-health changes (`<SENSOR>_OK` / `<SENSOR>_STALE`),
rejected samples (`<SENSOR>_INVALID_SAMPLE`) and GNSS fix changes, each with `time_s` and `kind`.

## 5. Telemetry packet v2 (41 bytes)

Little-endian, fixed point, CRC-16/CCITT-FALSE over bytes 0–38. Full byte table in
`avionics/firmware/telemetry/packet.py`. Summary:

| Field | Encoding | Unit / resolution |
|---|---|---|
| sync, version | `A5 66`, 2 (decoder also accepts 1) | — |
| flags | bit 0 SIMULATED, 1 GPS valid, 2 separation, 3 `imu_ok`, 4 `baro_ok`, 5 `gnss_ok`, 6 `temp_ok`, 7 `battery_ok` | — |
| seq | uint16, wraps | — |
| time | uint32 | ms |
| flight state, GPS fix, satellites | uint8 each (255 = unknown) | — |
| altitude, GNSS altitude | int32 | 0.1 m |
| vertical velocity, axial / total acceleration, temperature | int16 | 0.01 m/s, 0.01 m/s², 0.01 °C |
| latitude, longitude | int32 | 10⁻⁷ deg |
| battery | uint16 | mV |

Missing values use the most negative signed value (or the unsigned maximum); out-of-range values saturate. Health bits
in a v1 packet are unknown (decoded as `None`).

## 6. Units, conventions and known conversion limits

- Body frame: +z toward the nose along the rocket axis. Accelerometers report **specific force** (+9.81 m/s² on +z on
  the pad).
- `altitude` is barometric altitude above the pad reference pressure using the ISA formula with the sea-level
  standard temperature. **Known limit:** above a pad at elevation E the height is overestimated by about
  0.0065 × E / (288.15 − 0.0065 × E), i.e. 1.1 % at a 500 m pad, plus any non-standard-temperature error. The planning
  launch site is at 0 m (`simulation/sim_config.json`), so the current results are unaffected; for a real site, derive
  the reference temperature from the measured pad temperature (future work).
- Latitude / longitude in the examples are relative to a fictitious origin (0°, 0°); they are not a launch site.
