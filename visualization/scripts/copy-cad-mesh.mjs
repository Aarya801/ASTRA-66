/**
 * Copies the exported OpenSCAD assembly mesh from the ASTRA-66 CAD exports into the site's
 * public/ directory at build time.
 *
 * The mesh already exists in the repository (cad/exports/assembly/), so it is not duplicated
 * in git; this step makes it available to the production build - locally and on Vercel alike.
 * If the mesh is missing the build still succeeds and the site simply hides the CAD MESH
 * button (public/models/assembly_meta.json is committed, and the front end handles a failed
 * fetch by hiding the control).
 */
import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const vis = resolve(here, '..');
const repo = resolve(vis, '..');

const NAME = 'astra66_assembly_flight_parts.stl';
const src = resolve(repo, 'cad', 'exports', 'assembly', NAME);
const outDir = resolve(vis, 'public', 'models');
const dst = resolve(outDir, NAME);

if (!existsSync(src)) {
  console.warn(`[astra66] CAD mesh not found at cad/exports/assembly/${NAME} - building without it.`);
  process.exit(0);
}

mkdirSync(outDir, { recursive: true });

if (existsSync(dst) && statSync(dst).size === statSync(src).size) {
  console.log(`[astra66] CAD mesh already present (${(statSync(dst).size / 1048576).toFixed(1)} MB).`);
  process.exit(0);
}

copyFileSync(src, dst);
console.log(`[astra66] copied CAD mesh (${(statSync(dst).size / 1048576).toFixed(1)} MB) into public/models/.`);
