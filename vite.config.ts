import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Production base `/gsm/` — для публикации на https://предрейс.рф/gsm
// Локально (`npm run dev`) base остаётся `/`.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/gsm/' : '/',
  server: {
    host: '127.0.0.1',
    port: 5173,
    open: true,
  },
}));
