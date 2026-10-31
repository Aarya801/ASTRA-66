"""Browser smoke test for the ASTRA-66 visualiser.

Loads the production build in headless Chrome and exercises the controls the user actually
uses: data loading, telemetry, play / pause / reset / restart, playback speed, the timeline
scrubber, camera modes, inspect mode, the trajectory, the data-source switch and the
"NOT AVAILABLE" path for channels the data does not contain.

It skips (rather than fails) when Chrome is not installed or the app has not been built, so
it can live next to the pure-data tests without making them fragile.

Prepare and run:
    cd visualization && npm install && npm run build
    python -m unittest discover -s visualization/tests -v
"""
from __future__ import annotations

import functools
import http.server
import json
import threading
import unittest
from pathlib import Path

from cdp import Browser, find_chrome, free_port

VIS = Path(__file__).resolve().parents[1]
DIST = VIS / "dist"
SHOTS = VIS / "tests" / "screenshots"


class Server:
    def __init__(self, root: Path):
        handler = functools.partial(QuietHandler, directory=str(root))
        self.port = free_port()
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/"

    def stop(self):
        self.httpd.shutdown()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(find_chrome(), "Chrome/Edge not found - set CHROME_PATH to run the browser test")
@unittest.skipUnless((DIST / "index.html").exists(), "run 'npm run build' in visualization/ first")
class BrowserSmoke(unittest.TestCase):
    server: Server
    browser: Browser

    @classmethod
    def setUpClass(cls):
        cls.server = Server(DIST)
        cls.browser = Browser(find_chrome())
        cls.browser.goto(cls.server.url, settle=1.0)
        # the simulator now lives below the hero: bring it into view so rendering is active
        cls.browser.ws.evaluate("document.getElementById('simulator').scrollIntoView(); true")
        # wait for the app to finish loading its data and render a first frame
        ready = cls.browser.ws.evaluate("""
          (async () => {
            for (let i = 0; i < 200; i++) {
              const a = window.ASTRA66;
              if (a && a.frame && a.renderer) return true;
              await new Promise(r => setTimeout(r, 100));
            }
            return false;
          })()
        """, timeout=90)
        if not ready:
            cls.browser.close()
            cls.server.stop()
            raise AssertionError("the visualiser did not finish loading")
        SHOTS.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.server.stop()

    def js(self, expr):
        return self.browser.ws.evaluate(expr)

    def rendered_colours(self, region=None):
        """Distinct colours in what the browser actually paints (blank frame -> 1)."""
        return self.browser.distinct_colours()

    def vehicle_on_screen(self):
        """True when the middle of the airframe projects inside the camera frustum."""
        return self.js("""(() => {
            const a = ASTRA66, R = a.rocket;
            const p = R.group.localToWorld(new R.group.position.constructor(0, R.L / 2000, 0));
            p.project(a.rig.camera);
            return Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && p.z > -1 && p.z < 1;
        })()""")

    # ---------------------------------------------------------------- loading

    def test_01_no_console_errors(self):
        errors = [e for e in self.browser.console_errors() if "favicon" not in e.lower()]
        self.assertEqual(errors, [], f"console errors: {errors}")

    def test_02_engineering_data_loaded(self):
        state = json.loads(self.js("""JSON.stringify({
            source: ASTRA66.source.id,
            duration: ASTRA66.source.duration,
            parts: ASTRA66.rocket.parts.length,
            samples: ASTRA66.source.path.length,
            apogee: ASTRA66.data.trajectory.results.apogee_m,
            loading: document.getElementById('loading').classList.contains('hidden'),
        })"""))
        self.assertEqual(state["source"], "sim")
        self.assertTrue(state["loading"], "loading overlay still visible")
        self.assertGreater(state["parts"], 10)
        self.assertGreater(state["samples"], 100)
        self.assertAlmostEqual(state["apogee"], 328.2358583723043, places=6)

    def test_02b_the_vehicle_is_actually_visible(self):
        self.js("""(() => {
            const tl = document.getElementById('timeline');
            tl.value = String(1000 * 2.2 / ASTRA66.source.duration);
            tl.dispatchEvent(new Event('input'));
            document.querySelector('[data-cam="chase"]').click();
        })()""")
        self.assertTrue(self.vehicle_on_screen(), "the vehicle is outside the chase camera frustum")
        self.assertGreater(self.rendered_colours(), 3, "the flight view rendered an empty frame")

    def test_03_panels_are_populated(self):
        text = self.js("document.getElementById('sidebar').innerText")
        for needle in ("SIMULATION BASIS", "1-DOF", "PLACEHOLDER", "NOT MODELLED",
                       "DIGITAL / SOFTWARE VALIDATION", "CURRENT MODEL LIMITATIONS"):
            self.assertIn(needle, text)

    def test_04_not_flight_certified_is_on_screen(self):
        self.assertIn("NOT FLIGHT CERTIFIED", self.js("document.body.innerText"))

    # ---------------------------------------------------------------- telemetry

    def test_05_telemetry_matches_the_simulation(self):
        frame = json.loads(self.js("""(() => {
            const a = ASTRA66, f = a.source.sample(a.data.trajectory.results.t_apogee_s);
            return JSON.stringify({ alt: f.altitude, v: f.velocity, phase: f.phase });
        })()"""))
        self.assertAlmostEqual(frame["alt"], 328.2358583723043, delta=0.05)
        self.assertAlmostEqual(frame["v"], 0.0, delta=0.5)
        self.assertIn(frame["phase"], ("COAST", "DESCENT"))

    def test_06_hud_updates_with_the_timeline(self):
        hud = self.js("""(() => {
            const a = ASTRA66, tl = document.getElementById('timeline');
            tl.value = String(1000 * 1.45 / a.source.duration);
            tl.dispatchEvent(new Event('input'));
            return new Promise(res => requestAnimationFrame(() => requestAnimationFrame(
                () => res(document.getElementById('hud-rows').innerText))));
        })()""")
        self.assertIn("80.3", hud.replace("\n", " "), f"expected v_max in the HUD, got: {hud!r}")

    # ---------------------------------------------------------------- transport

    def test_07_play_pause_reset_restart(self):
        result = json.loads(self.js("""(async () => {
            const a = ASTRA66, nextFrame = () => new Promise(requestAnimationFrame);
            const frameMatchesSource = () => {
                const expected = a.source.sample(a.t);
                const hud = document.getElementById('hud-rows').innerText;
                const hudMatches = a.source.channels.filter(channel => channel.hud).every(channel => {
                    const value = expected.values[channel.key];
                    const shown = value === null || value === undefined ? 'NOT AVAILABLE' :
                        `${value.toFixed(channel.digits)}${channel.unit ? ` ${channel.unit}` : ''}`;
                    return hud.includes(channel.label) && hud.includes(shown) &&
                        (!channel.extra || value === null || value === undefined || hud.includes(channel.extra(value)));
                });
                return a.frame.t === a.t && a.frame.phase === expected.phase &&
                    JSON.stringify(a.frame.values) === JSON.stringify(expected.values) &&
                    hud.includes(`TIME\n${expected.t.toFixed(3)} s`) && hudMatches;
            };
            const sourceTimes = a.source.path.map(row => row[0]);
            const lowerSampleIndex = (t) => {
                let lo = 0, hi = sourceTimes.length - 1;
                while (hi - lo > 1) {
                    const mid = (lo + hi) >> 1;
                    if (sourceTimes[mid] <= t) lo = mid; else hi = mid;
                }
                return t >= sourceTimes.at(-1) ? sourceTimes.length - 1 : lo;
            };
            document.getElementById('btn-reset').click();
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
            const t0 = a.t;
            document.getElementById('btn-play').click();
            const observed = [];
            for (let i = 0; i < 8; i++) {
                await nextFrame();
                observed.push({ t: a.t, matches: frameMatchesSource(), lowerIndex: lowerSampleIndex(a.t) });
            }
            const playing = a.playing, t1 = a.t;
            const cycles = [];
            for (let i = 0; i < 3; i++) {
                document.getElementById('btn-pause').click();
                const frozenAt = a.t;
                for (let frame = 0; frame < 5; frame++) await nextFrame();
                const frozen = !a.playing && a.t === frozenAt && frameMatchesSource();
                document.getElementById('btn-play').click();
                for (let frame = 0; frame < 90 && a.t <= frozenAt; frame++) await nextFrame();
                cycles.push({ frozenAt, frozen, resumed: a.playing && a.t > frozenAt && frameMatchesSource(), t: a.t });
            }
            document.getElementById('btn-pause').click();
            document.getElementById('btn-reset').click();
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
            const reset = { t: a.t, playing: a.playing, matches: frameMatchesSource(),
                sourceTime: a.source.sample(0).t, hud: document.getElementById('hud-rows').innerText };
            const timeline = document.getElementById('timeline');
            const replayCheckpoints = async () => {
                const frames = [];
                for (const value of ['0', '123', '500', '1000']) {
                    timeline.value = value;
                    timeline.dispatchEvent(new Event('input'));
                    await new Promise(requestAnimationFrame);
                    await new Promise(requestAnimationFrame);
                    frames.push({ t: a.t, values: a.frame.values, phase: a.frame.phase,
                        hud: document.getElementById('hud-rows').innerText,
                        matches: frameMatchesSource() });
                }
                return frames;
            };
            const firstReplay = await replayCheckpoints();
            document.getElementById('btn-reset').click();
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
            const secondReplay = await replayCheckpoints();
            const sameReplay = JSON.stringify(firstReplay) === JSON.stringify(secondReplay);
            document.getElementById('btn-reset').click();
            await new Promise(requestAnimationFrame);
            await new Promise(requestAnimationFrame);
            document.getElementById('btn-play').click();
            for (let frame = 0; frame < 90 && a.t === 0; frame++) await nextFrame();
            const replayed = frameMatchesSource() && a.t > 0;
            document.getElementById('btn-pause').click();
            return JSON.stringify({ t0, t1, playing, cycles, observed, reset, firstReplay, secondReplay,
                sameReplay, replayed });
        })()"""))
        self.assertEqual(result["t0"], 0)
        self.assertTrue(result["playing"])
        self.assertGreater(result["t1"], 0, "time did not advance while playing")
        self.assertEqual(len(result["cycles"]), 3)
        self.assertTrue(all(cycle["frozen"] for cycle in result["cycles"]),
                        f"playback or telemetry changed while paused: {result['cycles']}")
        self.assertTrue(all(cycle["resumed"] for cycle in result["cycles"]),
                        f"resume did not continue source-consistent playback: {result['cycles']}")
        self.assertEqual([cycle["t"] for cycle in result["cycles"]],
                         sorted(cycle["t"] for cycle in result["cycles"]),
                         "repeated resumes must preserve forward playback order")
        self.assertTrue(all(item["matches"] for item in result["observed"]),
                        f"playback telemetry diverged from its active source: {result['observed']}")
        indices = [item["lowerIndex"] for item in result["observed"]]
        self.assertEqual(indices, sorted(indices), "playback moved backward through source records")
        self.assertTrue(any(b > a for a, b in zip(indices, indices[1:])),
                        "playback did not advance to later source records")
        self.assertEqual(result["reset"]["t"], 0, "reset did not return to T+0")
        self.assertFalse(result["reset"]["playing"], "reset must leave playback paused")
        self.assertTrue(result["reset"]["matches"], "reset frame/HUD does not match the initial source record")
        self.assertEqual(result["reset"]["sourceTime"], 0)
        self.assertTrue(all(frame["matches"] for frame in result["firstReplay"] + result["secondReplay"]),
                        "deterministic checkpoints did not match their source telemetry")
        self.assertTrue(result["sameReplay"], "same timeline checkpoints after reset differed from the fresh run")
        self.assertTrue(result["replayed"], "playback after reset did not produce source-consistent telemetry")

    def test_08_playback_speed(self):
        speeds = json.loads(self.js("""(() => {
            const out = [];
            for (const s of ['0.25', '2', '10', '1']) {
                document.querySelector(`[data-speed="${s}"]`).click();
                out.push(ASTRA66.speed);
            }
            return JSON.stringify(out);
        })()"""))
        self.assertEqual(speeds, [0.25, 2, 10, 1])

    def test_09_timeline_scrub(self):
        t = self.js("""(() => {
            const a = ASTRA66, tl = document.getElementById('timeline');
            tl.value = '500'; tl.dispatchEvent(new Event('input'));
            return a.t;
        })()""")
        self.assertGreater(t, 1)

    # ---------------------------------------------------------------- views

    def test_10_camera_modes(self):
        modes = json.loads(self.js("""(() => {
            const out = {};
            for (const m of ['chase', 'ground', 'side', 'top', 'free']) {
                document.querySelector(`[data-cam="${m}"]`).click();
                out[m] = [ASTRA66.rig.mode, ASTRA66.rig.camera.position.toArray().map(x => +x.toFixed(2))];
            }
            return JSON.stringify(out);
        })()"""))
        for m in ("chase", "ground", "side", "top", "free"):
            self.assertEqual(modes[m][0], m)
        self.assertNotEqual(modes["side"][1], modes["top"][1], "camera did not move between modes")

    def test_11_inspect_mode_and_component_data(self):
        # enter inspect part-way through the flight: the camera must follow the vehicle
        self.js("""(() => {
            const tl = document.getElementById('timeline');
            tl.value = String(1000 * 2.2 / ASTRA66.source.duration);
            tl.dispatchEvent(new Event('input'));
        })()""")
        info = json.loads(self.js("""(() => {
            document.querySelector('[data-toggle="inspect"]').click();
            const a = ASTRA66;
            const state = { inspect: a.inspect, scale: a.rocket.group.scale.x, mode: a.rig.mode,
                            trajVisible: a.traj.group.visible };
            document.querySelector('[data-part="AV-306"]').click();
            state.inspectorText = document.getElementById('ins-body').innerText;
            state.inspectorOpen = !document.getElementById('inspector').hidden;
            return JSON.stringify(state);
        })()"""))
        self.assertTrue(info["inspect"])
        self.assertEqual(info["scale"], 1, "inspect mode should show the vehicle at true size")
        self.assertEqual(info["mode"], "inspect")
        self.assertFalse(info["trajVisible"], "the trajectory should not obscure the vehicle in inspect mode")
        self.assertTrue(info["inspectorOpen"])
        self.assertIn("AV-306", info["inspectorText"])
        self.assertIn("32.1 g", info["inspectorText"])
        self.assertTrue(self.vehicle_on_screen(), "the vehicle is not in view in inspect mode")
        self.assertGreater(self.rendered_colours(), 3, "inspect view rendered an empty frame")
        self.js("""document.querySelector('[data-toggle=\"inspect\"]').click()""")

    def test_12_display_toggles(self):
        state = json.loads(self.js("""(() => {
            const a = ASTRA66, out = {};
            for (const k of ['labels', 'cgcp', 'internals', 'trajectory', 'grid']) {
                const before = a.toggles[k];
                document.querySelector(`[data-toggle="${k}"]`).click();
                out[k] = [before, a.toggles[k]];
            }
            out.markersVisible = a.rocket.markers.visible;
            out.trajVisible = a.traj.group.visible;
            for (const k of ['labels', 'cgcp', 'internals', 'trajectory', 'grid']) {
                document.querySelector(`[data-toggle="${k}"]`).click();
            }
            return JSON.stringify(out);
        })()"""))
        for k in ('labels', 'cgcp', 'internals', 'trajectory', 'grid'):
            before, after = state[k]
            with self.subTest(toggle=k):
                self.assertNotEqual(before, after, f"toggle {k} did not change")
        self.assertFalse(state["markersVisible"], "CG/CP markers should hide when the toggle is off")
        self.assertFalse(state["trajVisible"], "the trajectory should hide when the toggle is off")

    def test_13_trajectory_grows_with_time(self):
        counts = json.loads(self.js("""(async () => {
            const a = ASTRA66, tl = document.getElementById('timeline');
            const at = async (s) => {
                tl.value = String(1000 * s / a.source.duration);
                tl.dispatchEvent(new Event('input'));
                await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
                return a.traj.flownGeo.drawRange.count;
            };
            return JSON.stringify([await at(0.5), await at(8.5), await at(60)]);
        })()"""))
        self.assertLess(counts[0], counts[1])
        self.assertLess(counts[1], counts[2])

    # ---------------------------------------------------------------- data sources

    def test_14_switch_to_sensor_replay(self):
        state = json.loads(self.js("""(async () => {
            const sel = document.getElementById('sel-source');
            sel.value = 'replay';
            sel.dispatchEvent(new Event('change'));
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            const a = ASTRA66, f = a.source.sample(10.1);
            return JSON.stringify({
                id: a.source.id, klass: a.source.klass, duration: a.source.duration,
                alt: f.altitude, accel: f.acceleration, phase: f.phase,
                hud: document.getElementById('hud-rows').innerText,
                chip: document.getElementById('chip-source').innerText,
            });
        })()"""))
        self.assertEqual(state["id"], "replay")
        self.assertEqual(state["klass"], "SYNTHETIC")
        self.assertIsNone(state["accel"], "the replay data set has no acceleration channel")
        self.assertIn("NOT AVAILABLE", state["hud"], "missing channels must be shown as NOT AVAILABLE")
        self.assertGreater(state["alt"], 100)
        self.assertIn("SYNTHETIC", state["chip"])

    def test_15_summary_on_completion(self):
        result = json.loads(self.js("""(async () => {
            const a = ASTRA66, nextFrame = () => new Promise(requestAnimationFrame);
            const sel = document.getElementById('sel-source');
            sel.value = 'sim'; sel.dispatchEvent(new Event('change'));
            const tl = document.getElementById('timeline');
            tl.value = '999'; tl.dispatchEvent(new Event('input'));
            document.getElementById('btn-play').click();
            for (let i = 0; i < 600 && a.playing; i++) await nextFrame();
            const last = a.source.sample(a.source.duration);
            return JSON.stringify({ summary: document.getElementById('sum-body').innerText,
                t: a.t, duration: a.source.duration, playing: a.playing,
                frameMatchesEnd: a.frame.t === a.source.duration && a.frame.phase === last.phase &&
                    JSON.stringify(a.frame.values) === JSON.stringify(last.values),
                timeline: document.getElementById('timeline').value });
        })()"""))
        self.assertIn("328.2 m", result["summary"])
        self.assertIn("PLACEHOLDER", result["summary"])
        self.assertIn("NOT AVAILABLE", result["summary"])
        self.assertEqual(result["t"], result["duration"], "playback must clamp to the final data timestamp")
        self.assertFalse(result["playing"], "playback must stop at end of data")
        self.assertTrue(result["frameMatchesEnd"], "final displayed telemetry must match the final source record")
        self.assertEqual(float(result["timeline"]), 1000)

    def test_16_final_screenshot(self):
        """Leave the app in a representative state and capture it as visible evidence."""
        self.js("""(async () => {
            document.getElementById('sum-close').click();
            document.getElementById('btn-reset').click();
            const sel = document.getElementById('sel-scale');
            sel.value = '25'; sel.dispatchEvent(new Event('change'));
            const tl = document.getElementById('timeline');
            tl.value = String(1000 * 2.2 / ASTRA66.source.duration);
            tl.dispatchEvent(new Event('input'));
            document.querySelector('[data-cam="chase"]').click();
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        })()""")
        self.browser.screenshot(SHOTS / "smoke_flight.png")
        self.assertTrue((SHOTS / "smoke_flight.png").stat().st_size > 10_000)

    def test_16b_cad_mesh_overlay(self):
        """The exact exported OpenSCAD mesh can replace the generated geometry."""
        available = self.js("!!(ASTRA66.data.project.cad_mesh)")
        if not available:
            self.skipTest("CAD mesh not exported - run: npm run data:cad")
        state = json.loads(self.js("""(async () => {
            const a = ASTRA66;
            for (let i = 0; i < 100 && !a.rocket.cadMesh; i++) await new Promise(r => setTimeout(r, 100));
            document.querySelector('[data-toggle="cad"]').click();
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            return JSON.stringify({
                loaded: !!a.rocket.cadMesh,
                meshVisible: a.rocket.cadMesh ? a.rocket.cadMesh.visible : false,
                proceduralHidden: a.rocket.parts.every((m) => !m.visible),
                triangles: a.data.project.cad_mesh.triangles,
            });
        })()"""))
        self.assertTrue(state["loaded"], "the CAD mesh did not load")
        self.assertTrue(state["meshVisible"])
        self.assertTrue(state["proceduralHidden"], "generated geometry should hide behind the CAD mesh")
        self.assertGreater(state["triangles"], 10000)
        self.assertGreater(self.rendered_colours(), 3, "CAD mesh view rendered an empty frame")
        self.browser.screenshot(SHOTS / "smoke_cad_mesh.png")
        self.js("""document.querySelector('[data-toggle=\"cad\"]').click()""")

    def test_17_inspect_screenshot(self):
        self.js("""(async () => {
            document.querySelector('[data-toggle="inspect"]').click();
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        })()""")
        self.browser.screenshot(SHOTS / "smoke_inspect.png")
        self.assertTrue((SHOTS / "smoke_inspect.png").stat().st_size > 10_000)


    # ---------------------------------------------------------------- website

    def test_20_website_sections_render(self):
        state = json.loads(self.js("""JSON.stringify({
            stats: document.querySelectorAll('#hero-stats .stat').length,
            heroText: document.getElementById('hero-stats').innerText,
            flight: document.getElementById('site-flight').innerText,
            cards: document.querySelectorAll('#site-system .card').length,
            validation: document.getElementById('site-validation').innerText,
            limits: document.querySelectorAll('#site-limits .limit-list li').length,
            foot: document.getElementById('foot-note').innerText,
        })"""))
        self.assertEqual(state["stats"], 4)
        self.assertIn("328.2 m", state["heroText"])
        self.assertIn("328.2 m", state["flight"])
        self.assertIn("PLACEHOLDER", state["flight"])
        self.assertEqual(state["cards"], 6, "expected the six engineering subsystem cards")
        self.assertIn("155 PASS", state["validation"])
        self.assertIn("NOT FLIGHT CERTIFIED", state["validation"])
        self.assertGreaterEqual(state["limits"], 8)
        self.assertIn("NOT FLIGHT CERTIFIED", state["foot"])

    def test_21_missing_values_are_marked_not_available(self):
        text = self.js("document.getElementById('site-flight').innerText")
        self.assertIn("NOT AVAILABLE IN CURRENT MODEL", text)
        val = self.js("document.getElementById('site-validation').innerText")
        self.assertIn("NOT AVAILABLE IN CURRENT MODEL", val)

    def test_22_github_links_open_safely(self):
        links = json.loads(self.js("""JSON.stringify(
            [...document.querySelectorAll('a[href^="https://github.com/"]')].map(
                (a) => [a.getAttribute('href'), a.target, a.rel]))"""))
        self.assertGreaterEqual(len(links), 3, "expected a GitHub link in the nav, hero and footer")
        self.assertTrue(any(h == "https://github.com/Aarya801/ASTRA-66" for h, _, _ in links))
        for href, target, rel in links:
            with self.subTest(href=href):
                self.assertEqual(target, "_blank")
                self.assertIn("noopener", rel)

    def test_23_no_horizontal_overflow(self):
        for w, h, mobile in ((1600, 950, False), (1024, 800, False), (768, 1024, True), (390, 844, True)):
            self.browser.set_viewport(w, h, mobile)
            self.js("window.scrollTo(0, 0); true")
            over = json.loads(self.js("""JSON.stringify({
                scrollW: document.documentElement.scrollWidth,
                inner: window.innerWidth,
                canvasW: document.getElementById('scene').clientWidth,
                canvasH: document.getElementById('scene').clientHeight,
            })"""))
            with self.subTest(width=w):
                self.assertLessEqual(over["scrollW"], over["inner"] + 1,
                                     f"horizontal overflow at {w}px: {over}")
                self.assertGreater(over["canvasW"], 0)
                self.assertGreater(over["canvasH"], 200, "the 3D stage collapsed at this width")
        self.browser.set_viewport(1600, 950, False)
        self.js("document.getElementById('simulator').scrollIntoView(); true")

    def test_24_mobile_layout_still_renders_the_simulation(self):
        self.browser.set_viewport(390, 844, True)
        drawer = json.loads(self.js("""JSON.stringify({
            display: getComputedStyle(document.getElementById('sidebar')).display,
            controls: document.getElementById('btn-sidebar').getAttribute('aria-controls'),
            expanded: document.getElementById('btn-sidebar').getAttribute('aria-expanded'),
            opens: (() => {
                document.getElementById('btn-sidebar').click();
                const d = getComputedStyle(document.getElementById('sidebar')).display;
                const expanded = document.getElementById('btn-sidebar').getAttribute('aria-expanded');
                document.getElementById('btn-sidebar').click();
                return { display: d, expanded };
            })(),
        })"""))
        self.assertEqual(drawer["display"], "none",
                         "the panels must not cover the 3D view on a phone")
        self.assertEqual(drawer["controls"], "sidebar")
        self.assertEqual(drawer["expanded"], "false")
        self.assertNotEqual(drawer["opens"]["display"], "none", "the PANELS button must open the drawer")
        self.assertEqual(drawer["opens"]["expanded"], "true")
        self.js("""(async () => {
            document.getElementById('simulator').scrollIntoView();
            await new Promise(r => setTimeout(r, 400));
            const tl = document.getElementById('timeline');
            tl.value = String(1000 * 2.2 / ASTRA66.source.duration);
            tl.dispatchEvent(new Event('input'));
            document.querySelector('[data-cam="chase"]').click();
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        })()""")
        self.assertTrue(self.vehicle_on_screen(), "the vehicle is not framed on a phone viewport")
        self.assertGreater(self.rendered_colours(), 3, "the mobile stage rendered an empty frame")
        self.browser.screenshot(SHOTS / "smoke_mobile.png")
        self.browser.set_viewport(1600, 950, False)
        self.js("document.getElementById('simulator').scrollIntoView(); true")

    def test_25_rendering_pauses_when_the_stage_is_off_screen(self):
        state = json.loads(self.js("""(async () => {
            const a = ASTRA66;
            // scroll right down to the footer, well past the stage
            document.documentElement.style.scrollBehavior = 'auto';
            window.scrollTo(0, document.documentElement.scrollHeight);
            for (let i = 0; i < 40 && !a.offscreen; i++) await new Promise(r => setTimeout(r, 50));
            const away = a.offscreen;
            document.getElementById('simulator').scrollIntoView();
            for (let i = 0; i < 40 && a.offscreen; i++) await new Promise(r => setTimeout(r, 50));
            return JSON.stringify({ away, back: a.offscreen });
        })()"""))
        self.assertTrue(state["away"], "rendering should pause when the stage is scrolled away")
        self.assertFalse(state["back"], "rendering should resume when the stage returns")

    def test_26_full_page_screenshot(self):
        self.js("""(async () => {
            document.documentElement.style.scrollBehavior = 'auto';
            window.scrollTo(0, 0);
            await new Promise(r => setTimeout(r, 300));
        })()""")
        self.browser.screenshot(SHOTS / "site_hero.png")
        self.assertTrue((SHOTS / "site_hero.png").stat().st_size > 10_000)

    def test_27_keyboard_shortcuts_preserve_native_control_activation(self):
        state = json.loads(self.js("""(() => {
            ASTRA66.hover = true;
            ASTRA66.playing = false;
            const toggle = document.querySelector('[data-toggle="labels"]');
            toggle.focus();
            return JSON.stringify({ focused: document.activeElement === toggle, before: ASTRA66.toggles.labels });
        })()"""))
        self.assertTrue(state["focused"])
        self.browser.press_key(" ", "Space", 32)
        self.assertNotEqual(self.js("ASTRA66.toggles.labels"), state["before"],
                            "Space should activate the focused display button")
        self.assertFalse(self.js("ASTRA66.playing"), "Space on a control should not also toggle playback")

    def test_28_engineering_panels_are_keyboard_operable(self):
        self.js("""(() => document.querySelector('[aria-controls="panel-engineering"]').focus())()""")
        self.assertEqual(self.js("document.activeElement.getAttribute('aria-expanded')"), "false")
        self.browser.press_key(" ", "Space", 32)
        state = json.loads(self.js("""JSON.stringify({
            expanded: document.activeElement.getAttribute('aria-expanded'),
            open: document.querySelector('[aria-controls="panel-engineering"]').closest('.panel').dataset.open,
        })"""))
        self.assertEqual(state["expanded"], "true")
        self.assertEqual(state["open"], "true")

    def test_29_invalid_export_shows_safe_retry_state(self):
        vehicle_file = DIST / "data" / "vehicle.json"
        original = vehicle_file.read_bytes()
        vehicle_file.write_text('{"<img src=x onerror=alert(1)>": true}', encoding="utf-8")
        try:
            self.browser.goto(self.server.url, settle=0.5)
            state = json.loads(self.js("""JSON.stringify({
                alert: document.querySelector('#loading [role="alert"]')?.innerText || '',
                retry: document.querySelector('#loading .load-retry')?.textContent || '',
                injected: !!document.querySelector('#loading img'),
            })"""))
            self.assertIn("vehicle.json is missing or invalid", state["alert"])
            self.assertEqual(state["retry"], "TRY AGAIN")
            self.assertFalse(state["injected"], "invalid data must be rendered as text, never HTML")
        finally:
            vehicle_file.write_bytes(original)

    def test_30_repeated_shortcut_keydown_is_ignored(self):
        self.js("ASTRA66.hover = true; ASTRA66.playing = false; true")
        self.browser.press_key(" ", "Space", 32, repeat=True)
        self.assertFalse(self.js("ASTRA66.playing"), "a repeated Space keydown must not toggle playback")

if __name__ == "__main__":
    unittest.main(verbosity=2)
