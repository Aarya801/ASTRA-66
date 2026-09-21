import { defineConfig } from 'vite';

// ASTRA-66 visualiser build configuration.
// base './' keeps the production build portable (it can be opened from any sub-path or served
// from a static host without rewriting asset URLs).
export default defineConfig({
  base: './',
  server: { open: false, port: 5173 },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    chunkSizeWarningLimit: 900,
    sourcemap: false,
  },
});
