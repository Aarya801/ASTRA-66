# avionics/ground_station/

Ground-station **prototype**: decodes telemetry packets, keeps link statistics and shows the data in a browser
dashboard. It has only ever been run on **SIMULATED TELEMETRY**. It is a development tool, **not validated for real-time
flight use**, and like the rest of the avionics it is **not flight certified**.

| File | Content |
|---|---|
| `receiver.py` | `GroundStationReceiver`: decode, reject bad packets, count missing / duplicate sequence numbers, CSV log; capture-file reader |
| `server.py` | Local HTTP server (standard library): replays a capture, runs a fresh simulated flight, or replays a sensor-level dataset through the flight-computer software; `GET /api/telemetry?after=N` |
| `dashboard/index.html` | Self-contained dashboard (no external files): flight state, sensor health (IMU / baro / GNSS / temperature / battery), GPS status, battery status, packet count and loss, latest telemetry time, altitude, vertical velocity, acceleration, temperature, GPS position and track, battery voltage; light and dark themes |

## Run

```bash
python avionics/ground_station/server.py                      # replay the committed SIMULATED capture
python avionics/ground_station/server.py --simulate --speed 2 --loop
python avionics/ground_station/server.py --sensors simulation/data/sample_flight.csv   # sensor-level replay (Phase 5)
```

Battery status uses 1S planning thresholds (LOW below 3.6 V, CRITICAL below 3.4 V); these are assumptions, not values
from a datasheet. Sensor health comes from telemetry packet v2 (a v1 capture shows "?").

Open http://127.0.0.1:8766/ . The server binds to localhost only. The banner always states the data source; with the
current software it is always "SIMULATED TELEMETRY: not flight data".

## Limits

- REAL HARDWARE TELEMETRY is not implemented: no radio has been selected (COMPONENT TO BE SELECTED). The hardware link
  class refuses to start without a radio driver.
- The server replays packets at their recorded times. Latency, throughput and robustness with a real radio and a real
  serial connection have not been measured.
- "Missing sequence numbers" counts packets dropped in the air and packets rejected as corrupted.
