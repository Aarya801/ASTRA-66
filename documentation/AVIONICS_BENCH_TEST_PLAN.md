# ASTRA-66 — Avionics bench-test plan (electronics and software only)

> **Scope: a bench, a laptop and the avionics electronics.** No motor, no igniter, no pyrotechnics, no energetic
> device and no deployment hardware are involved in any step; the avionics have no output that could drive one.
> Propulsion stays an external, commercially certified component and is not part of any test here. Nothing in this
> plan makes ASTRA-66 flight certified: the project is **NOT FLIGHT CERTIFIED**, and passing every test proves only
> that the electronics and software behave as specified on the bench.
>
> **Nothing below has been performed.** No hardware exists yet (`documentation/HARDWARE_INTEGRATION_STATUS.md`).

## How to run and record a test

1. Select the components first (`documentation/HARDWARE_SELECTION_CHECKLIST.md`); a test without a recorded part and
   datasheet is not evidence.
2. Record raw data in the standard sensor-level format with `data_source = BENCH` and a meta file
   (`avionics/bench_data/README.md`).
3. Process the recording with the same pipeline used for synthetic data, so the software path is identical:
   `python simulation/avionics_replay.py avionics/bench_data/<record>.csv --out simulation/results/<name>`.
4. Write the outcome (pass / fail, measured numbers, anomalies) into the bench record's meta file; never edit measured
   values.
5. Work with a second person present for anything involving LiPo charging, and follow the range's battery rules.

Safety on the bench: keep the battery disconnected while wiring; check polarity before the first power-up; treat every
GPIO as input-only; if the radio is used, transmit only on a band and at a power level legal where you are.

## Tests

| ID | Test | Objective | Outline | Pass criteria (targets, to be agreed with the mentor) | Evidence |
|---|---|---|---|---|---|
| B-01 | Power-up verification | The board powers up safely on the intended supply | Bench supply or charged cell at nominal voltage, current meter in series; power through the AV-307 switch; observe the buzzer / LED annunciation | No component above its rated temperature; current draw within the budget; switch reliably powers the electronics on and off; no brown-out at the lowest planned cell voltage | Measured idle and active current; photo of the setup; notes |
| B-02 | Sensor detection | Every selected sensor is found on its bus and responds | Scan I²C / SPI / UART at start-up; read one sample from each sensor; unplug one sensor and repeat | All expected devices detected; the flight computer reports a missing sensor as unhealthy instead of failing; breakwire continuity reads correctly (open and closed) | Start-up log; health flags |
| B-03 | IMU data sanity | Accelerometer and gyro produce physically sensible values | With the bay stationary, log 60 s in six orientations (±x, ±y, ±z up); rotate slowly by a known angle about each axis | Magnitude ≈ 1 g at rest in every orientation; axis signs match the +z-toward-nose convention; gyro bias and noise recorded; integrated rotation within a few per cent of the applied angle | Bench record + measured bias / noise table |
| B-04 | Pressure sensor sanity | Barometric pressure and derived altitude behave correctly | Log at rest; compare with a reference barometer or local QNH; move the bay a known height (stairwell, lift); optionally a slow syringe / bag test on the sealed bay | Reading within the sensor's stated accuracy of the reference; a known height change gives the right altitude change within the agreed tolerance; noise at rest recorded | Bench record; reference readings |
| B-05 | GNSS acquisition | The receiver gets and keeps a usable fix | Cold start outdoors; warm start; repeat with the module inside the assembled airframe; then with the radio transmitting | Time to first fix recorded for each case; fix type and satellite count logged; fix retained (or documented loss) with the radio active | Bench record; times and satellite counts |
| B-06 | Data logging | Frames reach the card intact at the target rate | Log at the target rate for several minutes while all sensors run | No missing sequence numbers; every row's CRC-16 verifies; frames written = frames expected within the agreed margin | Log file + reader report (`read_flight_log`) |
| B-07 | Packet generation | Telemetry packets are produced correctly from live data | Run the flight computer with the radio disabled but packets captured over USB | Packet rate as configured; fields match the log within quantisation; SIMULATED flag clear on real data; health bits follow the sensors | Captured packets; decoder output |
| B-08 | Packet integrity | Corrupted packets are detected, never accepted | Inject bit errors in the capture (offline) and repeat with a real link if available | Every corrupted packet rejected by CRC; no corrupted packet reaches the display | Receiver statistics |
| B-09 | Receiver / ground-station communication | The ground station shows live data from the real link | Airborne module and ground module at bench distance; run `avionics/ground_station/server.py`; then repeat at increasing distance | Dashboard updates continuously; values match the onboard log; link statistics plausible; measured usable range recorded | Screenshot; received-telemetry log |
| B-10 | Packet-loss handling | Loss is measured and displayed, never hidden | Move out of range / shield the antenna; return | Missing sequence numbers counted; display marks stale data; no false values shown; recovery works | Link statistics over the run |
| B-11 | Timestamp consistency | The time base is monotonic and correctly scaled | Log for longer than one counter wrap if the counter is 32-bit µs (~72 min); compare elapsed log time with a stopwatch | Timestamps strictly increasing; no duplicates; wrap handled; drift against wall-clock time recorded | Long log + reader report |
| B-12 | Battery monitoring | Reported voltage matches reality | Compare the logged voltage with a multimeter from full charge down to the agreed cut-off, including while transmitting | Agreement within the agreed tolerance across the range; sag under transmit recorded | Calibration table |
| B-13 | Long-duration logging | The system survives a realistic pad hold | Run a full pad-hold duration (target from the mission plan) with all sensors, logging and telemetry active | No data gaps beyond the agreed limit; card not full; temperature stable; battery endurance with margin | Long bench record; endurance figure |
| B-14 | Power-down / data preservation | An unexpected power cut does not destroy the log | Pull power at a random time during logging; repeat several times; then read the card | The file is readable; at most the final row is damaged, and the reader reports it; no earlier rows corrupted | Reader report per trial |

## Exit criteria for the bench phase

- B-01…B-14 executed with the selected hardware, each with a bench record and a meta file.
- Every measured value that the analysis uses (masses, dimensions, endurance) entered through the documented workflow
  (`documentation/MASS_MEASUREMENT_PROCEDURE.md`) and the pipeline re-run.
- Remaining open items listed honestly in `documentation/HARDWARE_INTEGRATION_STATUS.md`.
- A mentor has reviewed the results. Flight remains subject to a complete flight-readiness review and range approval;
  the bench phase alone never makes the project flight certified.
