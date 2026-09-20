# ASTRA-66 avionics: data flow

All data described here are **SIMULATED** until hardware exists. Schema: `avionics/data/schema/flight_data_schema.json`.

## 1. End-to-end path

```
sensor (simulated today)
  │  SensorSample(sensor, t_us, values)             SENSOR LAYER
  ▼
acquisition: fixed-rate schedule, µs timestamp, freshness tracking
  │
  ├─► processing: pad reference → altitude → Kalman filter → state classifier     FLIGHT-DATA PROCESSING
  │
  ├─► frame (fresh samples + seq, timestamp, vertical_velocity, flight_state)
  │     └─► DataLogger: timestamp check → schema validation → quality flags → CSV / JSON-lines (+CRC-16)   DATA LOGGER
  │           └─► microSD card (hardware) / file (today) ─► copied after recovery ─► POST-FLIGHT ANALYSIS
  │
  └─► telemetry frame (latest values) → 41-byte packet v2 (+CRC-16, SIMULATED flag, sensor health) → link          TELEMETRY
        └─► ground-station receiver → dashboard + received-telemetry log                          GROUND STATION
```

## 2. Rates

| Stream | Rate | Notes |
|---|---|---|
| Flight-computer tick | 100 Hz | = IMU rate |
| IMU | 100 Hz | requirement ≥ 100 Hz to SD (engineering package §8) |
| Barometer | 50 Hz | ≥ 20 Hz needed for apogee timing |
| Separation breakwire | 50 Hz | logging only |
| GNSS | 1 Hz | minimum; more if the selected module allows |
| Temperature, battery | 1 Hz | slow quantities |
| Log frames | 50 Hz (example) / ≥ 100 Hz (hardware target) | example decimated to keep the repository small |
| Telemetry packets | 5 Hz | package concept: 2–5 Hz summaries; full-rate data stay on the SD card |

## 3. Freshness rule (what an empty cell means)

A log frame contains the samples taken since the previous frame. Slow sensors therefore appear only in about one
frame per second; in other frames their cells are empty. An empty cell also appears when a value was rejected by
validation (then `quality_flags` has the sensor's bit set) or when the sensor delivered nothing (dropout).
Telemetry is different: it always carries the latest valid value, because the ground display needs a current reading;
since Phase 5 the packet also carries per-sensor health bits, so a value from a sensor that has gone silent is marked stale.

## 4. Validation and error handling at each stage

| Stage | Check | Action |
|---|---|---|
| Acquisition | sensor returns nothing | no sample; frame cell stays empty |
| Processing | NaN / inf / unparseable / outside the plausibility range (Phase 5: schema check before processing) | never reaches the estimator, classifier or telemetry; counted; sensor health drops after 3 nominal periods without a valid sample |
| Logger | required field missing / invalid, time duplicate or backwards | frame rejected and counted |
| Logger | optional value non-finite, unparseable or outside the plausibility range | written empty, sensor bit set in `quality_flags`, counted |
| Logger | time gap > 3 nominal periods | frame kept, bit 6 set |
| Telemetry | value outside the packet range | saturates at the limit (never wraps) |
| Receiver | wrong length / sync / version / CRC | packet rejected and counted |
| Receiver | sequence gap / repeat | counted as missing / duplicate (16-bit wrap aware) |
| Reader (analysis) | wrong column count, CRC mismatch, required field, time order | row dropped, reported by reason |

## 5. Data-source labelling

| Where | Label |
|---|---|
| Log row | `data_source` = SIMULATED or HARDWARE |
| Log metadata sidecar (`*.meta.json`) | `data_source`, title "NOT FLIGHT DATA", truth profile, seeds |
| Telemetry packet | flags bit 0 = SIMULATED (bits 3–7 = sensor health, packet v2) |
| Ground station | banner "SIMULATED TELEMETRY: not flight data" |
| Analysis plots and report | subtitle / banner "SIMULATED DATA (not flight data)" |

## 6. Example data in this repository

| File | Content |
|---|---|
| `avionics/data/example/example_flight_simulated.csv` | 4547 frames at 50 Hz: 10 s on the pad, then a replay of the existing 1-DOF trajectory (PLACEHOLDER propulsion) |
| `avionics/data/example/example_flight_simulated.meta.json` | Counts, detected events, truth events, assumptions |
| `avionics/data/example/example_flight_simulated_telemetry_capture.csv` | Received packets (hex) after a simulated link with 2 % loss and 1 % corrupted packets |
| `avionics/analysis/results/example_flight_simulated/` | Plots, `flight_summary.json` and `flight_report.md` from the analysis tool |

Regenerate with `python -m avionics.firmware.simulate_flight` and
`python avionics/analysis/flight_data_analysis.py avionics/data/example/example_flight_simulated.csv`.
