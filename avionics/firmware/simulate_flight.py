"""Run the flight-computer software against SIMULATED sensors and write a flight-data log (+ telemetry capture).

    python -m avionics.firmware.simulate_flight                    # regenerates avionics/data/example/
    python -m avionics.firmware.simulate_flight --out-dir some/dir --seed 3 --loss 0.05

The default truth profile replays the existing 1-DOF trajectory (simulation/results/trajectory_baseline.csv), which
uses the PLACEHOLDER propulsion input. The output is SIMULATED data for software development only: it is not flight
data and not a prediction of any real flight.
"""
import os
import sys

if __package__ in (None, ""):          # run as a file: make the repository root importable, never avionics/firmware
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path[0] = _root
    __package__ = "avionics.firmware"

import argparse  # noqa: E402

from avionics.firmware.flight_computer import FlightComputer  # noqa: E402
from avionics.firmware.logging.logger import CsvLogSink, DataLogger  # noqa: E402
from avionics.firmware.sensor_interfaces.simulated import TrajectoryReplayProfile, simulated_sensor_suite  # noqa: E402
from avionics.firmware.telemetry.link import SimulatedTelemetryLink  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRAJECTORY = os.path.join(ROOT, "simulation", "results", "trajectory_baseline.csv")
EXAMPLE_DIR = os.path.join(ROOT, "avionics", "data", "example")
EXAMPLE_STEM = "example_flight_simulated"


def default_profile():
    return TrajectoryReplayProfile.from_csv(TRAJECTORY)


def run_simulated_flight(profile=None, out_dir=None, stem=EXAMPLE_STEM, sink=None, seed=0, faults=None,
                         log_rate_hz=50.0, telemetry_rate_hz=5.0, loss_prob=0.02, bit_error_prob=0.01, duration_s=None):
    """Simulate one flight. Writes <stem>.csv, <stem>.meta.json and <stem>_telemetry_capture.csv when out_dir is given
    (or logs to `sink`). Returns a dict with the detected events, logger summary, packets and link statistics."""
    profile = profile or default_profile()
    duration = duration_s if duration_s is not None else profile.duration
    meta = dict(
        title="ASTRA-66 SIMULATED flight-data example: NOT FLIGHT DATA",
        generator="python -m avionics.firmware.simulate_flight",
        truth_profile=profile.label,
        truth_events_s=dict(liftoff=round(profile.t_liftoff, 3),
                            apogee=None if profile.t_apogee is None else round(profile.t_apogee, 3),
                            landing=round(profile.t_landing, 3)),
        seed=seed, log_rate_hz=log_rate_hz, telemetry_rate_hz=telemetry_rate_hz,
        telemetry_link=dict(kind="SIMULATED TELEMETRY", loss_prob=loss_prob, bit_error_prob=bit_error_prob),
        notes=["All sensor values are synthetic (seeded noise on a truth profile). Noise, drift, battery discharge and "
               "parachute swing are illustrative assumptions, not properties of any component.",
               "The truth trajectory uses the PLACEHOLDER propulsion input: not representative of any real motor.",
               "GNSS positions are relative to a fictitious origin (0 deg, 0 deg) with a synthetic horizontal drift; "
               "the 1-DOF simulation has no horizontal motion."])
    paths = {}
    if sink is None:
        if out_dir is None:
            raise ValueError("give out_dir or sink")
        os.makedirs(out_dir, exist_ok=True)
        paths = dict(csv=os.path.join(out_dir, stem + ".csv"), meta=os.path.join(out_dir, stem + ".meta.json"),
                     capture=os.path.join(out_dir, stem + "_telemetry_capture.csv"))
        sink = CsvLogSink(paths["csv"])
    link = SimulatedTelemetryLink(loss_prob=loss_prob, bit_error_prob=bit_error_prob, seed=seed + 21)
    logger = DataLogger(sink, "SIMULATED", nominal_period_s=1.0 / log_rate_hz, meta_path=paths.get("meta"), metadata=meta)
    fc = FlightComputer(simulated_sensor_suite(profile, seed=seed, faults=faults), logger=logger, telemetry_link=link,
                        log_rate_hz=log_rate_hz, telemetry_rate_hz=telemetry_rate_hz)
    events = fc.run(duration)
    logger.metadata["detected_events_s"] = {e.name: round(e.time_s, 3) for e in events}
    apo = next((e for e in events if e.name == "APOGEE"), None)
    if apo:
        logger.metadata["detected_apogee"] = dict(time_s=round(apo.detail["apogee_time_s"], 3),
                                                  estimated_altitude_m=round(apo.detail["apogee_altitude_m"], 2))
    logger.metadata["telemetry_counts"] = dict(sent=link.sent, lost=link.lost, corrupted=link.corrupted)
    packets = link.receive()
    summary = logger.close()
    if "capture" in paths:
        with open(paths["capture"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write("rx_time_s,packet_hex\n")
            for t, p in packets:
                fh.write(f"{t:.3f},{p.hex().upper()}\n")
    return dict(events=events, summary=summary, packets=packets, link=link, paths=paths, flight_computer=fc)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=EXAMPLE_DIR)
    ap.add_argument("--stem", default=EXAMPLE_STEM)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--log-rate", type=float, default=50.0)
    ap.add_argument("--loss", type=float, default=0.02, help="simulated telemetry packet-loss probability")
    ap.add_argument("--bit-errors", type=float, default=0.01, help="simulated probability of a corrupted packet")
    a = ap.parse_args(argv)
    r = run_simulated_flight(out_dir=a.out_dir, stem=a.stem, seed=a.seed, log_rate_hz=a.log_rate, loss_prob=a.loss,
                             bit_error_prob=a.bit_errors)
    c = r["summary"]["counts"]
    print(f"SIMULATED flight: {c['written']} frames written, {c['rejected']} rejected; "
          f"events {r['summary'].get('detected_events_s')}")
    for k, p in r["paths"].items():
        print(f"  wrote {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
