/**
 * HTML label layer: projects world points to screen space each frame. Lighter than an extra
 * WebGL renderer pass and it keeps label text crisp and selectable-free.
 */
import * as THREE from 'three';

export class Labels {
  constructor(container) {
    this.el = container;
    this.items = [];
    this._v = new THREE.Vector3();
  }

  clear() {
    this.el.innerHTML = '';
    this.items = [];
  }

  /**
   * @param {THREE.Vector3|function} position world position, or a function returning one
   * @param {string} text
   * @param {string} cls extra CSS class
   */
  add(position, text, cls = '') {
    const div = document.createElement('div');
    div.className = `lb ${cls}`;
    div.textContent = text;
    this.el.appendChild(div);
    const item = { position, div, visible: true };
    this.items.push(item);
    return item;
  }

  setGroupVisible(cls, on) {
    for (const it of this.items) {
      if (it.div.classList.contains(cls)) {
        it.visible = on;
        if (!on) it.div.style.display = 'none';
      }
    }
  }

  update(camera, width, height) {
    const placed = [];
    for (const it of this.items) {
      if (!it.visible) { it.div.style.display = 'none'; continue; }
      const p = typeof it.position === 'function' ? it.position() : it.position;
      this._v.copy(p).project(camera);
      const behind = this._v.z > 1 || this._v.z < -1;
      const x = (this._v.x * 0.5 + 0.5) * width;
      const y = (-this._v.y * 0.5 + 0.5) * height;
      const off = behind || x < -80 || y < -40 || x > width + 80 || y > height + 40;
      // hide a label that would sit on top of one already placed (happens when the vehicle
      // is small on screen); the marker it points at stays visible.
      const clash = !off && placed.some((p) => Math.abs(p.x - x) < 130 && Math.abs(p.y - y) < 15);
      it.div.style.display = off || clash ? 'none' : 'block';
      if (!off && !clash) {
        it.div.style.left = `${x.toFixed(1)}px`;
        it.div.style.top = `${y.toFixed(1)}px`;
        placed.push({ x, y });
      }
    }
  }
}
