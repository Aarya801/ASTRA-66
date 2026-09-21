/**
 * Scene furniture: sky, ground, grid, launch pad and rail, coordinate axes, altitude ruler
 * and the apogee marker. Everything with a physical size is taken from the data files
 * (rail length, vehicle length, apogee); nothing here carries engineering meaning of its own.
 */
import * as THREE from 'three';

function skyTexture() {
  const c = document.createElement('canvas');
  c.width = 32; c.height = 256;
  const g = c.getContext('2d').createLinearGradient(0, 0, 0, 256);
  g.addColorStop(0.00, '#0a1119');
  g.addColorStop(0.42, '#16303f');
  g.addColorStop(0.62, '#284d61');
  g.addColorStop(0.78, '#4e7386');
  g.addColorStop(1.00, '#0f1a22');
  const ctx = c.getContext('2d');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 32, 256);
  const t = new THREE.CanvasTexture(c);
  t.mapping = THREE.EquirectangularReflectionMapping;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export class Environment {
  /**
   * @param {THREE.Scene} scene
   * @param {object} opts { apogee, railLengthM, vehicleLengthM }
   */
  constructor(scene, opts) {
    this.scene = scene;
    this.o = opts;
    this.groups = {};

    this.sky = skyTexture();
    this.backdrop = new THREE.Color(0x0e161d);
    scene.background = this.sky;
    this.fog = new THREE.FogExp2(0x16222c, 0.00035);
    scene.fog = this.fog;

    scene.add(new THREE.HemisphereLight(0x9dc2dd, 0x1b2630, 1.05));
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(120, 220, 160);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x86b6d6, 0.7);
    rim.position.set(-160, 60, -120);
    scene.add(rim);

    this._ground();
    this._pad();
    this._axes();
    this._ruler();
    this._apogee();
  }

  _ground() {
    const g = new THREE.Group();
    const r = 2600;
    const disc = new THREE.Mesh(
      new THREE.CircleGeometry(r, 96),
      new THREE.MeshStandardMaterial({ color: 0x1b2730, roughness: 0.96, metalness: 0 }),
    );
    disc.rotation.x = -Math.PI / 2;
    disc.position.y = -0.02;
    g.add(disc);

    const grid = new THREE.GridHelper(2000, 40, 0x35505f, 0x233340);
    grid.material.transparent = true;
    grid.material.opacity = 0.55;
    g.add(grid);
    this.grid = grid;

    const fine = new THREE.GridHelper(100, 20, 0x2c4553, 0x24343f);
    fine.material.transparent = true;
    fine.material.opacity = 0.5;
    fine.position.y = 0.005;
    g.add(fine);
    this.fineGrid = fine;

    this.scene.add(g);
    this.groups.ground = g;
  }

  /** Launch pad and rail, at true size, inside a group that follows the vehicle's visual scale. */
  _pad() {
    const g = new THREE.Group();
    const railL = this.o.railLengthM;

    const pad = new THREE.Mesh(
      new THREE.CylinderGeometry(0.42, 0.5, 0.05, 24),
      new THREE.MeshStandardMaterial({ color: 0x33424d, roughness: 0.85 }),
    );
    pad.position.y = 0.025;
    g.add(pad);

    const rail = new THREE.Mesh(
      new THREE.BoxGeometry(0.03, railL, 0.03),
      new THREE.MeshStandardMaterial({ color: 0x8b969f, roughness: 0.4, metalness: 0.55 }),
    );
    rail.position.set(0.055, railL / 2 + 0.05, 0);
    g.add(rail);

    const foot = new THREE.Mesh(
      new THREE.BoxGeometry(0.22, 0.03, 0.12),
      new THREE.MeshStandardMaterial({ color: 0x6d7880, roughness: 0.5, metalness: 0.4 }),
    );
    foot.position.set(0.11, 0.065, 0);
    g.add(foot);

    this.scene.add(g);
    this.groups.pad = g;
    this.pad = g;
  }

  _axes() {
    const g = new THREE.Group();
    const len = 30;
    const axis = (dir, color) => {
      const pts = [new THREE.Vector3(0, 0, 0), dir.clone().multiplyScalar(len)];
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8 }),
      );
      g.add(line);
    };
    axis(new THREE.Vector3(1, 0, 0), 0xc9584a);   // X - downrange reference
    axis(new THREE.Vector3(0, 1, 0), 0x5bbd7e);   // Y - altitude
    axis(new THREE.Vector3(0, 0, 1), 0x4a86c9);   // Z
    g.position.y = 0.01;
    this.scene.add(g);
    this.groups.axes = g;
  }

  /** Vertical altitude ruler: ticks every 50 m up to a little beyond apogee. */
  _ruler() {
    const g = new THREE.Group();
    const top = Math.ceil(this.o.apogee / 50) * 50 + 50;
    const pts = [];
    this.tickLabels = [];
    for (let h = 0; h <= top; h += 50) {
      pts.push(new THREE.Vector3(-14, h, 0), new THREE.Vector3(-6, h, 0));
      this.tickLabels.push({ y: h, text: `${h} m` });
    }
    pts.push(new THREE.Vector3(-10, 0, 0), new THREE.Vector3(-10, top, 0));
    const line = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x4a6577, transparent: true, opacity: 0.75 }),
    );
    g.add(line);
    this.scene.add(g);
    this.groups.ruler = g;
  }

  _apogee() {
    const g = new THREE.Group();
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(9, 0.22, 6, 64),
      new THREE.MeshBasicMaterial({ color: 0xe0a83a, transparent: true, opacity: 0.85 }),
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = this.o.apogee;
    g.add(ring);
    this.scene.add(g);
    this.groups.apogee = g;
    this.apogeeY = this.o.apogee;
  }

  setVehicleScale(s) {
    this.pad.scale.setScalar(s);
  }

  /**
   * Inspection backdrop: a plain dark field with no sky, fog, ruler or world grid, so the
   * airframe reads clearly at true size. Purely a viewing mode - no data changes.
   */
  setInspectBackdrop(on) {
    this.scene.background = on ? this.backdrop : this.sky;
    this.scene.fog = on ? null : this.fog;
    this.groups.ground.visible = !on;
    this.groups.ruler.visible = !on && this._gridOn !== false;
    this.groups.apogee.visible = !on;
    this.groups.axes.visible = !on;
    this.pad.visible = !on;
  }

  setGrid(on) {
    this._gridOn = on;
    this.grid.visible = on;
    this.fineGrid.visible = on;
    this.groups.ruler.visible = on && this.groups.ground.visible;
  }
}
