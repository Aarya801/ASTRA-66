# avionics/firmware/

Hardware-independent reference implementation of the flight-computer software, in standard-library Python. It runs
today against **SIMULATED** sensors; the same structure is meant to be ported to the selected microcontroller
(COMPONENT TO BE SELECTED) later. It is not flight software and is not flight certified.

| Module | Layer | Content |
|---|---|---|
| `sensor_interfaces/base.py` | Sensor layer | `Sensor` interface, `SensorSample`, fixed-rate scheduling, `HardwareSensorPlaceholder` (refuses to read) |
| `sensor_interfaces/catalog.py` | Sensor layer | Requirement table for every sensor (all COMPONENT TO BE SELECTED) |
| `sensor_interfaces/simulated.py` | Sensor layer | Truth profiles (replay of the existing trajectory, synthetic test profile), simulated IMU / barometer / GNSS / temperature / battery / breakwire, seeded noise, fault injection |
| `flight_state/estimator.py` | Processing | Pad reference pressure, ISA pressure → altitude, 2-state Kalman filter (barometer-only after apogee) |
| `flight_state/classifier.py` | Processing | PRELAUNCH → ASCENT → COAST → DESCENT → LANDED, forward only, with the transition assumptions in its docstring. Data label only |
| `logging/schema.py` | Logger | Loads the schema; validates, formats and parses values |
| `logging/timebase.py` | Logger | Counter unwrapping (32-bit µs wrap), timestamp monitor (duplicate, backwards, gap) |
| `logging/logger.py` | Logger | `DataLogger`, CSV and JSON-lines sinks with CRC-16, memory sink, metadata sidecar |
| `logging/reader.py` | Logger | Tolerant log reader used by the analysis |
| `telemetry/packet.py` | Telemetry | 41-byte packet v2 (v1 still decoded): encode / decode, sensor-health bits, saturation, missing-value sentinels, CRC-16 |
| `telemetry/link.py` | Telemetry | `SimulatedTelemetryLink` (loss, bit errors) and `HardwareTelemetryLink` (interface only; no radio selected) |
| `crc.py` | shared | CRC-16/CCITT-FALSE |
| `flight_computer.py` | all | Main loop: sensors → processing → logger + telemetry. No outputs other than log and link |
| `simulate_flight.py` | tool | Runs a simulated flight and writes a log, metadata and a telemetry capture |

## Run

```bash
python -m avionics.firmware.simulate_flight                       # regenerates avionics/data/example/
python -m avionics.firmware.simulate_flight --out-dir out --seed 3 --loss 0.1
```

Run it as a module (`-m`) from the repository root. The package `avionics.firmware.logging` must always be imported
through its full name; putting `avionics/firmware` itself on `sys.path` would shadow Python's standard `logging`.

## Porting notes (future hardware work)

- Keep the layer boundaries: one driver per selected sensor behind `Sensor`; an SD-card sink behind `LogSink`; a radio
  driver behind `HardwareTelemetryLink`.
- Keep integer microsecond timestamps from a free-running timer and unwrap them (`logging/timebase.py`).
- Re-derive the classifier thresholds and sensor ranges with the certified motor's published data, then re-run the
  tests with a trajectory built from that data.
- Measure loop timing, SD write latency and power on the bench before any flight consideration.
