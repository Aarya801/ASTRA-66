/**
 * ASTRA-66 visualisation - data layer.
 *
 *   ASTRA-66 engineering outputs
 *        -> visualization/tools/export_flight_data.py   (adapter, Python, read-only)
 *        -> public/data/*.json                          (common data format)
 *        -> this module                                 (FlightSource objects)
 *        -> scene + UI
 *
 * A FlightSource is the single interface the visualiser understands. Any future data set -
 * including a real recorded flight log - only has to produce one of these; nothing in the
 * rendering code knows where the numbers came from.
 *
 * No physics is computed here. Values absent from the repository stay null and are rendered
 * as "NOT AVAILABLE".
 */

const DATA = './data';

export async function loadAll() {
  const grab = async (name) => {
    const res = await fetch(`${DATA}/${name}`, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`cannot load ${name} (${res.status}) - run: python visualization/tools/export_flight_data.py`);
    try {
      return await res.json();
    } catch {
      throw new Error(`${name} is not valid JSON - run: python visualization/tools/export_flight_data.py`);
    }
  };
  const [vehicle, trajectory, replay, project] = await Promise.all(
    ['vehicle.json', 'trajectory.json', 'replay.json', 'project.json'].map(grab),
  );
  return validateDataBundle({ vehicle, trajectory, replay, project });
}

const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

function requireRecord(value, file, path) {
  if (!isRecord(value)) throw new Error(`${file} is missing or invalid: expected ${path} to be an object`);
  return value;
}

function requireFinite(value, file, path) {
  if (!finite(value)) throw new Error(`${file} is missing or invalid: expected ${path} to be a finite number`);
}

/** Fail early with a file-specific message before rendering code consumes exported data. */
export function validateDataBundle(bundle) {
  requireRecord(bundle, 'exported data', 'the data bundle');
  const vehicle = requireRecord(bundle.vehicle, 'vehicle.json', 'vehicle');
  const geometry = requireRecord(vehicle.geometry, 'vehicle.json', 'geometry');
  for (const key of ['length_mm', 'body_od_mm', 'body_id_mm', 'coupler_od_mm', 'nose_len_mm', 'nose_split_mm', 'mmt_od_mm', 'rail_length_m']) {
    requireFinite(geometry[key]?.v, 'vehicle.json', `geometry.${key}.v`);
  }
  const stations = requireRecord(geometry.stations_mm, 'vehicle.json', 'geometry.stations_mm');
  for (const key of ['nc_base', 'pl_end', 'band_end', 'cpl_fwd', 'cpl_aft', 'av_bh_fwd_outer', 'av_bh_aft_outer',
    'sled_fwd', 'sled_aft', 'mmt_fwd', 'mmt_aft', 'fin_le', 'core_fwd', 'core_aft', 'motor_fwd', 'motor_aft', 'cam', 'hatch']) {
    requireFinite(stations[key], 'vehicle.json', `geometry.stations_mm.${key}`);
  }
  const fin = requireRecord(geometry.fin, 'vehicle.json', 'geometry.fin');
  for (const key of ['count', 'root_chord_mm', 'tip_chord_mm', 'semi_span_mm', 'sweep_mm', 'thickness_mm', 'le_station_mm']) {
    requireFinite(fin[key]?.v, 'vehicle.json', `geometry.fin.${key}.v`);
  }
  const railButton = requireRecord(geometry.rail_button, 'vehicle.json', 'geometry.rail_button');
  for (const key of ['angle_deg', 'fwd_station_mm', 'aft_station_mm', 'diameter_mm', 'standoff_mm']) {
    requireFinite(railButton[key]?.v, 'vehicle.json', `geometry.rail_button.${key}.v`);
  }
  requireRecord(vehicle.modules, 'vehicle.json', 'modules');
  const stability = requireRecord(vehicle.stability, 'vehicle.json', 'stability');
  for (const key of ['cg_liftoff_mm', 'cp_mm']) requireFinite(stability[key]?.v, 'vehicle.json', `stability.${key}.v`);

  const trajectory = requireRecord(bundle.trajectory, 'trajectory.json', 'trajectory');
  const columns = trajectory.columns;
  if (!Array.isArray(columns) || new Set(columns).size !== columns.length) {
    throw new Error('trajectory.json is missing or invalid: columns must be a unique array');
  }
  const columnIndex = Object.fromEntries(columns.map((column, index) => [column, index]));
  const requiredColumns = ['t_s', 'altitude_m', 'velocity_mps', 'accel_mps2', 'mach', 'q_Pa', 'thrust_N',
    'drag_N', 'cd', 'mass_kg', 'cg_mm', 'static_margin_cal'];
  for (const key of requiredColumns) {
    if (!(key in columnIndex)) throw new Error(`trajectory.json is incompatible: missing ${key} column`);
  }
  if (!Array.isArray(trajectory.samples) || trajectory.samples.length < 2) {
    throw new Error('trajectory.json is missing or invalid: expected at least two samples');
  }
  const phases = trajectory.phases;
  if (!Array.isArray(phases) || !Array.isArray(trajectory.phase_index) || trajectory.phase_index.length !== trajectory.samples.length) {
    throw new Error('trajectory.json is missing or invalid: phases and phase_index must match the samples');
  }
  let previousTime = -Infinity;
  for (let rowIndex = 0; rowIndex < trajectory.samples.length; rowIndex++) {
    const row = trajectory.samples[rowIndex];
    if (!Array.isArray(row) || row.length !== columns.length || row.some((value) => value !== null && !finite(value))) {
      throw new Error(`trajectory.json is invalid: sample ${rowIndex} must match columns and contain finite values or null`);
    }
    const time = row[columnIndex.t_s];
    if (!finite(time) || time <= previousTime || !finite(row[columnIndex.altitude_m])) {
      throw new Error(`trajectory.json is invalid: sample ${rowIndex} has invalid or non-increasing time/altitude`);
    }
    previousTime = time;
    const phase = trajectory.phase_index[rowIndex];
    if (!Number.isInteger(phase) || phase < 0 || phase >= phases.length) {
      throw new Error(`trajectory.json is invalid: phase_index[${rowIndex}] is out of range`);
    }
  }
  const results = requireRecord(trajectory.results, 'trajectory.json', 'results');
  for (const key of ['apogee_m', 't_apogee_s', 'v_max_mps', 'mach_max', 'a_max_g', 'q_max_Pa', 'rail_exit_v_mps',
    't_burnout_s', 'h_burnout_m', 'descent_rate_mps', 't_landing_s', 'mass_liftoff_g', 'sm_liftoff']) {
    requireFinite(results[key], 'trajectory.json', `results.${key}`);
  }
  requireRecord(trajectory.motor_input, 'trajectory.json', 'motor_input');
  if (!Array.isArray(trajectory.events) || typeof trajectory.disclaimer !== 'string') {
    throw new Error('trajectory.json is missing or invalid: expected events and disclaimer');
  }

  const replay = requireRecord(bundle.replay, 'replay.json', 'replay');
  if (!Array.isArray(replay.samples) || replay.samples.length < 2 || !isRecord(replay.summary)) {
    throw new Error('replay.json is missing or invalid: expected samples and summary');
  }
  previousTime = -Infinity;
  for (let i = 0; i < replay.samples.length; i++) {
    const sample = replay.samples[i];
    if (!isRecord(sample) || !finite(sample.t) || sample.t <= previousTime ||
        !Array.isArray(sample.health) || sample.health.length === 0 ||
        !sample.health.every((value) => value === 0 || value === 1 || value === false || value === true)) {
      throw new Error(`replay.json is invalid: sample ${i} has invalid time or health data`);
    }
    previousTime = sample.t;
  }
  const replayAltitude = requireRecord(replay.summary.max_estimated_altitude, 'replay.json', 'summary.max_estimated_altitude');
  requireFinite(replayAltitude.altitude_m, 'replay.json', 'summary.max_estimated_altitude.altitude_m');
  requireFinite(replayAltitude.time_s, 'replay.json', 'summary.max_estimated_altitude.time_s');
  requireFinite(replay.summary.rows_used, 'replay.json', 'summary.rows_used');
  requireRecord(replay.summary.invalid_samples, 'replay.json', 'summary.invalid_samples');
  requireRecord(replay.summary.telemetry, 'replay.json', 'summary.telemetry');

  const project = requireRecord(bundle.project, 'project.json', 'project');
  for (const key of ['motor', 'simulation_basis', 'software_validation', 'system']) requireRecord(project[key], 'project.json', key);
  for (const key of ['limitations', 'sources', 'steps']) {
    if (!Array.isArray(project[key])) throw new Error(`project.json is missing or invalid: expected ${key} to be an array`);
  }
  if (typeof project.pipeline_date !== 'string' || typeof project.pipeline_overall !== 'string') {
    throw new Error('project.json is missing or invalid: pipeline status fields are absent');
  }
  return bundle;
}

/** Linear interpolation helper shared by the sources (visual interpolation only). */
function lerpAt(times, t) {
  const n = times.length;
  if (t <= times[0]) return { i: 0, j: 0, f: 0 };
  if (t >= times[n - 1]) return { i: n - 1, j: n - 1, f: 0 };
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= t) lo = mid; else hi = mid;
  }
  const span = times[hi] - times[lo];
  return { i: lo, j: hi, f: span > 0 ? (t - times[lo]) / span : 0 };
}

const mix = (a, b, f) => (a === null || b === null ? null : a + (b - a) * f);

/**
 * Source 1 - the project's own 1-DOF flight simulation (simulation/results/trajectory_baseline.csv).
 * Every channel below is a real column of that file.
 */
export function simSource(traj) {
  const col = Object.fromEntries(traj.columns.map((c, i) => [c, i]));
  const rows = traj.samples;
  const times = rows.map((r) => r[col.t_s]);
  const get = (row, key) => (row[col[key]] ?? null);

  const channels = [
    { key: 'altitude_m', label: 'ALTITUDE', unit: 'm', digits: 1, hud: true },
    { key: 'velocity_mps', label: 'VELOCITY', unit: 'm/s', digits: 1, hud: true },
    { key: 'accel_mps2', label: 'ACCEL', unit: 'm/s²', digits: 2, hud: true, extra: (v) => `${(v / 9.80665).toFixed(2)} g` },
    { key: 'mach', label: 'MACH', unit: '', digits: 3, hud: true },
    { key: 'q_Pa', label: 'DYN. PRESSURE', unit: 'Pa', digits: 0 },
    { key: 'thrust_N', label: 'THRUST', unit: 'N', digits: 1, note: 'PLACEHOLDER motor' },
    { key: 'drag_N', label: 'DRAG', unit: 'N', digits: 2 },
    { key: 'cd', label: 'Cd', unit: '', digits: 3 },
    { key: 'mass_kg', label: 'MASS', unit: 'kg', digits: 4 },
    { key: 'cg_mm', label: 'CG STATION', unit: 'mm', digits: 1 },
    { key: 'static_margin_cal', label: 'STATIC MARGIN', unit: 'cal', digits: 3 },
  ];

  const duration = times[times.length - 1];
  const res = traj.results;

  return {
    id: 'sim',
    name: '1-DOF FLIGHT SIMULATION',
    shortName: 'SIMULATION',
    klass: 'SIMULATED',
    model: traj.model,
    phaseSource: traj.phase_source,
    phaseDerived: false,
    duration,
    channels,
    events: traj.events,
    hasAttitude: false,
    note: `${traj.rows_in_source} integrator rows reduced to ${rows.length} visualisation samples (peaks and phase changes preserved).`,
    disclaimer: traj.disclaimer,
    sample(t) {
      const { i, j, f } = lerpAt(times, t);
      const a = rows[i], b = rows[j];
      const values = {};
      for (const c of channels) values[c.key] = mix(get(a, c.key), get(b, c.key), f);
      return {
        t,
        altitude: values.altitude_m,
        velocity: values.velocity_mps,
        acceleration: values.accel_mps2,
        phase: traj.phases[traj.phase_index[i]].toUpperCase(),
        values,
      };
    },
    /** Sampled [t, altitude] pairs for the trajectory ribbon. */
    path: rows.map((r) => [r[col.t_s], r[col.altitude_m]]),
    summary: [
      { k: 'Maximum altitude (apogee)', v: `${res.apogee_m.toFixed(1)} m`, c: 'SIMULATED' },
      { k: 'Time to apogee', v: `${res.t_apogee_s.toFixed(2)} s`, c: 'SIMULATED' },
      { k: 'Maximum velocity', v: `${res.v_max_mps.toFixed(2)} m/s (Mach ${res.mach_max.toFixed(3)})`, c: 'SIMULATED' },
      { k: 'Maximum acceleration', v: `${res.a_max_g.toFixed(2)} g`, c: 'SIMULATED' },
      { k: 'Maximum dynamic pressure', v: `${res.q_max_Pa.toFixed(0)} Pa`, c: 'SIMULATED' },
      { k: 'Rail-exit velocity', v: `${res.rail_exit_v_mps.toFixed(2)} m/s`, c: 'SIMULATED' },
      { k: 'Burnout', v: `${res.t_burnout_s.toFixed(2)} s at ${res.h_burnout_m.toFixed(1)} m`, c: 'SIMULATED' },
      { k: 'Descent rate', v: `${res.descent_rate_mps.toFixed(2)} m/s`, c: 'SIMULATED' },
      { k: 'Total modelled duration', v: `${res.t_landing_s.toFixed(1)} s`, c: 'SIMULATED' },
      { k: 'Liftoff mass (model input)', v: `${(res.mass_liftoff_g / 1000).toFixed(4)} kg`, c: 'CALCULATED' },
      { k: 'Static margin at liftoff (model input)', v: `${res.sm_liftoff.toFixed(3)} cal`, c: 'CALCULATED' },
      { k: 'Motor data', v: `${traj.motor_input.name} — PLACEHOLDER`, c: 'PLACEHOLDER' },
      { k: 'Physically measured result', v: 'NOT AVAILABLE — nothing has flown', c: 'NA' },
    ],
  };
}

/**
 * Source 2 - the project's synthetic sensor replay, processed by the real flight-computer
 * software (simulation/results/avionics_replay/). This is a different, synthetic data set:
 * it is NOT the 1-DOF trajectory, and it contains no thrust, drag or Mach channels.
 */
export function replaySource(rep) {
  const rows = rep.samples;
  const times = rows.map((r) => r.t);

  const channels = [
    { key: 'alt', label: 'EST. ALTITUDE', unit: 'm', digits: 2, hud: true },
    { key: 'v', label: 'EST. VELOCITY', unit: 'm/s', digits: 2, hud: true },
    { key: 'acceleration', label: 'ACCEL', unit: 'm/s²', digits: 2, hud: true, always_null: true,
      note: 'the estimator does not publish acceleration' },
    { key: 'baro_alt', label: 'BARO ALTITUDE', unit: 'm', digits: 2 },
    { key: 'pressure', label: 'PRESSURE', unit: 'Pa', digits: 1 },
    { key: 'temperature', label: 'TEMPERATURE', unit: '°C', digits: 2 },
    { key: 'battery', label: 'BATTERY', unit: 'V', digits: 3 },
    { key: 'lat', label: 'GNSS LAT', unit: '°', digits: 7 },
    { key: 'lon', label: 'GNSS LON', unit: '°', digits: 7 },
    { key: 'gps_fix', label: 'GNSS FIX', unit: '', digits: 0 },
    { key: 'gps_sats', label: 'GNSS SATS', unit: '', digits: 0 },
  ];

  const duration = times[times.length - 1];
  const ev = rep.events || {};
  const truth = rep.truth_events_s || {};

  return {
    id: 'replay',
    name: 'AVIONICS SENSOR REPLAY (SYNTHETIC)',
    shortName: 'SENSOR REPLAY',
    klass: 'SYNTHETIC',
    model: 'flight-computer software replaying a synthetic sensor data set',
    phaseSource: rep.phase_source,
    phaseDerived: false,
    duration,
    channels,
    hasAttitude: false,
    events: Object.entries(ev).map(([name, t]) => ({
      name,
      t_s: t,
      detail: truth[name.toLowerCase()] !== undefined ? `truth ${truth[name.toLowerCase()]} s` : '',
    })),
    note: `${rows.length} samples at 10 Hz from ${rep.summary.rows_used} sensor rows. Data-source mode ${rep.data_source_mode}.`,
    disclaimer: 'SYNTHETIC sensor data generated by the project. Not recorded from hardware; no sensor has been powered.',
    sample(t) {
      const { i, j, f } = lerpAt(times, t);
      const a = rows[i], b = rows[j];
      const values = {};
      for (const c of channels) {
        if (c.always_null) { values[c.key] = null; continue; }
        const va = a[c.key] ?? null, vb = b[c.key] ?? null;
        values[c.key] = (c.key === 'gps_fix' || c.key === 'gps_sats') ? va : mix(va, vb, f);
      }
      return {
        t,
        altitude: values.alt,
        velocity: values.v,
        acceleration: null,
        phase: a.state,
        health: a.health,
        values,
      };
    },
    path: rows.map((r) => [r.t, r.alt]),
    summary: [
      { k: 'Maximum estimated altitude', v: `${rep.summary.max_estimated_altitude.altitude_m.toFixed(2)} m at ${rep.summary.max_estimated_altitude.time_s.toFixed(2)} s`, c: 'SYNTHETIC' },
      { k: 'Known truth apogee of the data set', v: `${rep.truth_apogee_m} m at ${truth.apogee} s`, c: 'SYNTHETIC' },
      { k: 'Detected liftoff', v: `${(ev.LIFTOFF ?? 0).toFixed(2)} s (truth ${truth.liftoff} s)`, c: 'SYNTHETIC' },
      { k: 'Detected burnout', v: `${(ev.BURNOUT ?? 0).toFixed(2)} s (truth ${truth.burnout} s)`, c: 'SYNTHETIC' },
      { k: 'Detected landing', v: `${(ev.LANDING ?? 0).toFixed(2)} s (truth ${truth.landing} s)`, c: 'SYNTHETIC' },
      { k: 'Invalid samples rejected', v: Object.entries(rep.summary.invalid_samples).map(([k, n]) => `${k} ${n}`).join(', ') || 'none', c: 'SYNTHETIC' },
      { k: 'Telemetry packets decoded', v: `${rep.summary.telemetry.decoded} of ${rep.summary.telemetry.sent}`, c: 'SYNTHETIC' },
      { k: 'Acceleration channel', v: 'NOT AVAILABLE in this data set', c: 'NA' },
      { k: 'Physically measured result', v: 'NOT AVAILABLE — no sensor has been powered', c: 'NA' },
    ],
  };
}

/** Format a value/unit pair, or the honest "NOT AVAILABLE". */
export function fmt(value, unit, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const n = Math.abs(value) >= 1e5 ? value.toExponential(2) : value.toFixed(digits);
  return unit ? `${n} ${unit}` : `${n}`;
}
