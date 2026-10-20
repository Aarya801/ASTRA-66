import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { loadAll, replaySource, simSource, validateDataBundle } from '../src/data.js';

const dataDir = new URL('../public/data/', import.meta.url);

async function committedBundle() {
  const names = ['vehicle', 'trajectory', 'replay', 'project'];
  const values = await Promise.all(names.map(async (name) =>
    JSON.parse(await readFile(new URL(`${name}.json`, dataDir), 'utf8'))));
  return Object.fromEntries(names.map((name, index) => [name, values[index]]));
}

test('committed exports satisfy the visualization data contract', async () => {
  const bundle = await committedBundle();
  assert.equal(validateDataBundle(bundle), bundle);
});

test('an incompatible trajectory reports its missing channel before rendering', async () => {
  const bundle = await committedBundle();
  const column = bundle.trajectory.columns.indexOf('altitude_m');
  bundle.trajectory.columns.splice(column, 1);
  bundle.trajectory.samples.forEach((row) => row.splice(column, 1));
  assert.throws(() => validateDataBundle(bundle), /trajectory\.json is incompatible: missing altitude_m column/);
});

test('non-monotonic simulation time is rejected', async () => {
  const bundle = await committedBundle();
  bundle.trajectory.samples[1][0] = bundle.trajectory.samples[0][0];
  assert.throws(() => validateDataBundle(bundle), /invalid or non-increasing time\/altitude/);
});

test('a missing export names the file and the recovery command', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 404 });
  try {
    await assert.rejects(loadAll(), /cannot load vehicle\.json \(404\).*export_flight_data\.py/);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('malformed JSON names the file and the recovery command', async () => {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => { throw new SyntaxError('unexpected token'); },
  });
  try {
    await assert.rejects(loadAll(), /vehicle\.json is not valid JSON.*export_flight_data\.py/);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('simulation source selects the first, middle, and final exported records exactly', async () => {
  const { trajectory } = await committedBundle();
  const source = simSource(trajectory);
  const columns = Object.fromEntries(trajectory.columns.map((key, index) => [key, index]));
  const indices = [0, Math.floor(trajectory.samples.length / 2), trajectory.samples.length - 1];

  for (const index of indices) {
    const row = trajectory.samples[index];
    const frame = source.sample(row[columns.t_s]);
    assert.equal(frame.t, row[columns.t_s]);
    assert.equal(frame.altitude, row[columns.altitude_m]);
    assert.equal(frame.velocity, row[columns.velocity_mps]);
    assert.equal(frame.acceleration, row[columns.accel_mps2]);
    assert.equal(frame.phase, trajectory.phases[trajectory.phase_index[index]].toUpperCase());
    for (const channel of source.channels) {
      assert.equal(frame.values[channel.key], row[columns[channel.key]], `${channel.key} at sample ${index}`);
    }
  }

  assert.deepEqual(source.channels.map(({ key, unit }) => [key, unit]), [
    ['altitude_m', 'm'], ['velocity_mps', 'm/s'], ['accel_mps2', 'm/s²'], ['mach', ''],
    ['q_Pa', 'Pa'], ['thrust_N', 'N'], ['drag_N', 'N'], ['cd', ''], ['mass_kg', 'kg'],
    ['cg_mm', 'mm'], ['static_margin_cal', 'cal'],
  ]);
});

test('simulation source interpolates numeric channels between records and clamps at the endpoints', async () => {
  const { trajectory } = await committedBundle();
  const source = simSource(trajectory);
  const columns = Object.fromEntries(trajectory.columns.map((key, index) => [key, index]));
  const index = Math.floor(trajectory.samples.length / 2);
  const before = trajectory.samples[index];
  const after = trajectory.samples[index + 1];
  const time = (before[columns.t_s] + after[columns.t_s]) / 2;
  const frame = source.sample(time);

  assert.equal(frame.t, time);
  for (const channel of source.channels) {
    const left = before[columns[channel.key]];
    const right = after[columns[channel.key]];
    const expected = left === null || right === null ? null : (left + right) / 2;
    if (expected === null) assert.equal(frame.values[channel.key], null, `${channel.key} midpoint`);
    else assert.ok(Math.abs(frame.values[channel.key] - expected) < 1e-10, `${channel.key} midpoint`);
  }
  assert.equal(frame.phase, trajectory.phases[trajectory.phase_index[index]].toUpperCase(),
    'phase is the lower/active record label, not interpolated');
  assert.equal(source.sample(-1).t, -1, 'sample reports the requested time while clamping its data');
  assert.equal(source.sample(-1).altitude, trajectory.samples[0][columns.altitude_m]);
  assert.equal(source.sample(source.duration + 1).altitude,
    trajectory.samples.at(-1)[columns.altitude_m]);
});

test('sensor replay source preserves source records and holds discrete telemetry between records', async () => {
  const { replay } = await committedBundle();
  const source = replaySource(replay);
  const indices = [0, Math.floor(replay.samples.length / 2), replay.samples.length - 1];

  for (const index of indices) {
    const row = replay.samples[index];
    const frame = source.sample(row.t);
    assert.equal(frame.t, row.t);
    assert.equal(frame.phase, row.state);
    assert.deepEqual(frame.health, row.health);
    for (const channel of source.channels) {
      const expected = channel.always_null ? null : (row[channel.key] ?? null);
      assert.equal(frame.values[channel.key], expected, `${channel.key} at sample ${index}`);
    }
  }

  const index = Math.floor(replay.samples.length / 2);
  const before = replay.samples[index];
  const after = replay.samples[index + 1];
  const frame = source.sample((before.t + after.t) / 2);
  assert.equal(frame.phase, before.state);
  assert.deepEqual(frame.health, before.health);
  assert.equal(frame.values.gps_fix, before.gps_fix, 'GNSS fix is categorical and held from the lower record');
  assert.equal(frame.values.gps_sats, before.gps_sats, 'satellite count is held from the lower record');
  assert.equal(frame.values.acceleration, null, 'replay has no acceleration estimate');
  assert.ok(Math.abs(frame.values.alt - (before.alt + after.alt) / 2) < 1e-10);
});
