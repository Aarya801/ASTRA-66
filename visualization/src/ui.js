/**
 * Engineering user interface: side panels, HUD, component inspector and end-of-flight summary.
 *
 * Display rule used everywhere in this file: a value the repository does not contain is shown
 * as "NOT AVAILABLE". A value the repository contains is shown with the provenance class the
 * repository gave it (CALCULATED / ASSUMPTION / USER-SUPPLIED / COMMERCIAL SPEC / PLACEHOLDER /
 * SIMULATED / SYNTHETIC). Nothing is rounded up into a claim.
 */
const $ = (id) => document.getElementById(id);
const NA = '<span class="v na">NOT AVAILABLE</span>';

const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function tagClass(c) {
  if (!c) return 'NA';
  const t = String(c).toUpperCase();
  if (t.startsWith('COMMERCIAL')) return 'COMMERCIAL';
  if (t.startsWith('USER')) return 'USER-SUPPLIED';
  return ['CALCULATED', 'SIMULATED', 'ASSUMPTION', 'PLACEHOLDER', 'SYNTHETIC', 'MEASURED'].includes(t) ? t : 'NA';
}

export function tag(c) {
  const t = tagClass(c);
  const label = t === 'COMMERCIAL' ? 'COMMERCIAL SPEC' : (t === 'NA' ? 'NOT AVAILABLE' : t);
  return `<span class="tag ${t}">${label}</span>`;
}

/** Render a {v, unit, class, note} record, or NOT AVAILABLE. */
function valueRow(label, rec, digits = 2) {
  if (!rec || rec.v === null || rec.v === undefined) {
    return `<div class="k">${esc(label)}</div>${NA}`;
  }
  const n = typeof rec.v === 'number'
    ? (Math.abs(rec.v) >= 1e5 ? rec.v.toExponential(2) : rec.v.toFixed(digits))
    : esc(rec.v);
  const unit = rec.unit ? ` ${esc(rec.unit)}` : '';
  return `<div class="k">${esc(label)}${rec.note ? `<br><span style="font-size:9.5px">${esc(rec.note)}</span>` : ''}</div>` +
         `<div class="v">${n}${unit}${tag(rec.class)}</div>`;
}

function plain(label, value, cls) {
  if (value === null || value === undefined || value === '') return `<div class="k">${esc(label)}</div>${NA}`;
  return `<div class="k">${esc(label)}</div><div class="v">${esc(value)}${cls ? tag(cls) : ''}</div>`;
}

/* ------------------------------------------------------------------ side panels */

export function renderBasis(project, source) {
  const b = project.simulation_basis;
  $('panel-basis').innerHTML = `
    <div class="kv">
      ${plain('Active data source', source.name, source.klass)}
      ${plain('Flight model', b.model)}
      ${plain('Degrees of freedom', b.degrees_of_freedom)}
      ${plain('Trajectory', b.trajectory_is)}
      ${plain('Sensor data', b.sensor_data_is)}
      ${plain('Flight-phase source', source.phaseSource)}
      ${plain('Propulsion data', `${project.motor.status}`, project.motor.status)}
      ${plain('Motor designation', project.motor.designation)}
      ${plain('Flight certified', 'NO')}
    </div>
    <div class="callout warn"><b>Attitude</b><br>${esc(b.attitude_is)}</div>
    <div class="callout bad">This visualisation shows a <b>digital model</b>. Nothing has been built, powered,
    bench tested or flown, so no value on screen is a measurement of a real flight.</div>
    <p class="note">${esc(source.note || '')}</p>`;
}

export function renderEngineering(vehicle, project) {
  const g = vehicle.geometry, m = vehicle.mass, s = vehicle.stability;
  $('panel-engineering').innerHTML = `
    <div class="sub-h">GEOMETRY</div>
    <div class="kv">
      ${valueRow('Overall length', g.length_mm, 0)}
      ${valueRow('Body outside diameter', g.body_od_mm, 1)}
      ${valueRow('Nose length (ogive)', g.nose_len_mm, 0)}
      ${valueRow('Coupler / avionics bay length', g.coupler_len_mm, 0)}
      ${valueRow('Booster tube length', g.booster_len_mm, 0)}
      ${valueRow('Fin count', g.fin.count, 0)}
      ${valueRow('Fin root chord', g.fin.root_chord_mm, 0)}
      ${valueRow('Fin semi-span', g.fin.semi_span_mm, 0)}
      ${valueRow('Launch rail length', g.rail_length_m, 1)}
    </div>
    <div class="sub-h">MASS</div>
    <div class="kv">
      ${valueRow('Liftoff mass', m.liftoff_g, 1)}
      ${valueRow('Burnout mass', m.burnout_g, 1)}
      ${valueRow('Airframe mass (no motor)', m.airframe_g, 1)}
    </div>
    <div class="sub-h">STABILITY</div>
    <div class="kv">
      ${valueRow('CG at liftoff', s.cg_liftoff_mm, 1)}
      ${valueRow('CG at burnout', s.cg_burnout_mm, 1)}
      ${valueRow('CP (Barrowman)', s.cp_mm, 1)}
      ${valueRow('Static margin, liftoff', s.sm_liftoff_cal, 3)}
      ${valueRow('Static margin, rail exit', s.sm_rail_exit_cal, 3)}
      ${valueRow('Static margin, burnout', s.sm_burnout_cal, 3)}
      ${plain('Target band', s.target)}
    </div>
    <div class="sub-h">MODEL STATUS</div>
    <div class="kv">
      ${plain('CAD revision', vehicle.cad_rev)}
      ${plain('CAD validated', vehicle.cad_validation_date)}
      ${plain('Renderer', vehicle.openscad)}
      ${plain('Motor data', vehicle.motor_status, vehicle.motor_status)}
    </div>
    <p class="note">Stations are measured from the nose tip, the convention used throughout ASTRA-66.
    Static margin is the project's own value; the visualiser does not recompute stability.</p>`;
}

export function renderComponents(vehicle, onSelect) {
  const parts = [];
  const count = Object.values(vehicle.modules).reduce((n, items) => n + items.length, 0);
  for (const [mod, items] of Object.entries(vehicle.modules)) {
    parts.push(`<div class="sub-h">${esc(mod.toUpperCase())}</div><div class="kv">`);
    for (const it of items) {
      parts.push(
        `<div class="k"><a href="#" data-part="${esc(it.id)}" style="color:inherit;text-decoration:none;border-bottom:1px dotted #3d5162">${esc(it.id)}</a> ${esc(it.item)}</div>` +
        `<div class="v">${it.mass_g.toFixed(1)} g${tag(it.provenance)}</div>`,
      );
    }
    parts.push('</div>');
  }
  const el = $('panel-components');
  el.innerHTML = parts.join('') +
    `<p class="note">${count} items from <code>analysis/results/mass_budget.csv</code>. Click an identifier to inspect it
     in 3D. Electronics masses are planning assumptions: no component has been selected or weighed.</p>`;
  el.querySelectorAll('[data-part]').forEach((a) => {
    a.addEventListener('click', (e) => { e.preventDefault(); onSelect(a.dataset.part); });
  });
}

export function renderLimitations(project) {
  const nm = project.simulation_basis.not_modelled;
  $('panel-limits').innerHTML = `
    <div class="callout warn"><b>These limitations are part of the deliverable.</b> They are copied from the
    project's own engineering status document and simulation summary — not softened here.</div>
    <div class="sub-h">DOCUMENTED LIMITATIONS</div>
    <ul class="list">${project.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
    <div class="sub-h">NOT MODELLED BY THE FLIGHT SIMULATION</div>
    <ul class="list">${nm.map((l) => `<li>${esc(l)}</li>`).join('')}</ul>
    <div class="sub-h">PROPULSION</div>
    <p class="note">${esc(project.motor.note)}</p>`;
}

export function renderValidation(project) {
  const v = project.software_validation;
  const row = (k, val) => (val === null || val === undefined
    ? `<div class="k">${esc(k)}</div>${NA}`
    : `<div class="k">${esc(k)}</div><div class="v">${esc(val)}</div>`);
  $('panel-validation').innerHTML = `
    <div class="kv">
      ${row('Flight-simulation checks', v.simulation_checks ? `${v.simulation_checks[0]}/${v.simulation_checks[1]} PASS` : null)}
      ${row('Regression tests', v.regression_tests ? `${v.regression_tests} PASS` : null)}
      ${row('Avionics tests', v.avionics_tests ? `${v.avionics_tests} PASS` : null)}
      ${row('Total automated tests', v.total_tests ? `${v.total_tests} PASS` : null)}
      ${row('Failures', v.failures === null ? null : `${v.failures}`)}
      ${row('CAD checks', `${v.cad_checks.PASS} PASS / ${v.cad_checks.WARN} WARN / ${v.cad_checks.FAIL} FAIL`)}
      ${row('CAD ↔ avionics checks', `${v.cad_avionics_checks.PASS} PASS / ${v.cad_avionics_checks.WARN} WARN / ${v.cad_avionics_checks.UNVERIFIED} UNVERIFIED / ${v.cad_avionics_checks.FAIL} FAIL`)}
      ${row('Pipeline run', `${project.pipeline_overall} (${project.pipeline_date.slice(0, 10)})`)}
    </div>
    <div class="callout bad"><b>${esc(v.label)}</b>${esc(v.caveat)}</div>
    <div class="sub-h">PIPELINE STEPS</div>
    <ul class="list">${project.steps.map((s) => `<li>${s.ok ? '✔' : '✘'} ${esc(s.step)}</li>`).join('')}</ul>`;
}

export function renderSources(project) {
  const rows = project.sources.map((s) =>
    `<div class="k" style="word-break:break-all">${esc(s.path)}</div><div class="v" style="font-size:9.5px">${esc(s.sha256.slice(0, 10))}</div>`).join('');
  $('panel-sources').innerHTML = `
    <p class="note">Every number in this visualiser is read from the files below by
    <code>visualization/tools/export_flight_data.py</code>. The adapter is read-only: it never writes to the
    engineering project. SHA-256 prefixes identify the exact revision that was exported.</p>
    <div class="kv">${rows}</div>
    ${project.cad_mesh ? `<div class="sub-h">CAD MESH</div><div class="kv">
      ${plain('File', project.cad_mesh.source)}
      ${plain('Triangles', project.cad_mesh.triangles.toLocaleString())}
      ${plain('SHA-256', project.cad_mesh.sha256.slice(0, 10))}</div>` : ''}`;
}

/* ------------------------------------------------------------------ HUD */

export function renderHud(source, frame) {
  const rows = [];
  const push = (label, text, na = false, extra = '') => rows.push(
    `<div class="k">${esc(label)}</div><div class="v${na ? ' na' : ''}">${na ? 'NOT AVAILABLE' : esc(text)}${extra}</div>`);

  push('TIME', `${frame.t.toFixed(3)} s`);
  for (const c of source.channels.filter((x) => x.hud)) {
    const v = frame.values[c.key];
    if (v === null || v === undefined) push(c.label, '', true);
    else push(c.label, `${v.toFixed(c.digits)}${c.unit ? ` ${c.unit}` : ''}`,
      false, c.extra ? `<em>${esc(c.extra(v))}</em>` : '');
  }
  $('hud-rows').innerHTML = rows.join('');
  $('hud-phase').textContent = frame.phase || '—';
  $('hud-mode').textContent = source.shortName;
  $('hud-foot').textContent = `${source.klass} DATA · DIGITAL MODEL · NOT FLIGHT CERTIFIED`;
}

/* ------------------------------------------------------------------ inspector */

export function showComponent(component, partName, tagText) {
  const box = $('inspector');
  box.hidden = false;
  $('ins-title').textContent = partName || (component ? component.id : 'COMPONENT');
  if (!component) {
    $('ins-body').innerHTML = `<div class="kv">${plain('Component', partName)}</div>
      <p class="note">This feature is drawn from CAD parameters but has no separate line in the mass budget.</p>`;
    return;
  }
  $('ins-body').innerHTML = `
    <div class="kv">
      ${plain('Identifier', component.id)}
      ${plain('Module', component.module)}
      ${plain('Mass', `${component.mass_g.toFixed(1)} g`, component.provenance)}
      ${plain('CG station', `${component.station_mm} mm`)}
      ${plain('Status', 'MODELLED — not manufactured or weighed')}
      ${tagText ? plain('Note', tagText, tagText) : ''}
    </div>
    <p class="note">${component.note ? esc(component.note) : 'No further note in the mass budget.'}</p>
    <p class="note">Purpose and interface detail: <code>documentation/PROJECT_OVERVIEW.md</code>.</p>`;
}

export function hideComponent() { $('inspector').hidden = true; }

/* ------------------------------------------------------------------ summary */

export function showSummary(source, extra) {
  const rows = source.summary.map((r) =>
    `<tr><td>${esc(r.k)}</td><td class="v">${esc(r.v)}</td><td>${tag(r.c)}</td></tr>`).join('');
  $('sum-body').innerHTML = `
    <table>
      <thead><tr><th>QUANTITY</th><th style="text-align:right">VALUE</th><th>CLASS</th></tr></thead>
      <tbody>
        ${rows}
        <tr><td>Modelled path length</td><td class="v">${extra.pathLength.toFixed(0)} m</td><td>${tag(source.klass)}</td></tr>
      </tbody>
    </table>
    <div class="callout bad" style="margin-top:12px"><b>MODEL INPUT vs SIMULATED RESULT vs MEASURED RESULT</b>
    Model inputs are the masses, geometry and placeholder motor data. Simulated results come from the project's
    1-DOF model. <b>There are no measured results:</b> ASTRA-66 has never been built or flown.</div>`;
  $('summary').hidden = false;
}

export function hideSummary() { $('summary').hidden = true; }

/* ------------------------------------------------------------------ misc */

export function setChips(source, project) {
  $('chip-source').textContent = `DATA SOURCE: ${source.name}`;
  $('chip-model').textContent = `MODEL: ${project.simulation_basis.degrees_of_freedom}`;
}

export function renderTimelineMarks(source, el) {
  let lastPct = -99;
  let row = 0;
  el.innerHTML = source.events.map((e) => {
    const pct = Math.min(100, Math.max(0, (e.t_s / source.duration) * 100));
    row = pct - lastPct < 9 ? (row + 1) % 3 : 0;   // stagger crowded early events
    lastPct = pct;
    const edge = pct < 4 ? 'translateX(0)' : (pct > 96 ? 'translateX(-100%)' : 'translateX(-50%)');
    return `<span style="left:${pct.toFixed(2)}%;top:${row * 11}px;transform:${edge}" ` +
           `title="${esc(e.name)} ${esc(e.detail || '')}">${esc(e.name)}</span>`;
  }).join('');
}
