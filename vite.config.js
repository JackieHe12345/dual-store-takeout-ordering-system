import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'node:path';

export default defineConfig(({ mode }) => {
  if (!['customer', 'staff', 'admin'].includes(mode)) throw new Error('Select a frontend mode');
  return {
    root: resolve(`frontend-${mode}`),
    base: './',
    plugins: [vue()],
    build: { outDir: resolve(`nginx/html/${mode}`), emptyOutDir: true },
  };
});
