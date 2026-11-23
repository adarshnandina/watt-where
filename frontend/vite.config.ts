import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The browser talks only to Vite (:5173). Vite forwards /api/* to Django (:8000),
// so there is no CORS to configure and no API key or backend URL in the frontend code.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
