import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { loadAll, validateDataBundle } from '../src/data.js';

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
