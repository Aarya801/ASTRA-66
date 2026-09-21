/**
 * Trajectory rendering.
 *
 * The flown path is drawn from the data source's own [t, altitude] pairs. The current model
 * is 1-DOF (vertical), so the path is vertical: no downrange component is invented. A faint
 * preview line shows the whole modelled path, and a bright line grows as the flight plays.
 */
import * as THREE from 'three';

export class Trajectory {
  /**
   * @param {THREE.Scene} scene
   * @param {Array<[number, number]>} path [t, altitude] pairs
   * @param {number} headRadius marker radius in metres (scaled to the flight, not the vehicle)
   */
  constructor(scene, path, headRadius = 1.6) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.path = path;
    this.times = path.map((p) => p[0]);

    const pts = path.map(([, h]) => new THREE.Vector3(0, h, 0));

    // full modelled path, dimmed
    this.preview = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineDashedMaterial({ color: 0x3f6f86, dashSize: 6, gapSize: 5, transparent: true, opacity: 0.55 }),
    );
    this.preview.computeLineDistances();
    this.group.add(this.preview);

    // flown path, grows with playback
    this.flownGeo = new THREE.BufferGeometry().setFromPoints(pts);
    this.flown = new THREE.Line(
      this.flownGeo,
      new THREE.LineBasicMaterial({ color: 0x5fd0f0, transparent: true, opacity: 0.95 }),
    );
    this.flownGeo.setDrawRange(0, 1);
    this.group.add(this.flown);

    // Apogee tick on the modelled path (the vehicle itself marks the current point, so no
    // extra head marker is drawn - it would only hide the rocket in the chase view).
    const peak = path.reduce((best, p) => (p[1] > best[1] ? p : best), path[0]);
    const tick = new THREE.Mesh(
      new THREE.SphereGeometry(headRadius * 0.45, 10, 8),
      new THREE.MeshBasicMaterial({ color: 0xe0a83a }),
    );
    tick.position.y = peak[1];
    this.group.add(tick);

    scene.add(this.group);
  }

  /** Reveal the path up to time t (seconds). */
  update(t, altitude) {
    let n = 1;
    while (n < this.times.length && this.times[n] <= t) n++;
    this.flownGeo.setDrawRange(0, Math.max(n, 2));
  }

  reset() {
    this.flownGeo.setDrawRange(0, 1);
  }

  setVisible(on) { this.group.visible = on; }

  dispose() {
    this.scene.remove(this.group);
    this.group.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
  }

  /** Total path length in metres (vertical model: ascent + descent). */
  static length(path) {
    let d = 0;
    for (let i = 1; i < path.length; i++) d += Math.abs(path[i][1] - path[i - 1][1]);
    return d;
  }
}
