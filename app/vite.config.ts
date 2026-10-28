import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {nodePolyfills} from 'vite-plugin-node-polyfills';
import pkg from './package.json';

// Upstream Ketcher (ketcher-core) requires `raphael` with CommonJS; rewrite that one line so the
// browser bundle can import it as ESM. Same adaptation as the previous interface, no fork.
const ketcherRaphaelEsm = {
  name: 'ketcher-raphael-esm',
  transform(code: string, id: string) {
    if (!id.endsWith('/ketcher-core/dist/application/render/raphael-ext.modern.js')) return;
    return code.replace(
      "var raphaelModule = typeof window !== 'undefined' ? require('raphael') : undefined;",
      "import raphaelModule from 'raphael';",
    );
  },
};

// The Tauri shell loads this at dev time from devUrl; `cargo tauri build` bundles ../dist.
export default defineConfig({
  plugins: [react(), nodePolyfills({include: ['process', 'events', 'util', 'assert', 'buffer']}), ketcherRaphaelEsm],
  clearScreen: false,
  define: {__APP_VERSION__: JSON.stringify(pkg.version)},
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    fs: {allow: ['..']}, // design/tokens.css lives one level up
  },
  envPrefix: ['VITE_', 'TAURI_ENV_'],
  build: {target: 'es2022', sourcemap: false, chunkSizeWarningLimit: 4000},
});
