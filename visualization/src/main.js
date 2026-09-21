/**
 * ASTRA-66 digital flight visualisation - application entry point.
 *
 * Architecture (see 3D_SIMULATOR_README.md):
 *   ASTRA-66 engineering data  ->  Python adapter  ->  public/data/*.json
 *        ->  data.js (FlightSource)  ->  scene + UI  ->  three.js
 *
 * The engineering model stays the source of truth. This file animates it; it does not
 * simulate anything.
 */
import * as THREE from 'three';
import { loadAll, simSource, replaySource } from './data.js';
import { Rocket } from './rocket.js';
import { Environment } from './environment.js';
import { Trajectory } from './trajectory.js';
import { CameraRig } from './cameras.js';
import { Labels } from './labels.js';
import * as UI from './ui.js';
import * as SITE from './site.js';

const $ = (id) => document.getElementById(id);

const app = {
  t: 0,
  playing: false,
  speed: 1,
  scale: 25,
  source: null,
  sources: {},
  inspect: false,
  toggles: { labels: false, cgcp: true, internals: false, trajectory: true, grid: true, cad: false },
};

// Exposed so that the automated UI smoke test (and anyone debugging) can inspect state
// from the console. Read-only by convention; nothing in the app reads it back.
window.ASTRA66 = app;

init().catch((err) => {
  $('loading').innerHTML = `<div style="max-width:520px;text-align:center;color:#f0c4bc;line-height:1.6">
     <b>Could not start the visualiser</b><br>${String(err.message || err)}</div>`;
  console.error(err);
});

async function init() {
  const data = await loadAll();
  app.data = data;

  app.sources.sim = simSource(data.trajectory);
  app.sources.replay = replaySource(data.replay);
  app.source = app.sources.sim;

  /* ---------------------------------------------------------------- renderer + scene */
  const canvas = $('scene');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  app.renderer = renderer;

  const scene = new THREE.Scene();
  app.scene = scene;

  const vehicleLen = data.vehicle.geometry.length_mm.v / 1000;
  const apogee = data.trajectory.results.apogee_m;

  app.env = new Environment(scene, {
    apogee,
    railLengthM: data.vehicle.geometry.rail_length_m.v,
    vehicleLengthM: vehicleLen,
  });

  app.rocket = new Rocket(data.vehicle);
  scene.add(app.rocket.group);
  app.rocket.group.scale.setScalar(app.scale);
  app.env.setVehicleScale(app.scale);

  app.rig = new CameraRig(canvas, apogee, vehicleLen);
  app.labels = new Labels($('labels'));

  app.headRadius = Math.max(apogee * 0.005, 0.4);
  app.traj = new Trajectory(scene, app.source.path, app.headRadius);

  buildLabels();

  /* ---------------------------------------------------------------- panels */
  UI.renderBasis(data.project, app.source);
  UI.renderEngineering(data.vehicle, data.project);
  UI.renderComponents(data.vehicle, selectPartById);
  UI.renderLimitations(data.project);
  UI.renderValidation(data.project);
  UI.renderSources(data.project);
  UI.setChips(app.source, data.project);
  UI.renderTimelineMarks(app.source, $('tl-marks'));

  /* ---------------------------------------------------------------- website sections */
  SITE.renderHeroStats(data.trajectory, data.project);
  SITE.renderFlightSection(data.trajectory, data.replay);
  SITE.renderSystemSection(data.project);
  SITE.renderValidationSection(data.project);
  SITE.renderLimitsSection(data.project);
  SITE.renderFootNote(data.project);
  SITE.wireScrollSpy();

  /* ---------------------------------------------------------------- optional CAD mesh */
  if (data.project.cad_mesh) {
    $('btn-cad').hidden = false;
    app.rocket.loadCadMesh(data.project.cad_mesh).catch((e) => {
      console.warn('CAD mesh unavailable:', e);
      $('btn-cad').hidden = true;
    });
  }

  wireUi();
  // On a phone or small tablet the panels would cover the 3D view: start collapsed and let
  // the visitor open them with the PANELS button.
  if (innerWidth < 1150) $('sidebar').classList.add('hidden');
  fillSourceSelect();
  setSource('sim');
  resize();
  addEventListener('resize', resize);
  // the viewport also changes size when the sidebar is toggled or the page reflows
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe($('viewport'));

  $('loading').classList.add('hidden');

  watchVisibility();
  tick(0);   // one frame now, so the canvas is never blank when it scrolls into view

  let last = performance.now();
  renderer.setAnimationLoop((now) => {
    const dt = Math.min((now - last) / 1000, 0.1);
    last = now;
    // Skip the frame entirely while the simulator is scrolled out of view: the page below is
    // long, and a hidden WebGL canvas should not cost the visitor anything.
    if (app.offscreen) return;
    tick(dt);
  });
}

/**
 * Pause rendering (and playback) while the simulator is off screen, and restore it when the
 * visitor scrolls back. Keeps a long landing page cheap on a laptop battery.
 */
function watchVisibility() {
  if (!('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      app.offscreen = !e.isIntersecting;
      if (app.offscreen && app.playing) {
        app.wasPlaying = true;
        app.playing = false;
        setPlayButtons();
      } else if (!app.offscreen && app.wasPlaying) {
        app.wasPlaying = false;
        app.playing = true;
        setPlayButtons();
      }
    }
  }, { threshold: 0.03 });
  io.observe($('simulator'));
}

/* ------------------------------------------------------------------ labels */

function buildLabels() {
  const L = app.labels;
  const R = app.rocket;
  L.clear();

  const local = (y) => () => new THREE.Vector3(0, R.group.position.y + y * app.scale, 0);

  for (const a of R.anchors()) L.add(local(a.y), a.text, 'part');

  L.add(() => new THREE.Vector3(0, R.group.position.y + R.y(app.cgStation ?? R.v.stability.cg_liftoff_mm.v) * app.scale, 0),
    'CG', 'cg');
  L.add(() => new THREE.Vector3(0, R.group.position.y + R.y(R.v.stability.cp_mm.v) * app.scale, 0), 'CP', 'cp');

  L.add(new THREE.Vector3(9, app.env.apogeeY, 0),
    `APOGEE ${app.data.trajectory.results.apogee_m.toFixed(1)} m (simulated)`, 'mark');
  L.add(new THREE.Vector3(0, 0.5, 6), 'LAUNCH PAD / RAIL', 'mark dim');

  for (const t of app.env.tickLabels) {
    if (t.y === 0 || t.y % 100 !== 0) continue;
    L.add(new THREE.Vector3(-20, t.y, 0), t.text, 'mark dim');
  }

  applyToggles();
}

/* ------------------------------------------------------------------ playback */

function tick(dt) {
  if (app.playing) {
    app.t += dt * app.speed;
    if (app.t >= app.source.duration) {
      app.t = app.source.duration;
      app.playing = false;
      setPlayButtons();
      UI.showSummary(app.source, { pathLength: Trajectory.length(app.source.path) });
    }
    $('timeline').value = String((app.t / app.source.duration) * 1000);
  }

  const frame = app.source.sample(app.t);
  app.frame = frame;

  const y = frame.altitude ?? 0;
  app.rocket.group.position.y = y;
  if (frame.values.cg_mm) {
    app.cgStation = frame.values.cg_mm;
    app.rocket.setCg(frame.values.cg_mm);
  }

  app.traj.update(app.t, y);
  UI.renderHud(app.source, frame);
  $('t-now').textContent = `T + ${app.t.toFixed(3)} s`;

  app.vehiclePos = new THREE.Vector3(0, y + (app.rocket.L / 2000) * app.scale, 0);
  app.rig.update(dt, app.vehiclePos, app.scale);

  const w = app.renderer.domElement.clientWidth;
  const h = app.renderer.domElement.clientHeight;
  app.labels.update(app.rig.camera, w, h);
  app.renderer.render(app.scene, app.rig.camera);
}

function setTime(t) {
  app.t = Math.max(0, Math.min(t, app.source.duration));
  if (app.rig) app.rig.snap();
  $('timeline').value = String((app.t / app.source.duration) * 1000);
  UI.hideSummary();
}

function setPlayButtons() {
  $('btn-play').classList.toggle('on', app.playing);
  $('btn-pause').classList.toggle('on', !app.playing);
}

/* ------------------------------------------------------------------ sources */

function fillSourceSelect() {
  $('sel-source').innerHTML = Object.values(app.sources)
    .map((s) => `<option value="${s.id}">${s.name}</option>`).join('');
}

function setSource(id) {
  const s = app.sources[id];
  if (!s) return;
  app.source = s;
  app.t = 0;
  app.playing = false;
  setPlayButtons();
  UI.hideSummary();

  app.traj.dispose();
  app.traj = new Trajectory(app.scene, s.path, app.headRadius);
  app.rig.snap();
  app.traj.setVisible(app.toggles.trajectory);

  UI.setChips(s, app.data.project);
  UI.renderBasis(app.data.project, s);
  UI.renderTimelineMarks(s, $('tl-marks'));
  $('t-end').textContent = `/ ${s.duration.toFixed(1)} s`;
  $('sel-source').value = id;
}

/* ------------------------------------------------------------------ picking */

const ray = new THREE.Raycaster();
const ptr = new THREE.Vector2();

function pick(event) {
  if (!app.inspect) return;
  const rect = app.renderer.domElement.getBoundingClientRect();
  ptr.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  ptr.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  ray.setFromCamera(ptr, app.rig.camera);
  const hits = ray.intersectObjects(app.rocket.parts.filter((m) => m.visible), false);
  if (!hits.length) { UI.hideComponent(); return; }
  const o = hits[0].object;
  UI.showComponent(o.userData.component, o.userData.partName, o.userData.tag);
}

function selectPartById(id) {
  const mesh = app.rocket.parts.find((m) => m.userData.partId === id);
  UI.showComponent(mesh ? mesh.userData.component : findComponent(id), mesh ? mesh.userData.partName : id,
    mesh ? mesh.userData.tag : null);
  if (mesh && !app.inspect) setInspect(true);
}

function findComponent(id) {
  for (const items of Object.values(app.data.vehicle.modules)) {
    const hit = items.find((i) => i.id === id);
    if (hit) return hit;
  }
  return null;
}

/* ------------------------------------------------------------------ toggles + wiring */

function applyToggles() {
  const t = app.toggles;
  app.labels.setGroupVisible('part', t.labels);
  app.labels.setGroupVisible('cg', t.cgcp && !t.cad);
  app.labels.setGroupVisible('cp', t.cgcp && !t.cad);
  app.rocket.setMarkers(t.cgcp);
  app.rocket.setInternals(t.internals);
  app.traj.setVisible(t.trajectory && !app.inspect);
  app.env.setGrid(t.grid);
  app.rocket.setCadMesh(t.cad);
}

function setInspect(on) {
  app.inspect = on;
  document.querySelector('[data-toggle="inspect"]').classList.toggle('on', on);
  document.querySelectorAll('[data-cam]').forEach((b) => b.classList.remove('on'));
  if (on) {
    app.playing = false;
    setPlayButtons();
    app.scaleBeforeInspect = app.scale;
    app.scale = 1;
    $('sel-scale').value = '1';
    applyScale();
    app.env.setInspectBackdrop(true);
    app.rig.setMode('inspect', { scale: 1, baseY: app.rocket.group.position.y });
    app.rocket.setInternals(true);
    app.toggles.internals = true;
    document.querySelector('[data-toggle="internals"]').classList.add('on');
    app.toggles.labels = true;
    document.querySelector('[data-toggle="labels"]').classList.add('on');
    applyToggles();
  } else {
    UI.hideComponent();
    if (app.scaleBeforeInspect) {
      app.scale = app.scaleBeforeInspect;
      $('sel-scale').value = String(app.scale);
      applyScale();
    }
    app.env.setInspectBackdrop(false);
    document.querySelector('[data-cam="free"]').classList.add('on');
    app.rig.setMode('free');
    applyToggles();
  }
}

function applyScale() {
  app.rocket.group.scale.setScalar(app.scale);
  app.env.setVehicleScale(app.scale);
}

function wireUi() {
  // panels
  document.querySelectorAll('.panel h2').forEach((h) => h.addEventListener('click', () => {
    const p = h.parentElement;
    p.dataset.open = p.dataset.open === 'true' ? 'false' : 'true';
  }));
  $('btn-sidebar').addEventListener('click', () => $('sidebar').classList.toggle('hidden'));

  // transport
  $('btn-play').addEventListener('click', () => {
    if (app.t >= app.source.duration) app.t = 0;
    app.playing = true; UI.hideSummary(); setPlayButtons();
    if (app.inspect) setInspect(false);
  });
  $('btn-pause').addEventListener('click', () => { app.playing = false; setPlayButtons(); });
  $('btn-reset').addEventListener('click', () => { app.playing = false; setTime(0); app.traj.reset(); setPlayButtons(); });
  $('btn-restart').addEventListener('click', () => {
    setTime(0); app.traj.reset(); app.playing = true; setPlayButtons();
    if (app.inspect) setInspect(false);
  });
  $('timeline').addEventListener('input', (e) => {
    setTime((Number(e.target.value) / 1000) * app.source.duration);
  });

  document.querySelectorAll('[data-speed]').forEach((b) => b.addEventListener('click', () => {
    app.speed = Number(b.dataset.speed);
    document.querySelectorAll('[data-speed]').forEach((x) => x.classList.toggle('on', x === b));
  }));

  $('sel-source').addEventListener('change', (e) => setSource(e.target.value));
  $('sel-scale').addEventListener('change', (e) => { app.scale = Number(e.target.value); applyScale(); });

  // cameras
  document.querySelectorAll('[data-cam]').forEach((b) => b.addEventListener('click', () => {
    if (app.inspect) { setInspect(false); }
    document.querySelectorAll('[data-cam]').forEach((x) => x.classList.toggle('on', x === b));
    app.rig.setMode(b.dataset.cam, { scale: app.scale });
    // place the camera straight away so the switch is visible even while paused
    app.rig.snap();
    app.rig.update(1, app.vehiclePos || new THREE.Vector3(), app.scale);
  }));

  // display toggles
  document.querySelectorAll('[data-toggle]').forEach((b) => b.addEventListener('click', () => {
    const key = b.dataset.toggle;
    if (key === 'inspect') { setInspect(!app.inspect); return; }
    app.toggles[key] = !app.toggles[key];
    b.classList.toggle('on', app.toggles[key]);
    applyToggles();
  }));

  $('ins-close').addEventListener('click', UI.hideComponent);
  $('sum-close').addEventListener('click', UI.hideSummary);
  app.renderer.domElement.addEventListener('click', pick);

  // Keyboard shortcuts apply only while the pointer is over the simulator, so that Space still
  // scrolls the page everywhere else on the site.
  const appEl = document.querySelector('.app');
  appEl.addEventListener('pointerenter', () => { app.hover = true; });
  appEl.addEventListener('pointerleave', () => { app.hover = false; });

  addEventListener('keydown', (e) => {
    if (!app.hover || app.offscreen) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); app.playing = !app.playing; setPlayButtons(); }
    if (e.code === 'KeyR') { setTime(0); app.traj.reset(); }
    if (e.code === 'KeyI') setInspect(!app.inspect);
  });

  // hero call to action: scroll to the simulator and start playing from the pad
  const heroRun = $('btn-hero-run');
  if (heroRun) {
    heroRun.addEventListener('click', () => {
      setTime(0);
      app.traj.reset();
      app.wasPlaying = true;          // the visibility observer starts it once the stage is in view
      if (app.inspect) setInspect(false);
    });
  }

  setPlayButtons();
}

function resize() {
  const el = $('viewport');
  const w = el.clientWidth, h = el.clientHeight;
  if (!w || !h) return;
  // Cap the device pixel ratio: 2 on desktop, 1.5 on phones, where the GPU budget is smaller
  // and the canvas is dense with UI anyway.
  app.renderer.setPixelRatio(Math.min(devicePixelRatio, w < 700 ? 1.5 : 2));
  app.renderer.setSize(w, h, false);
  app.rig.resize(w, h);
}
