import { defineConfig } from 'electron-vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  main: {
    build: {
      sourcemap: true,
    },
  },
  preload: {
    build: {
      sourcemap: true,
    },
  },
  renderer: {
    plugins: [react()],
    build: {
      sourcemap: true,
    },
  },
});
