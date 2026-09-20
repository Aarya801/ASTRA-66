# ASTRA-66 — Hardware integration: what is software, what is synthetic, what is missing

> **No avionics hardware has been selected, bought, built, weighed or tested.** This document separates the four
> things that are easy to confuse in a software-first project: defined interfaces, synthetic data, unselected
> hardware, and measurements that do not exist yet. The item-by-item audit is
> `HARDWARE_INTEGRATION_STATUS.md`; the generic hardware classes are `../avionics/HARDWARE_MAPPING.md`.
> ASTRA-66 is NOT FLIGHT CERTIFIED.

## 1. Software-defined interfaces (exist and are tested)

These are real, working software contracts. A hardware driver plugs in behind them without changing anything above.

| Interface | Contract | Defined in |
|---|---|---|
| `Sensor` | `name`, `rate_hz`, `simulated`; `due(t_us)`; `sample(t_us)` → `SensorSample` or `None`. **Input only** | `avionics/firmware/sensor_interfaces/base.py` |
| `LogSink` | `open(schema)`, `write(record)`, `flush()`, `close()` — a microSD writer implements this | `avionics/firmware/logging/logger.py` |
| `TelemetryLink` | `send(packet, t_s)`, `receive()`; the hardware link needs a radio driver with `transmit` / `receive` | `avionics/firmware/telemetry/link.py` |
| Flight-data schema | 23 fields with units, rates, plausibility limits and a CRC-16 per row (v1.1.0) | `avionics/data/schema/flight_data_schema.json` |
| Telemetry packet v2 | 41 bytes, little-endian, sequence number, CRC-16, SIMULATED flag, sensor-health bits | `avionics/firmware/telemetry/packet.py` |
| Data-source modes | `SYNTHETIC`, `BENCH`, `FLIGHT` (FLIGHT disabled until a real record exists) | `avionics/firmware/data_source.py` |
| Ground-station API | `GET /api/telemetry?after=N` → JSON frames, link statistics | `avionics/ground_station/server.py` |

A placeholder driver (`HardwareSensorPlaceholder`) refuses to return data, so simulated and real sources can never be
silently mixed, and the hardware telemetry link refuses to start without a radio driver.

## 2. Synthetic and test data (exist, clearly labelled)

| Dataset | What it is | Label |
|---|---|---|
| `avionics/data/example/example_flight_simulated.csv` | 4547 logged frames from the simulated sensors on the project trajectory (placeholder motor) | `SIMULATED` (legacy alias of SYNTHETIC) |
| `simulation/data/sample_flight.csv` | 2162-row sensor-level dataset with five scripted faults, for replay testing | `SYNTHETIC` |
| `avionics/bench_data/example_bench_record.csv` | Column template for future bench records; 501 rows of generated pad data | `SYNTHETIC` — explicitly *not* a measurement |
| `simulation/results/avionics_replay/` | Estimates, telemetry, log and event timeline from replaying the sample | derived from SYNTHETIC |

Rules that keep this honest: the mode is in every row, the logger refuses a frame whose mode differs from its own,
plots and reports print the mode, and `FLIGHT` is refused by the software.

## 3. Hardware not yet selected

Every item below is **COMPONENT TO BE SELECTED**. The repository names example classes only because the original BOM
listed them for planning; no datasheet has been checked and nothing has been bought.

Microcontroller · IMU · barometer · GNSS module and antenna · temperature sensor · battery-monitor divider ·
1S LiPo battery · 3.3 V regulator · power switch · microSD card and socket · telemetry radio pair (band and power
must be legal where operated) · buzzer and LED · optional camera · ground-station radio.

Selection procedure and per-subsystem requirements: `HARDWARE_SELECTION_CHECKLIST.md`.

## 4. Hardware that must be measured

Nothing in this repository has been measured. The following are needed before any of the "fits" or "mass" statements
mean anything physical:

1. Real board outlines **with headers and connectors**, against the CAD placeholder envelopes.
2. Mass of every avionics and payload item, and of each assembled module (currently all estimates:
   electronics 59 g, GPS 20 g, battery 27 g, camera 35 g, switch allowance 12 g).
3. Centre of gravity of the assembled vehicle (balance method plus a moment cross-check).
4. Tube, coupler and motor-tube diameters from the purchased stock (3 stations × 2 axes).
5. Avionics-bay sealing and static-port pressure lag.
6. Battery cell size, retention and pad endurance.
7. Harness: connector passage through the ⌀8 mm grommet, wire count, bend radius.
8. Radio: antenna placement, interference with GNSS, and usable range.
9. Printed-part fits (shoulder, fin guide slot, heat-set inserts) from fit coupons.

Procedure: `MASS_MEASUREMENT_PROCEDURE.md`. Open CAD-side warnings: `CAD_AVIONICS_INTEGRATION.md`.

## 5. Future physical validation

In order, and none of it has started:

1. Mentor-approved component selection, recorded with datasheet references.
2. Measure and weigh; update `cad/parts/COTS_envelopes.scad` and `analysis/analysis.py`; re-run the pipeline
   (including `--with-cad`) so the CAD, mass budget and simulation stay consistent.
3. Bench tests B-01…B-14 (`AVIONICS_BENCH_TEST_PLAN.md`), recording data as `BENCH` and replaying it through the same
   software.
4. Hardware-in-the-loop comparison: bench data versus the simulation, using the existing analysis tool.
5. Only then, and only with a qualified mentor and range approval: motor selection with published data, mass and CG
   with the motor fitted, flight-readiness review.

Until every one of those steps has evidence in the repository, ASTRA-66 remains a software and design project:
**NOT FLIGHT CERTIFIED**.
