# avionics/analysis/

Post-flight analysis of a flight-data log that follows `avionics/data/schema/flight_data_schema.json`.

```bash
python avionics/analysis/flight_data_analysis.py avionics/data/example/example_flight_simulated.csv
python avionics/analysis/flight_data_analysis.py LOG.csv --out some/folder
```

## Outputs (default folder `results/<log name>/`)

| Output | Content |
|---|---|
| `altitude_vs_time.svg` | Barometric altitude above the pad, apogee marked |
| `velocity_vs_time.svg` | Vertical velocity derived from barometric altitude, and the logged onboard estimate |
| `acceleration_vs_time.svg` | Axial specific force and acceleration magnitude |
| `temperature_vs_time.svg` | Bay temperature |
| `battery_voltage_vs_time.svg` | Battery voltage |
| `gps_track.svg` | Ground track relative to the first fix (only if the log has GNSS fixes) |
| `flight_summary.json`, `flight_report.md` | Data quality, derived statistics, event times |

The committed example output is in `results/example_flight_simulated/`. It is **SIMULATED DATA**, derived from the
PLACEHOLDER propulsion input, and every plot and report says so.

## Derived statistics (all CALCULATED from the log)

| Statistic | Method |
|---|---|
| Apogee | maximum of the 0.3 s moving average of barometric altitude |
| Max vertical velocity | derivative of smoothed altitude (smoothing blunts sharp peaks by a few m/s); onboard estimate reported alongside |
| Max axial specific force / acceleration magnitude | maximum accelerometer reading |
| Descent rate | median derived descent speed from 2 s after apogee to 1 s before landing |
| Event times | state-label time minus the classifier's confirmation time; apogee = time of maximum smoothed altitude |
| Burn, time to apogee, flight and descent durations | differences of event times |
| Temperature, battery | start, minimum, maximum, mean, end; battery drop = start − minimum |
| GNSS | fixes, first and last fix, last-fix and maximum distance from the first fix, track length |
| Data quality | rows read and usable, dropped rows by reason, rejected values by field, timestamp gaps, CRC check |

If the log has no `flight_state` column values, states are reconstructed offline with the same classifier.
