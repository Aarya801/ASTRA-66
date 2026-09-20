"""Ground-station prototype server: feeds telemetry packets through the receiver and serves the browser dashboard.

    python avionics/ground_station/server.py                     # replay the committed SIMULATED capture
    python avionics/ground_station/server.py --simulate --speed 2
    python avionics/ground_station/server.py --capture FILE.csv --port 8766
    python avionics/ground_station/server.py --sensors simulation/data/sample_flight.csv   # sensor-level replay

Then open http://127.0.0.1:8766/ . The server binds to localhost only.

Sources: a telemetry capture file (rx_time_s,packet_hex), a fresh simulated flight (SimulatedTelemetryLink with
packet loss and bit errors), or a sensor-level dataset replayed through the flight-computer software
(simulation/avionics_replay.py). Packets are released at their recorded times (optionally faster) and decoded exactly
as a radio receiver would decode them. REAL HARDWARE TELEMETRY is not implemented: no radio has been selected.
This is a development prototype. It is NOT validated for real-time flight use.
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from avionics.firmware.telemetry.link import LINK_SIMULATED  # noqa: E402
from avionics.ground_station.receiver import GroundStationReceiver, read_capture  # noqa: E402

DASHBOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "index.html")
DEFAULT_CAPTURE = os.path.join(ROOT, "avionics", "data", "example", "example_flight_simulated_telemetry_capture.csv")
NOTICE = "Prototype ground station. Not validated for real-time flight use."


class TelemetryFeed:
    """Releases (t_s, packet) pairs into a receiver as (wall time since start) x speed passes their time stamps."""

    def __init__(self, packets, source_label, speed=1.0, loop=False, clock=time.monotonic):
        ok = [(t, p) for t, p in packets if t == t]            # drop capture lines with unreadable times
        self.packets = ok
        self.t0 = ok[0][0] if ok else 0.0
        self.duration = (ok[-1][0] - self.t0) if ok else 0.0
        self.source_label, self.speed, self.loop, self.clock = source_label, speed, loop, clock
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        self.rx = GroundStationReceiver()
        self.frames = []            # [(index, rx_time, frame)]
        self.next_i = 0
        self.start = self.clock()
        self.run_id = getattr(self, "run_id", 0) + 1

    def poll(self):
        with self._lock:
            elapsed = (self.clock() - self.start) * self.speed
            if self.loop and self.next_i >= len(self.packets) and elapsed > self.duration + 5.0:
                self._reset()
                elapsed = 0.0
            while self.next_i < len(self.packets) and self.packets[self.next_i][0] - self.t0 <= elapsed:
                t, p = self.packets[self.next_i]
                fr = self.rx.ingest(p, t)
                if fr is not None:
                    self.frames.append((len(self.frames), t, fr))
                self.next_i += 1
            return elapsed

    def snapshot(self, after=-1):
        elapsed = self.poll()
        with self._lock:
            sim = self.rx.simulated
            frames = [dict(index=i, rx_time_s=t, **f.as_dict()) for i, t, f in self.frames if i > after]
            return dict(link=LINK_SIMULATED if sim in (None, True) else "RECORDED TELEMETRY (hardware flag set)",
                        simulated=sim, source=self.source_label, notice=NOTICE, run_id=self.run_id,
                        elapsed_s=round(elapsed, 2), duration_s=round(self.duration, 2),
                        complete=self.next_i >= len(self.packets), stats=self.rx.stats(), frames=frames)


def make_handler(feed):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                with open(DASHBOARD, "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            if url.path == "/api/telemetry":
                try:
                    after = int(parse_qs(url.query).get("after", ["-1"])[0])
                except ValueError:
                    after = -1
                body = json.dumps(feed.snapshot(after), allow_nan=False).encode("utf-8")
                return self._send(200, body, "application/json")
            self._send(404, b"not found", "text/plain")

        def log_message(self, *args):       # keep the console quiet
            pass
    return Handler


def make_server(feed, host="127.0.0.1", port=8766):
    return ThreadingHTTPServer((host, port), make_handler(feed))


def _rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def _load_replay():
    import importlib.util
    spec = importlib.util.spec_from_file_location("astra66_avionics_replay",
                                                  os.path.join(ROOT, "simulation", "avionics_replay.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_feed(args):
    if args.sensors:
        r = _load_replay().replay(args.sensors, loss_prob=args.loss, bit_error_prob=args.bit_errors, seed=args.seed)
        return TelemetryFeed(r["packets"], f"sensor replay: {_rel(args.sensors)} "
                             "(dataset -> flight-computer software -> simulated link)", speed=args.speed, loop=args.loop)
    if args.simulate:
        from avionics.firmware.logging.logger import MemorySink
        from avionics.firmware.simulate_flight import run_simulated_flight
        r = run_simulated_flight(sink=MemorySink(), seed=args.seed, loss_prob=args.loss, bit_error_prob=args.bit_errors)
        return TelemetryFeed(r["packets"], "live simulation (simulated sensors -> flight computer -> simulated link)",
                             speed=args.speed, loop=args.loop)
    path = args.capture or DEFAULT_CAPTURE
    return TelemetryFeed(read_capture(path), f"capture replay: {_rel(path)}", speed=args.speed, loop=args.loop)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--capture", help="telemetry capture CSV to replay (default: the committed SIMULATED example)")
    src.add_argument("--simulate", action="store_true", help="run a fresh simulated flight")
    src.add_argument("--sensors", help="sensor-level CSV to replay through the flight-computer software")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed factor")
    ap.add_argument("--loop", action="store_true", help="restart the replay after the end")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--loss", type=float, default=0.02)
    ap.add_argument("--bit-errors", type=float, default=0.01)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args(argv)
    feed = build_feed(a)
    srv = make_server(feed, a.host, a.port)
    print(f"{LINK_SIMULATED}: {feed.source_label}\n{NOTICE}\nDashboard: http://{a.host}:{a.port}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
