import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {nodePolyfills} from 'vite-plugin-node-polyfills';

const ketcherRaphaelEsm = {
  name: 'ketcher-raphael-esm',
  transform(code:string,id:string) {
    if (!id.endsWith('/ketcher-core/dist/application/render/raphael-ext.modern.js')) return;
    return code.replace(
      "var raphaelModule = typeof window !== 'undefined' ? require('raphael') : undefined;",
      "import raphaelModule from 'raphael';",
    );
  },
};

export default defineConfig({
  // Browser adaptations for upstream Ketcher's Node utility imports, without forking Ketcher.
  plugins:[react(),nodePolyfills({include:['process','events','util','assert','buffer']}),ketcherRaphaelEsm],
  server:{host:'127.0.0.1',port:5173,strictPort:true,proxy:{'/api':{target:'http://127.0.0.1:8765',changeOrigin:false}}}
});
