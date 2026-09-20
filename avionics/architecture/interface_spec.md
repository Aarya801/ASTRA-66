# ASTRA-66 avionics: interface specification

> Draft. No avionics component has been selected: every hardware item below is **COMPONENT TO BE SELECTED**. Ranges
> and rates are **requirements** (class C assumptions), not manufacturer specifications. Where a requirement is derived
> from the simulation it uses the PLACEHOLDER propulsion input and must be re-derived with the certified motor's data.
> The candidate classes repeat `avionics/electronics.csv`; their datasheets have not been checked. Nothing here has
> been built or tested, and ASTRA-66 is NOT flight certified.

## 1. Sensor interfaces

The same content is held in code in `avionics/firmware/sensor_interfaces/catalog.py` (tested against the schema).

### 1.1 Inertial measurement unit (IMU)
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (candidate class: 6-axis ±32 g breakout) |
| Measurement | Specific force (3 axes) and angular rate (3 axes), body frame, +z toward the nose |
| Schema fields / unit | `imu_accel_x`, `imu_accel_y`, `imu_accel_z` m/s² · `gyro_x`, `gyro_y`, `gyro_z` deg/s |
| Required range | accel ≥ ±16 g (2× the 7.4 g PLACEHOLDER peak); gyro ≥ ±1000 deg/s (roll not simulated: assumption) |
| Sampling rate | 100 Hz (≥ 100 Hz to SD) |
| Interface | I²C or SPI (SPI preferred for rate) |
| Purpose | Liftoff / burnout detection, acceleration record, estimator input |
| Failure considerations | saturation; temperature bias; vibration aliasing; mounting misalignment; bus lock-up (stale data); unknown orientation under the parachute (handled: estimator goes barometer-only after apogee) |

### 1.2 Barometric pressure sensor
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (candidate class: BMP390 / MS5611 breakout) |
| Measurement | Static pressure; converted on board to altitude above the pad (ISA) |
| Schema fields / unit | `barometric_pressure` Pa · `altitude` m |
| Required range | 30 000–110 000 Pa |
| Sampling rate | 50 Hz (≥ 20 Hz for apogee timing) |
| Interface | I²C or SPI |
| Purpose | Altitude, apogee and landing detection, estimator measurement, launch backup |
| Failure considerations | static-port errors; light and draughts on the die (foam cover); temperature drift; pressure transients at separation; stale data |

### 1.3 GPS / GNSS receiver
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (candidate class: u-blox M8/M9/M10 module + patch antenna) |
| Measurement | Latitude, longitude, altitude MSL, fix type, satellites |
| Schema fields / unit | `latitude`, `longitude` deg · `gps_altitude` m · `gps_fix` · `gps_satellites` |
| Required range | position for recovery; keep or regain fix at the flight dynamics |
| Sampling rate | 1 Hz minimum |
| Interface | UART (NMEA or binary protocol) |
| Purpose | Recovery location, ground track, cross-check of barometric altitude |
| Failure considerations | cold-start delay; loss of lock in boost; antenna shadowing; interference from the telemetry radio; large altitude noise |

### 1.4 Temperature sensor
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (candidate class: TMP117 breakout, or the barometer's internal channel) |
| Measurement | Avionics-bay air temperature |
| Schema field / unit | `temperature` °C |
| Required range | −20 to +60 °C (assumed environment) |
| Sampling rate | 1 Hz |
| Interface | I²C |
| Purpose | Environmental record; context for barometer and battery |
| Failure considerations | self-heating from nearby parts; measures board rather than air; stale data |

### 1.5 Battery monitor
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (MCU ADC + resistor divider, values chosen with the MCU) |
| Measurement | Battery terminal voltage (1S LiPo, nominal 3.0–4.2 V) |
| Schema field / unit | `battery_voltage` V |
| Required range | 0–5 V at the divider input |
| Sampling rate | 1 Hz |
| Interface | ADC |
| Purpose | Pad-hold endurance, brown-out diagnosis, ground-station go/no-go display |
| Failure considerations | divider tolerance (calibrate); sag under radio transmit; ADC reference drift |

### 1.6 Separation sense (breakwire)
| Item | Specification |
|---|---|
| Component | COMPONENT TO BE SELECTED (thin enamel wire + 2-pin connector, per `avionics/electronics.csv`) |
| Measurement | Continuity of a loop across joint I-03 |
| Schema field / unit | `separation_detected` 0/1 |
| Sampling rate | 50 Hz |
| Interface | GPIO **input** with pull-up |
| Purpose | Logs when the airframe separated (logging only) |
| Failure considerations | broken during handling (pre-flight continuity check); connector bounce |

### 1.7 Flight computer, storage and radio
| Item | Specification |
|---|---|
| Microcontroller | COMPONENT TO BE SELECTED (candidate classes in `avionics/electronics.csv`). Needs: I²C + SPI + UART + ADC, ≥ 100 Hz loop with margin, a free-running µs timer |
| Data storage | microSD over SPI: COMPONENT TO BE SELECTED. Needs a sustained write rate above the log rate × row size (about 110 bytes per row) with margin |
| Telemetry radio | COMPONENT TO BE SELECTED. Must operate only on a band and at a power level that are legal where it is used. 41-byte packets at 5 Hz ≈ 205 B/s payload before radio overhead |

## 2. Software interfaces

| Interface | Defined in | Contract |
|---|---|---|
| `Sensor` | `avionics/firmware/sensor_interfaces/base.py` | `name`, `rate_hz`, `simulated`; `due(t_us)`; `sample(t_us)` → `SensorSample` or None. Input only |
| `LogSink` | `avionics/firmware/logging/logger.py` | `open(schema)`, `write(record)`, `flush()`, `close()` |
| `DataLogger` | same | `log(frame)` → (accepted, issues); `close()` writes the metadata sidecar |
| `TelemetryLink` | `avionics/firmware/telemetry/link.py` | `send(packet, t_s)`; `receive()` → [(t_s, bytes)]. Hardware link requires a radio driver with `transmit` / `receive` |
| Packet v2 | `avionics/firmware/telemetry/packet.py` | 41 bytes, little-endian, CRC-16/CCITT-FALSE, sensor-health flag bits (table in the module docstring; v1 still decoded) |
| Log file | `avionics/data/schema/flight_data_schema.json` | CSV header = field order; last column CRC-16 of the row |
| Ground-station API | `avionics/ground_station/server.py` | `GET /api/telemetry?after=N` → JSON (link label, stats, frames) |

There is **no actuator interface**. Any future interface that could command anything must stay outside this
repository's avionics code, be disabled by default, and be designed and approved only through qualified mentor and range
review. Nothing in the current design requires one: recovery uses the certified motor's own ejection.

## 3. Physical interfaces with the existing airframe (requirements only, no redesign)

The CAD (rev B) already provides these. The avionics must fit them; if a selected part does not, record it as an
interface requirement and update the CAD through the normal pipeline (`cad/build_cad.py` + validation). No CAD file was
changed in Phase 4.

| Interface | Existing provision | Avionics requirement |
|---|---|---|
| Electronics sled | `cad/parts/AV-306_electronics_sled.scad`: 10 M2.5 insert bosses on a 25 mm pitch, switch tower, zip-tie slots | Boards mount on M2.5 standoffs within the placeholder envelopes of `cad/parts/COTS_envelopes.scad` (MCU 21 × 8.5 × 50, IMU 14 × 4 × 14, barometer 13 × 4 × 13, microSD 20 × 4.5 × 26, radio 20 × 7 × 28 mm, all PLACEHOLDER). IMU hard-mounted near the axis |
| Battery | `cad/parts/AV-308_battery_cage.scad`, strap-retained | Cell width ≤ 28.8 mm (clears the rod sleeves); placeholder 55 × 28 × 9 mm |
| Power switch | AV-307 on the sled tower, reached through the switch band | The BOM calls it the "arming switch"; it only switches battery power to the electronics. It arms nothing |
| Static ports | 4 × ⌀2 mm (STATIC_PORT_D) at 45/135/225/315° through `cad/parts/AV-302_switch_band.scad` and `cad/parts/AV-301_coupler.scad` | Barometer in the sealed avionics bay, shielded from light and draughts (foam); port size per the selected sensor's guidance |
| GPS / sensor tray | `cad/parts/PL-202_gps_tray.scad` in the payload bay, 6 M2.5 bosses, under the service hatch | GNSS module + antenna within the 25 × 8 × 35 mm placeholder envelope; sky view forward, away from the radio antenna and battery |
| Harness | I-08: ⌀8 grommet through AV-303, keyed JST-GH/XH connectors | GNSS UART and power between payload bay and avionics bay; strain relief within 20 mm |
| Separation sense | Joint I-03 (AV-301 ↔ BO-401) | Breakwire loop across the joint, 2-pin connector |
| Temperature sensor | no dedicated envelope | Use the barometer's internal channel, or add the selected breakout's envelope on a free sled boss and re-run CAD validation |
| Mass allocation | analysis: EL-AV 59 g, EL-GPS 20 g, EL-BAT 27 g (assumptions, "weigh") | Weigh the selected parts and update `analysis/analysis.py` through the normal pipeline |
