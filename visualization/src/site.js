/**
 * Website sections (hero statistics, flight data, engineering system, validation, limitations).
 *
 * These are rendered from exactly the same exported JSON as the 3D simulator, so the page and
 * the simulation can never disagree and no engineering number is hard-coded in prose. A value
 * the repository does not contain renders as "N/A — NOT AVAILABLE IN CURRENT MODEL".
 */
import { tag } from './ui.js';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const NA_LONG = 'N/A — NOT AVAILABLE IN CURRENT MODEL';

function card(title, rows, note) {
  const facts = rows.map(([k, v, cls]) => (
    v === null || v === undefined
      ? `<div class="fact"><span class="k">${esc(k)}</span><span class="v na">${NA_LONG}</span></div>`
      : `<div class="fact"><span class="k">${esc(k)}</span><span class="v">${esc(v)}${cls ? tag(cls) : ''}</span></div>`
  )).join('');
  return `<div class="card"><h3>${esc(title)}</h3>${facts}${note ? `<p class="cnote">${esc(note)}</p>` : ''}</div>`;
}

function tableCard(title, rows) {
  const body = rows.map(([k, v, cls]) => (
    v === null || v === undefined
      ? `<tr><td class="k">${esc(k)}</td><td class="v na">${NA_LONG}</td></tr>`
      : `<tr><td class="k">${esc(k)}</td><td class="v">${esc(v)}${cls ? tag(cls) : ''}</td></tr>`
  )).join('');
  return `<div class="table-card"><h3>${esc(title)}</h3><table><tbody>${body}</tbody></table></div>`;
}

export function renderHeroStats(trajectory, project) {
  const r = trajectory.results;
  const v = project.software_validation;
  const cad = v.cad_checks;
  const stats = [
    [`${r.apogee_m.toFixed(1)} m`, 'SIMULATED APOGEE', 'placeholder propulsion data'],
    [`${r.v_max_mps.toFixed(1)} m/s`, 'MAXIMUM VELOCITY', `Mach ${r.mach_max.toFixed(3)}, simulated`],
    [v.total_tests ? `${v.total_tests}` : '—', 'AUTOMATED TESTS', v.failures === 0 ? '0 failures' : 'see validation'],
    [`${cad.PASS} / ${cad.FAIL}`, 'CAD CHECKS PASS / FAIL', `${cad.WARN} accepted warnings`],
  ];
  $('hero-stats').innerHTML = stats.map(([val, key, sub]) =>
    `<div class="stat"><span class="v">${esc(val)}</span><span class="k">${esc(key)}</span>` +
    `<span class="c">${esc(sub)}</span></div>`).join('');
}

export function renderFlightSection(trajectory, replay) {
  const r = trajectory.results;
  const m = trajectory.motor_input;
  const ev = trajectory.events.map((e) =>
    [e.name, `${e.t_s.toFixed(2)} s${e.detail ? ` — ${e.detail}` : ''}`, 'SIMULATED']);

  $('site-flight').innerHTML = `<div class="data-grid">
    ${tableCard('TRAJECTORY (1-DOF SIMULATION)', [
      ['Maximum altitude (apogee)', `${r.apogee_m.toFixed(1)} m`, 'SIMULATED'],
      ['Time to apogee', `${r.t_apogee_s.toFixed(2)} s`, 'SIMULATED'],
      ['Maximum velocity', `${r.v_max_mps.toFixed(2)} m/s`, 'SIMULATED'],
      ['Maximum Mach number', r.mach_max.toFixed(3), 'SIMULATED'],
      ['Maximum acceleration', `${r.a_max_g.toFixed(2)} g`, 'SIMULATED'],
      ['Maximum dynamic pressure', `${r.q_max_Pa.toFixed(0)} Pa`, 'SIMULATED'],
      ['Rail-exit velocity', `${r.rail_exit_v_mps.toFixed(2)} m/s`, 'SIMULATED'],
      ['Descent rate', `${r.descent_rate_mps.toFixed(2)} m/s`, 'SIMULATED'],
      ['Total modelled duration', `${r.t_landing_s.toFixed(1)} s`, 'SIMULATED'],
      ['Measured flight result', null],
    ])}
    ${tableCard('EVENT TIMELINE', ev)}
    ${tableCard('MODEL INPUTS', [
      ['Liftoff mass', `${(r.mass_liftoff_g / 1000).toFixed(4)} kg`, 'CALCULATED'],
      ['Static margin at liftoff', `${r.sm_liftoff.toFixed(3)} cal`, 'CALCULATED'],
      ['Static margin at burnout', `${r.sm_burnout.toFixed(3)} cal`, 'CALCULATED'],
      ['Motor', m.name, 'PLACEHOLDER'],
      ['Total impulse (placeholder)', `${m.total_impulse_Ns.toFixed(2)} N·s`, 'PLACEHOLDER'],
      ['Burn time (placeholder)', `${m.burn_time_s.toFixed(2)} s`, 'PLACEHOLDER'],
      ['Peak thrust (placeholder)', `${m.peak_thrust_N.toFixed(1)} N`, 'PLACEHOLDER'],
      ['Certified motor selected', null],
    ])}
    ${tableCard('SECOND DATA SET — AVIONICS SENSOR REPLAY', [
      ['Data class', replay.data_class, 'SYNTHETIC'],
      ['Source data set', 'simulation/data/sample_flight.csv', 'SYNTHETIC'],
      ['Rows processed', `${replay.summary.rows_used}`, 'SYNTHETIC'],
      ['Detected liftoff', `${replay.events.LIFTOFF.toFixed(2)} s (truth ${replay.truth_events_s.liftoff} s)`, 'SYNTHETIC'],
      ['Estimated apogee', `${replay.summary.max_estimated_altitude.altitude_m.toFixed(2)} m ` +
        `(truth ${replay.truth_apogee_m} m)`, 'SYNTHETIC'],
      ['Invalid samples rejected', Object.entries(replay.summary.invalid_samples)
        .map(([k, n]) => `${k} ${n}`).join(', ') || 'none', 'SYNTHETIC'],
      ['Telemetry packets decoded', `${replay.summary.telemetry.decoded} / ${replay.summary.telemetry.sent}`, 'SYNTHETIC'],
      ['Recorded from hardware', null],
    ])}
  </div>
  <div class="callout warn" style="margin-top:18px"><b>Model input vs simulated result vs measured result</b>
  Model inputs are the masses, the geometry and the placeholder motor data. Simulated results come from the
  project's own 1-DOF integration. <b>There are no measured results:</b> ASTRA-66 has never been built or flown.</div>`;
}

export function renderSystemSection(project) {
  const sys = project.system;
  if (!sys) { $('site-system').innerHTML = ''; return; }
  $('site-system').innerHTML = Object.values(sys).map((s) => card(s.title, s.facts, s.note)).join('');
}

export function renderValidationSection(project) {
  const v = project.software_validation;
  const steps = project.steps.map((s) => [s.step, s.ok ? 'PASS' : 'FAIL', s.ok ? 'CALCULATED' : null]);
  $('site-validation').innerHTML = `<div class="data-grid">
    ${tableCard('DIGITAL / SOFTWARE VALIDATION', [
      ['Flight-simulation checks', v.simulation_checks ? `${v.simulation_checks[0]}/${v.simulation_checks[1]} PASS` : null],
      ['Regression tests', v.regression_tests ? `${v.regression_tests} PASS` : null],
      ['Avionics software tests', v.avionics_tests ? `${v.avionics_tests} PASS` : null],
      ['Total automated tests', v.total_tests ? `${v.total_tests} PASS` : null],
      ['Failures', v.failures === null ? null : `${v.failures}`],
      ['CAD checks', `${v.cad_checks.PASS} PASS / ${v.cad_checks.WARN} WARN / ${v.cad_checks.FAIL} FAIL`],
      ['CAD / avionics fit checks', `${v.cad_avionics_checks.PASS} PASS / ${v.cad_avionics_checks.WARN} WARN / ` +
        `${v.cad_avionics_checks.UNVERIFIED} UNVERIFIED / ${v.cad_avionics_checks.FAIL} FAIL`],
      ['Physical bench testing', null],
      ['Flight testing', null],
    ])}
    ${tableCard('PIPELINE STEPS (python run_validation.py)', steps)}
  </div>
  <div class="badge-row">
    <span class="badge ${project.pipeline_overall === 'PASS' ? 'ok' : 'bad'}">PIPELINE ${esc(project.pipeline_overall)}</span>
    <span class="badge neutral">RUN ${esc(project.pipeline_date.slice(0, 10))}</span>
    <span class="badge neutral">PYTHON 3.12 &amp; 3.14 IN CI</span>
    <span class="badge bad">NOT FLIGHT CERTIFIED</span>
  </div>
  <div class="callout bad" style="margin-top:16px"><b>${esc(v.label)}</b>${esc(v.caveat)}</div>`;
}

export function renderLimitsSection(project) {
  const items = [...project.limitations];
  for (const nm of project.simulation_basis.not_modelled) {
    items.push(`Not modelled by the flight simulation: ${nm}`);
  }
  $('site-limits').innerHTML = `
    <p class="sec-lede">This is a digital engineering visualization, not a flight certification. The list below is
    copied from the project's own engineering status document — nothing is softened or removed.</p>
    <ul class="limit-list">${items.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
    <div class="callout bad" style="margin-top:18px"><b>Propulsion</b>${esc(project.motor.note)}</div>`;
}

export function renderFootNote(project) {
  $('foot-note').textContent =
    `Built with three.js and Vite. Every engineering value on this site is exported from ${project.sources.length} ` +
    `files in the ASTRA-66 repository by visualization/tools/export_flight_data.py (read-only). ` +
    `Pipeline run ${project.pipeline_date.slice(0, 10)}: ${project.pipeline_overall}. NOT FLIGHT CERTIFIED.`;
}

/** Highlight the section currently in view in the top navigation. */
export function wireScrollSpy() {
  const links = [...document.querySelectorAll('.nav-links a')];
  const targets = links
    .map((a) => ({ a, el: document.querySelector(a.getAttribute('href')) }))
    .filter((t) => t.el);
  if (!targets.length || !('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      const hit = targets.find((t) => t.el === e.target);
      if (hit) {
        for (const t of targets) t.a.classList.toggle('active', t === hit);
      }
    }
  }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });
  for (const t of targets) io.observe(t.el);
}
