import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    target: 'es2022',
    // El chunk de Rapier compat incluye ~4 MB de WASM base64. Se carga separado
    // del menú, una sola vez y localmente; el umbral contempla ese binario.
    chunkSizeWarningLimit: 5000,
  },
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
});
