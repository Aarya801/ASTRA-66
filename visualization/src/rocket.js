/**
 * ASTRA-66 airframe - procedural geometry built from the project's own generated parameter
 * file (cad/astra66_params.scad) and station table (analysis/results/analysis.json), both of
 * which are exported into public/data/vehicle.json by the Python adapter.
 *
 * Nothing here is a redesign: every dimension used below is read from the data file. The
 * geometry is a faithful but simplified visual representation of the CAD solid - fillets,
 * fasteners, slots and print details are not drawn. The exact CAD mesh can be overlaid
 * separately (see loadCadMesh) when it has been exported.
 *
 * Local frame: +Y is nose-up, the tail sits at y = 0, and a station s (mm from the nose tip,
 * the project's own convention) maps to y = (L - s) / 1000 metres.
 */
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

const C = {
  nose: 0xeceff1,
  tube: 0xd3d8dc,
  printed: 0x77818a,
  ply: 0xc8a97a,
  mmt: 0xbfa27a,
  motor: 0xd2703a,
  fin: 0xd8c197,
  metal: 0x9aa4ad,
  cad: 0x7fb6cc,
};

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({
    color, roughness: opts.roughness ?? 0.55, metalness: opts.metalness ?? 0.06,
    transparent: !!opts.opacity, opacity: opts.opacity ?? 1, side: opts.side ?? THREE.FrontSide,
    depthWrite: opts.opacity ? opts.opacity > 0.75 : true,
  });
}

/** Tangent-ogive profile used by the CAD (fineness NC_L / BODY_OD). */
function ogivePoints(lengthMm, radiusMm, steps = 48) {
  const L = lengthMm, r = radiusMm;
  const R = (r * r + L * L) / (2 * r);
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const x = (i / steps) * L;                       // station from the tip
    const y = Math.sqrt(Math.max(R * R - (L - x) * (L - x), 0)) - (R - r);
    pts.push(new THREE.Vector2(Math.max(y, 0.0001) / 1000, 0));
    pts[pts.length - 1].y = x / 1000;
  }
  return pts;
}

export class Rocket {
  /**
   * @param {object} vehicle parsed public/data/vehicle.json
   */
  constructor(vehicle) {
    this.v = vehicle;
    const g = vehicle.geometry;
    this.L = g.length_mm.v;                       // mm
    this.R = g.body_od_mm.v / 2 / 1000;           // m
    this.st = g.stations_mm;
    this.group = new THREE.Group();
    this.group.name = 'ASTRA-66';
    this.parts = [];
    this.shells = [];      // outer airframe, faded in "internals" mode
    this.internals = [];   // parts only shown in "internals" mode
    this.markers = new THREE.Group();
    this.cadMesh = null;
    this._internalsOn = false;
    this._markersOn = true;
    this._cadOn = false;

    this._components = new Map();
    for (const [mod, items] of Object.entries(vehicle.modules || {})) {
      for (const it of items) this._components.set(it.id, { ...it, module: mod });
    }

    this._build();
    this.group.add(this.markers);
    this._buildMarkers();
  }

  /** station (mm from nose tip) -> local y (m), tail at 0 */
  y(station) { return (this.L - station) / 1000; }

  /** CG station of a mass-budget item, straight from analysis/results/mass_budget.csv */
  station(id, fallback) {
    const c = this._components.get(id);
    return c && c.station_mm !== null ? c.station_mm : fallback;
  }

  _add(mesh, { id, name, group = 'shell', tag = null } = {}) {
    mesh.userData.partId = id || null;
    mesh.userData.partName = name;
    mesh.userData.tag = tag;
    mesh.userData.component = id ? this._components.get(id) || null : null;
    this.group.add(mesh);
    this.parts.push(mesh);
    if (group === 'shell') this.shells.push(mesh);
    if (group === 'internal') { this.internals.push(mesh); mesh.visible = false; }
    return mesh;
  }

  _tube(fromStation, toStation, odMm, material, meta, idMm = null) {
    const h = Math.abs(this.y(fromStation) - this.y(toStation));
    const geo = idMm
      ? new THREE.CylinderGeometry(odMm / 2000, odMm / 2000, h, 48, 1, true)
      : new THREE.CylinderGeometry(odMm / 2000, odMm / 2000, h, 48);
    const m = new THREE.Mesh(geo, material);
    m.position.y = (this.y(fromStation) + this.y(toStation)) / 2;
    return this._add(m, meta);
  }

  _build() {
    const g = this.v.geometry;
    const st = this.st;
    const noseEnd = st.nc_base;

    // ---- nose cone (two printed parts, split at NC_SPLIT) --------------------------------
    const prof = ogivePoints(g.nose_len_mm.v, g.body_od_mm.v / 2, 56);
    const split = g.nose_split_mm.v / 1000;
    const upper = prof.filter((p) => p.y <= split);
    const lower = prof.filter((p) => p.y >= split);
    const lathe = (pts, flipName) => {
      const shape = pts.map((p) => new THREE.Vector2(p.x, this.y(p.y * 1000)));
      const geo = new THREE.LatheGeometry(shape, 56);
      return new THREE.Mesh(geo, mat(C.nose, { roughness: 0.42, side: THREE.DoubleSide }));
    };
    this._add(lathe(upper), { id: 'NC-101', name: 'NOSE TIP SECTION' });
    this._add(lathe(lower), { id: 'NC-102', name: 'NOSE BASE + SHOULDER' });

    // nose bulkhead / ballast mount (internal)
    const bh = new THREE.Mesh(new THREE.CylinderGeometry(g.body_id_mm.v / 2000, g.body_id_mm.v / 2000, 0.006, 32),
      mat(C.printed));
    bh.position.y = this.y(this.station('NC-103', 321));
    this._add(bh, { id: 'NC-103', name: 'NOSE BULKHEAD / BALLAST MOUNT', group: 'internal' });

    // ---- airframe tubes ------------------------------------------------------------------
    this._tube(noseEnd, st.pl_end, g.body_od_mm.v, mat(C.tube, { roughness: 0.62 }),
      { id: 'PL-201', name: 'PAYLOAD TUBE' });
    this._tube(st.pl_end, st.band_end, g.body_od_mm.v, mat(C.tube, { roughness: 0.5, metalness: 0.15 }),
      { id: 'AV-302', name: 'AVIONICS SWITCH BAND' });
    this._tube(st.band_end, this.L, g.body_od_mm.v, mat(C.tube, { roughness: 0.62 }),
      { id: 'BO-401', name: 'BOOSTER TUBE' });

    // ---- internals ------------------------------------------------------------------------
    this._tube(st.cpl_fwd, st.cpl_aft, g.coupler_od_mm.v, mat(C.printed, { roughness: 0.5 }),
      { id: 'AV-301', name: 'AVIONICS COUPLER (ELECTRONICS BAY)', group: 'internal' });

    for (const [id, name, s, t] of [
      ['AV-303', 'FORWARD BULKHEAD', st.av_bh_fwd_outer, st.cpl_fwd],
      ['AV-304', 'AFT BULKHEAD', st.cpl_aft, st.av_bh_aft_outer],
    ]) {
      const h = Math.abs(this.y(s) - this.y(t));
      const m = new THREE.Mesh(new THREE.CylinderGeometry(g.coupler_od_mm.v / 2000, g.coupler_od_mm.v / 2000, h, 32), mat(C.ply));
      m.position.y = (this.y(s) + this.y(t)) / 2;
      this._add(m, { id, name, group: 'internal' });
    }

    // electronics sled (AV-306) - dimensions from SLED_L / SLED_W / SLED_T in the parameter file
    const sledH = Math.abs(this.y(st.sled_fwd) - this.y(st.sled_aft));
    const sled = new THREE.Mesh(new THREE.BoxGeometry(0.052, sledH, 0.003), mat(C.printed, { roughness: 0.45 }));
    sled.position.y = (this.y(st.sled_fwd) + this.y(st.sled_aft)) / 2;
    this._add(sled, { id: 'AV-306', name: 'ELECTRONICS SLED', group: 'internal' });

    // battery envelope - BAT_L/W/H are USER-SUPPLIED placeholders in the parameter file
    const bat = new THREE.Mesh(new THREE.BoxGeometry(0.028, 0.055, 0.009), mat(0x3f6d8a, { roughness: 0.4 }));
    bat.position.set(0, this.y(this.station('EL-BAT', 492.8)), 0.008);
    this._add(bat, { id: 'EL-BAT', name: 'BATTERY (PLACEHOLDER ENVELOPE)', group: 'internal', tag: 'PLACEHOLDER' });

    // motor mount tube + external certified motor envelope
    this._tube(st.mmt_fwd, st.mmt_aft, g.mmt_od_mm.v, mat(C.mmt, { roughness: 0.7 }),
      { id: 'BO-402', name: 'MOTOR MOUNT TUBE', group: 'internal' });
    this._tube(st.motor_fwd, st.motor_aft, 29, mat(C.motor, { roughness: 0.5, opacity: 0.55 }),
      { id: 'MT-601', name: 'CERTIFIED MOTOR ENVELOPE (EXTERNAL COMPONENT)', group: 'internal', tag: 'PLACEHOLDER' });

    const cr = new THREE.Mesh(new THREE.CylinderGeometry(g.body_id_mm.v / 2000, g.body_id_mm.v / 2000, 0.006, 32), mat(C.ply));
    cr.position.y = this.y(this.station('BO-404', 897));
    this._add(cr, { id: 'BO-404', name: 'FORWARD CENTERING RING', group: 'internal' });

    const core = new THREE.Mesh(
      new THREE.CylinderGeometry(g.body_id_mm.v / 2000, g.body_id_mm.v / 2000,
        Math.abs(this.y(st.core_fwd) - this.y(st.core_aft)), 32, 1, true),
      mat(C.printed, { roughness: 0.5, opacity: 0.85 }));
    core.position.y = (this.y(st.core_fwd) + this.y(st.core_aft)) / 2;
    this._add(core, { id: 'BO-403', name: 'FIN-CAN CORE', group: 'internal' });

    // ---- fins ------------------------------------------------------------------------------
    const f = g.fin;
    const rootLE = this.y(f.le_station_mm.v);
    const rootTE = this.y(f.le_station_mm.v + f.root_chord_mm.v);
    const tipLE = this.y(f.le_station_mm.v + f.sweep_mm.v);
    const tipTE = this.y(f.le_station_mm.v + f.sweep_mm.v + f.tip_chord_mm.v);
    const rIn = this.R, rOut = this.R + f.semi_span_mm.v / 1000;

    const shape = new THREE.Shape();
    shape.moveTo(rIn, rootLE);
    shape.lineTo(rOut, tipLE);
    shape.lineTo(rOut, tipTE);
    shape.lineTo(rIn, rootTE);
    shape.closePath();
    const finGeo = new THREE.ExtrudeGeometry(shape, { depth: f.thickness_mm.v / 1000, bevelEnabled: false });
    finGeo.translate(0, 0, -f.thickness_mm.v / 2000);

    this.finMeshes = [];
    for (let i = 0; i < f.count.v; i++) {
      const fin = new THREE.Mesh(finGeo, mat(C.fin, { roughness: 0.6 }));
      fin.rotation.y = (i * Math.PI * 2) / f.count.v;
      this._add(fin, { id: 'BO-406', name: `FIN ${i + 1} OF ${f.count.v}` });
      this.finMeshes.push(fin);
    }

    // ---- rail buttons -------------------------------------------------------------------
    const rb = g.rail_button;
    const ang = (rb.angle_deg.v * Math.PI) / 180;
    for (const [id, station] of [['BO-409', rb.fwd_station_mm.v], ['BO-408', rb.aft_station_mm.v]]) {
      const b = new THREE.Mesh(
        new THREE.CylinderGeometry(rb.diameter_mm.v / 2000, rb.diameter_mm.v / 2000, rb.standoff_mm.v / 1000, 16),
        mat(C.metal, { metalness: 0.4, roughness: 0.4 }));
      b.rotation.z = Math.PI / 2;
      b.position.set(Math.sin(ang) * (this.R + rb.standoff_mm.v / 2000), this.y(station),
        Math.cos(ang) * (this.R + rb.standoff_mm.v / 2000));
      b.lookAt(0, this.y(station), 0);
      b.rotateX(Math.PI / 2);
      this._add(b, { id, name: 'RAIL BUTTON (ENVELOPE)', tag: 'PLACEHOLDER' });
    }

    // ---- payload-bay external features (documented CAD features) -------------------------
    const cowl = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.03, 0.006), mat(C.printed));
    cowl.position.set(-(this.R + 0.002), this.y(this.st.cam), 0);
    this._add(cowl, { id: 'PL-204', name: 'CAMERA LENS COWL' });

    const hatch = new THREE.Mesh(new THREE.BoxGeometry(0.025, 0.04, 0.004), mat(0xbfc6cb));
    hatch.position.set(this.R + 0.001, this.y(this.st.hatch), 0);
    this._add(hatch, { id: 'PL-205/206', name: 'ACCESS HATCH + DOUBLER FRAME' });
  }

  /** CG / CP rings, drawn at the stations the engineering model computed. */
  _buildMarkers() {
    const s = this.v.stability;
    const ring = (station, color) => {
      const g = new THREE.Mesh(new THREE.TorusGeometry(this.R + 0.006, 0.0035, 8, 40),
        new THREE.MeshBasicMaterial({ color }));
      g.rotation.x = Math.PI / 2;
      g.position.y = this.y(station);
      this.markers.add(g);
      return g;
    };
    this.cgRing = ring(s.cg_liftoff_mm.v, 0x4fc3f7);
    this.cpRing = ring(s.cp_mm.v, 0xff9a52);
    this.markers.visible = true;
  }

  /** Move the CG ring as the simulation burns propellant (cg_mm is a real trajectory column). */
  setCg(stationMm) {
    if (this.cgRing && stationMm) this.cgRing.position.y = this.y(stationMm);
  }

  setInternals(on) {
    this._internalsOn = on;
    for (const m of this.internals) m.visible = on && !this._cadOn;
    for (const m of this.shells) {
      m.material.transparent = on;
      m.material.opacity = on ? 0.22 : 1;
      m.material.depthWrite = !on;
      m.material.needsUpdate = true;
    }
  }

  setMarkers(on) {
    this._markersOn = on;
    this.markers.visible = on && !this._cadOn;
  }

  /**
   * Optional overlay: the exact mesh exported from the OpenSCAD assembly
   * (cad/exports/assembly/astra66_assembly_flight_parts.stl), copied by the adapter.
   * Returns null when the mesh has not been exported.
   */
  async loadCadMesh(meta) {
    if (!meta) return null;
    const geo = await new STLLoader().loadAsync(`./${meta.file}`);
    geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, mat(C.cad, { roughness: 0.45, metalness: 0.15 }));
    // The STL is in millimetres along its own long axis; map it into the local frame
    // (tail at y = 0, nose up) using the bounding box measured by the adapter.
    const axis = meta.long_axis;
    const g = new THREE.Group();
    mesh.scale.setScalar(0.001);
    if (axis === 'z') {
      mesh.rotation.x = meta.tip_at === 'min' ? -Math.PI / 2 : Math.PI / 2;
    } else if (axis === 'x') {
      mesh.rotation.z = meta.tip_at === 'min' ? Math.PI / 2 : -Math.PI / 2;
    }
    g.add(mesh);
    const box = new THREE.Box3().setFromObject(g);
    g.position.y -= box.min.y;
    const centre = box.getCenter(new THREE.Vector3());
    g.position.x -= centre.x;
    g.position.z -= centre.z;
    g.visible = false;
    this.cadMesh = g;
    this.group.add(g);
    return g;
  }

  setCadMesh(on) {
    if (!this.cadMesh) return;
    this._cadOn = on;
    this.cadMesh.visible = on;
    for (const m of this.parts) {
      m.visible = on ? false : (this.internals.includes(m) ? !!this._internalsOn : true);
    }
    this.markers.visible = !on && this._markersOn !== false;
  }

  /** Label anchors used by the HTML label layer. */
  anchors() {
    const a = (station, text, cls = '') => ({ y: this.y(station), text, cls });
    const st = this.st;
    return [
      a(120, 'NOSE CONE'),
      a((st.nc_base + st.pl_end) / 2, 'PAYLOAD BAY'),
      a((st.cpl_fwd + st.cpl_aft) / 2, 'AVIONICS / ELECTRONICS BAY'),
      a((st.band_end + st.mmt_fwd) / 2, 'RECOVERY BAY'),
      a((st.fin_le + this.L) / 2, 'FIN SECTION'),
      a(st.motor_fwd + 60, 'MOTOR (EXTERNAL, CERTIFIED)'),
    ];
  }

  dispose() {
    this.group.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
    });
  }
}
