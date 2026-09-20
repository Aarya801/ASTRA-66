# Post-flight analysis: `example_flight_simulated.csv`

> **SYNTHETIC DATA: not flight data.** Computer-generated; where the truth trajectory is the project simulation it uses the PLACEHOLDER propulsion input. The values show that the software works, not how a real flight would behave.

## Data quality

- Rows read: 4547; usable: 4547; dropped: {'malformed': 0, 'crc_mismatch': 0, 'rejected': 0, 'non_monotonic': 0, 'duplicate': 0}
- Row CRC verified: True; timestamp gaps: 0
- Rejected values by field: none
- Flight states: logged flight_state column

## Key results (CALCULATED from the log)

| Quantity | Value | Time (s) |
|---|---|---|
| Apogee (barometric, above pad) | 328.26 m | 18.56 |
| Max vertical velocity (derived) | 79.22 m/s | 11.5 |
| Max vertical velocity (onboard estimate) | 80.13 m/s | 11.44 |
| Max axial specific force | 82.81 m/s² (8.44 g) | 10.08 |
| Mean descent rate (median) | 5.12 m/s | |
| Burn duration | 1.44 s | |
| Time to apogee | 8.53 s | |
| Flight duration | 72.71 s | |
| Descent duration | 64.18 s | |
| Temperature min / max | 18.85 / 23.97 °C | |
| Battery start / min / drop | 4.101 / 4.026 / 0.075 V | |
| GNSS: last fix from first fix | 162.3 m (89 fixes) | 90.0 |

## Events

Estimated event times (state label time minus the classifier's confirmation time (liftoff, burnout, landing); apogee = time of maximum smoothed barometric altitude):

| Event | Time (s) |
|---|---|
| liftoff | 10.03 |
| burnout | 11.47 |
| apogee | 18.56 |
| landing | 82.74 |

State labels as logged (first time each state appears):

| State | Time (s) |
|---|---|
| PRELAUNCH | 0.0 |
| ASCENT | 10.08 |
| COAST | 11.52 |
| DESCENT | 18.96 |
| LANDED | 85.74 |

## Plots

- [altitude_vs_time.svg](altitude_vs_time.svg)
- [velocity_vs_time.svg](velocity_vs_time.svg)
- [acceleration_vs_time.svg](acceleration_vs_time.svg)
- [temperature_vs_time.svg](temperature_vs_time.svg)
- [battery_voltage_vs_time.svg](battery_voltage_vs_time.svg)
- [gps_track.svg](gps_track.svg)
