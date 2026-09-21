# ASTRA-66 — 3D Digital Flight Visualization

A deployable website and browser-based 3D viewer for the **existing** ASTRA-66 engineering
model and its flight simulation. It animates data the project already produces; it does not
simulate anything and it does not change any engineering file.

> **NOT FLIGHT CERTIFIED.** Nothing in ASTRA-66 has been built, powered, bench tested or
> flown. Every number this viewer displays is a calculation, a simulation output or a
> synthetic sensor value. There are no measured flight results.

---

## 1. Purpose

| Goal | How it is met |
| --- | --- |
| See the ASTRA-66 airframe in 3D | Geometry generated from the project's own parameter file and station table; the exported CAD mesh can be overlaid |
| Watch the modelled flight | The 1-DOF trajectory the project already computes, played back on a timeline |
| Read engineering telemetry | Real columns of `simulation/results/trajectory_baseline.csv` |
| Understand what is proven | Simulation-basis, limitations and software-validation panels, taken from the repository |
| Prepare for real flight data later | One `FlightSource` interface that a recorded log can implement |

---

## 2. Architecture

```
  ASTRA-66 ENGINEERING PROJECT                (unchanged, read-only)
  ├── analysis/results/analysis.json          masses, CG, CP, static margin, stations
  ├── analysis/results/mass_budget.csv        41 components with provenance
  ├── cad/astra66_params.scad                 generated dimensions + provenance tags
  ├── cad/exports/validation_results.json     CAD check results
  ├── simulation/results/flight_summary.json  1-DOF results and disclaimers
  ├── simulation/results/trajectory_baseline.csv   the trajectory itself
  ├── simulation/results/avionics_replay/     synthetic sensor replay outputs
  └── simulation/results/pipeline_status.json validation counts
                       │
                       ▼
        visualization/tools/export_flight_data.py        ← DATA ADAPTER (Python, read-only)
                       │   copies values, never computes new ones
                       ▼
        visualization/public/data/*.json                 ← COMMON DATA FORMAT
                       │
                       ▼
        visualization/src/data.js   →  FlightSource objects
                       │
                       ▼
        scene + UI   (rocket.js, environment.js, trajectory.js, cameras.js, labels.js, ui.js)
                       │
                       ▼
                    three.js  →  browser
```

The engineering model stays the single source of truth. The visualiser is a consumer: if a
parameter changes, re-run the ASTRA-66 pipeline, then re-run the adapter.

### Files

| Path | Role |
| --- | --- |
| `visualization/tools/export_flight_data.py` | Data adapter. Reads the project, writes `visualization/public/data/`. Never writes into the project. |
| `visualization/src/data.js` | Loads the JSON and wraps it in `FlightSource` objects (the only interface the renderer knows) |
| `visualization/src/rocket.js` | Airframe geometry from the exported parameters; optional exported CAD mesh |
| `visualization/src/environment.js` | Sky, ground, grid, pad and rail, axes, altitude ruler, apogee marker |
| `visualization/src/trajectory.js` | Modelled path preview and the flown path |
| `visualization/src/cameras.js` | Free / chase / ground / side / top / inspect camera rig |
| `visualization/src/labels.js` | HTML label layer projected from world space |
| `visualization/src/ui.js` | HUD, engineering panels, component inspector, flight summary |
| `visualization/src/main.js` | Wiring and the animation loop |
| `visualization/tests/test_visualization_data.py` | Checks that no engineering value was invented or changed |
| `visualization/tests/test_browser_smoke.py` | Drives the built app in headless Chrome |

---

## 3. How to run

```bash
cd visualization
npm install
npm run data        # re-export the ASTRA-66 data (Python 3, standard library only)
npm run dev         # http://localhost:5173
```

The site is a single scrolling page: hero, the 3D simulator, flight data, the engineering
system, validation, limitations and an about section. Everything below the simulator is
rendered from the same exported JSON, so the page and the 3D view can never disagree.

Production build and preview:

```bash
npm run build       # -> visualization/dist
npm run preview
```

Optional: overlay the **exact** mesh exported from the OpenSCAD assembly
(`cad/exports/assembly/astra66_assembly_flight_parts.stl`, 5.9 MB, 120 164 triangles):

```bash
npm run data:cad    # copies the mesh into public/models and enables the CAD MESH button
```

`visualization/public/data/*.json` is committed, so `npm run dev` works without running the
adapter first. `node_modules/`, `dist/` and the copied `.stl` mesh are generated and
git-ignored; the mesh is copied in automatically by `npm run dev` and `npm run build`.

---

## 3a. Deployment (Vercel)

The production build is a plain static site — HTML, one JS bundle, one CSS file, four JSON
data files and an optional mesh. It needs no server, no API and no environment variables.

`vercel.json` at the repository root configures the whole thing, so importing the repository
into Vercel needs **no manual settings**:

```jsonc
{
  "installCommand": "npm --prefix visualization ci",
  "buildCommand":   "npm --prefix visualization run build",
  "outputDirectory": "visualization/dist"
}
```

Deploy steps:

1. Sign in at <https://vercel.com> with the GitHub account that owns the repository.
2. **Add New → Project → Import** the **Aarya801/ASTRA-66** repository.
3. Leave every setting at its default (the root `vercel.json` supplies them) and press
   **Deploy**.
4. Every later push to `main` redeploys automatically.

Any other static host works the same way: build with `npm --prefix visualization run build`
and serve `visualization/dist/`. The build uses `base: './'`, so it is also valid from a
sub-path such as GitHub Pages.

### Assets

| Asset | Where it comes from | Deployed as |
| --- | --- | --- |
| `data/*.json` | `visualization/public/data/` (committed) | `dist/data/*.json` |
| `public/models/assembly_meta.json` | committed | `dist/models/` |
| `models/*.stl` | copied at build time from `cad/exports/assembly/` by `scripts/copy-cad-mesh.mjs` | `dist/models/` (lazy-loaded on demand) |
| JS / CSS | bundled by Vite with hashed names | `dist/assets/` |

There are no `localhost`, `127.0.0.1`, `file://` or absolute filesystem references anywhere in
the app; a test enforces that.

## 4. Controls

| Control | Action |
| --- | --- |
| PLAY / PAUSE / RESET / RESTART | Transport. Space = play/pause, R = reset, I = inspect |
| Speed | 0.25× · 0.5× · 1× · 2× · 5× · 10× |
| Timeline | Drag to any point in the flight; event marks show liftoff, rail exit, burnout, apogee, landing |
| CAMERA | FREE (orbit/zoom/pan) · CHASE · GROUND · SIDE (profile) · TOP |
| INSPECT ROCKET | True size, dark backdrop, internals shown; click a part for its data |
| LABELS | Section labels on/off |
| CG / CP | Stability markers on/off (CG moves with the burn, from the trajectory's own `cg_mm` column) |
| INTERNALS | Fade the airframe to show coupler, sled, motor tube and motor envelope |
| TRAJECTORY / GRID | Path and ground reference on/off |
| CAD MESH | Swap the generated geometry for the exported OpenSCAD mesh (only if exported) |
| VISUAL SCALE | ×1 … ×50. **Display only** — it enlarges the 1.144 m vehicle so it stays visible against a 328 m trajectory and changes no data |
| DATA SOURCE | 1-DOF flight simulation, or the synthetic avionics sensor replay |

---

## 5. Data format

`public/data/trajectory.json` (the primary source):

```jsonc
{
  "model": "1-DOF vertical point mass, RK4",
  "data_class": "SIMULATED",
  "motor_data_status": "PLACEHOLDER",
  "columns": ["t_s","altitude_m","velocity_mps","accel_mps2","mass_kg","thrust_N",
              "drag_N","cd","mach","q_Pa","cg_mm","static_margin_cal"],
  "phases": ["pad","powered","coast","descent"],
  "samples": [[0.0, 0.0, 0.0, 0.0, 1.2107, 0.0, 0.0, 1.1758, 0.0, 0.0, 696.42, 2.6348], ...],
  "phase_index": [0, 0, 1, ...],
  "events":  [{"name": "APOGEE", "t_s": 8.51, "detail": "328.2 m"}, ...],
  "results": { ...the project's own flight_summary results block, unchanged... }
}
```

Every sample is a row that exists in `simulation/results/trajectory_baseline.csv`; the adapter
only selects rows (keeping all phase changes and all peak values), it never interpolates new
ones. `vehicle.json` carries `{v, unit, class, note}` records so the UI can show the
provenance of each value. `project.json` carries the validation counts, the limitations and a
SHA-256 of every source file that was read.

The renderer only understands a **FlightSource**:

```js
{ id, name, klass, model, phaseSource, duration, channels, events,
  sample(t) -> { t, altitude, velocity, acceleration, phase, values }, path, summary }
```

Two are implemented today (`simSource`, `replaySource`). A recorded flight log becomes a third.

---

## 6. Simulation basis

* **Flight model:** the project's own 1-DOF vertical point-mass integration (RK4) — *not* a
  6-DOF flight-dynamics simulation.
* **Trajectory:** SIMULATED, with **PLACEHOLDER** propulsion data. Apogee 328.2 m, maximum
  velocity 80.3 m/s, maximum acceleration 7.43 g are illustrative software results.
* **Flight phase:** read from the `phase` column the simulation writes (not derived by the
  visualiser). In the sensor-replay source the phase comes from the flight-computer
  classifier.
* **Attitude:** **not modelled.** The model produces no pitch, yaw or roll, so the vehicle is
  drawn nose-up along the modelled flight direction. The orientation is illustrative.
* **Sensor data:** SYNTHETIC. It was generated by the project and processed by the real
  flight-computer software; no sensor has ever been powered.
* **Stability:** CG, CP and static margin are the engineering model's values. The visualiser
  displays them and never recomputes them.

---

## 7. Limitations

Carried from the project's own status documents and shown in the app:

* Motor, thrust curve and motor mass are **placeholders**; every trajectory number depends on them.
* 1-DOF only: no wind, weathercocking, angle of attack, pitch/yaw/roll, dynamic stability, 3-D drift or deployment transient.
* The drag model is an uncalibrated component build-up.
* No hardware has been selected, measured, printed, assembled, bench tested or flown.
* Rail-exit velocity (11.74 m/s) is below the usual 15 m/s guideline — an open issue in the engineering model.
* The 3D geometry is a faithful but **simplified** representation: fillets, fasteners, slots and print detail are not drawn. Internal electronics are drawn only where the parameter file documents an envelope, and those envelopes are placeholders. Use the CAD MESH overlay for the exact solid.
* Test counts shown in the app are **digital/software validation** only; they are not physical certification.

---

## 8. Testing

```bash
python -m unittest discover -s visualization/tests -v
```

* `test_visualization_data.py` (32 tests) — the exported data matches `analysis.json`,
  `mass_budget.csv`, `astra66_params.scad`, `flight_summary.json`,
  `trajectory_baseline.csv`, `validation_results.json` and `pipeline_status.json` exactly;
  every value carries a provenance class; limitations and disclaimers survive the export;
  the adapter is idempotent; nothing outside `visualization/` is modified.
* `test_browser_smoke.py` (17 tests) — loads the production build in headless Chrome and
  checks data loading, HUD values, play/pause/reset/restart, playback speed, the timeline,
  all camera modes, inspect mode and component data, display toggles, trajectory growth, the
  data-source switch (including the `NOT AVAILABLE` path for the acceleration channel the
  replay data set does not contain) and the end-of-flight summary. Skips if Chrome or the
  build is missing.

The ASTRA-66 pipeline (`python run_validation.py`) is untouched and still passes.

---

## 9. Connecting a real flight log later

Nothing about this is validated yet — it is the intended path, not a claim.

1. Record a flight with the avionics software in `BENCH` or (once it exists and is enabled)
   `FLIGHT` mode; the log follows `avionics/data/schema/flight_data_schema.json`.
2. Extend `visualization/tools/export_flight_data.py` with a reader for that log which emits
   the same JSON shape, with `"data_class": "MEASURED"` and the real data-source mode.
3. Add a third source in `visualization/src/data.js` built with the same
   `sample(t) -> { t, altitude, velocity, acceleration, phase, values }` contract.
4. Nothing in the renderer changes. The HUD already shows `NOT AVAILABLE` for channels a data
   set does not carry, and the provenance tag will read `MEASURED` instead of `SIMULATED`.

Until a genuine, mentor-reviewed flight record exists, `FLIGHT` mode stays disabled in
`avionics/firmware/data_source.py` and this viewer has nothing measured to show.

---

## 10. Safety boundary

This is an educational engineering visualisation. It contains no propulsion design, no
propellant, no ignition, no pyrotechnics and no actuation of any kind. Propulsion appears
only as an external, commercially certified component envelope at a high level, exactly as in
the rest of ASTRA-66. Any physical activity requires a qualified mentor, a recognised
rocketry organisation and compliance with local law and range safety rules.
