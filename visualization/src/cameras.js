/**
 * Camera system: FREE (orbit), CHASE, GROUND, SIDE (trajectory profile), TOP and INSPECT.
 * Every mode uses one perspective camera; only the placement rule changes, which keeps the
 * render path simple and the frame rate stable on a laptop.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const MODES = ['free', 'chase', 'ground', 'side', 'top', 'inspect'];

export class CameraRig {
  constructor(canvas, apogee, vehicleLen) {
    this.apogee = apogee;
    this.vehicleLen = vehicleLen;
    this.camera = new THREE.PerspectiveCamera(48, 1, 0.05, 40000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.maxPolarAngle = Math.PI * 0.499;
    this.controls.minDistance = 0.3;
    this.controls.maxDistance = 4000;
    this.mode = 'free';
    this.target = new THREE.Vector3(0, 0, 0);
    this._smoothed = new THREE.Vector3(0, 0, 0);
    this.setMode('free');
  }

  setMode(mode, opts = {}) {
    if (!MODES.includes(mode)) return;
    this.mode = mode;
    const a = this.apogee;
    const orbit = mode === 'free' || mode === 'inspect';
    this.controls.enabled = orbit;

    if (mode === 'free') {
      this.camera.position.set(a * 0.30, a * 0.26, a * 0.52);
      this.controls.target.set(0, a * 0.18, 0);
      this.camera.fov = 48;
    } else if (mode === 'inspect') {
      // Frame the vehicle where it actually is: inspect can be entered mid-flight, so the
      // camera is offset from the vehicle's current altitude, not from the pad.
      const L = this.vehicleLen * (opts.scale || 1);
      const baseY = opts.baseY || 0;
      this.camera.position.set(L * 0.95, baseY + L * 0.78, L * 1.35);
      this.controls.target.set(0, baseY + L * 0.5, 0);
      this.camera.fov = 40;
    }
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }

  /**
   * @param {number} dt         frame time
   * @param {THREE.Vector3} veh vehicle position (world)
   * @param {number} scale      current visual scale of the vehicle
   */
  update(dt, veh, scale) {
    const a = this.apogee;
    // Smooth follow during playback, but snap after a jump (scrubbing the timeline, a reset
    // or a data-source change teleports the vehicle).
    if (this._snap || this._smoothed.distanceTo(veh) > a * 0.06) this._smoothed.copy(veh);
    else this._smoothed.lerp(veh, Math.min(1, dt * 3.2));
    this._snap = false;
    const v = this._smoothed;

    switch (this.mode) {
      case 'chase': {
        const back = Math.max(this.vehicleLen * scale * 2.2, 12);
        this.camera.position.set(back * 0.75, v.y + back * 0.35, back);
        this.camera.lookAt(0, v.y, 0);
        break;
      }
      case 'ground': {
        this.camera.position.set(26, 2.2, 34);
        this.camera.lookAt(0, Math.max(v.y, 1.5), 0);
        break;
      }
      case 'side': {
        this.camera.position.set(0, a * 0.5, a * 1.45);
        this.camera.lookAt(0, a * 0.5, 0);
        break;
      }
      case 'top': {
        this.camera.position.set(0, a * 1.35, 0.001);
        this.camera.lookAt(0, 0, 0);
        break;
      }
      default:
        this.controls.update();
    }
  }

  /** Make the next update place the camera immediately, without follow lag. */
  snap() { this._snap = true; }

  resize(w, h) {
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }
}
