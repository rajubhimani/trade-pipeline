import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build output goes into ../src/trade_pipeline/api/static so FastAPI can
// serve it directly (see api/main.py) — one origin, no CORS handling needed
// for the dashboard's own fetch() calls in production.
//
// The dev-server proxy forwards API paths to the real FastAPI server
// (assumed running on :8000 via `uv run uvicorn ...`) so `fetch('/trades')`
// works identically in `npm run dev` and in the built/served app — no
// environment-specific base URL branching in the app code.
export default defineConfig({
  plugins: [react()],
  // Served by FastAPI under /dashboard (see api/main.py) — base must match
  // so built asset references (/dashboard/assets/...) resolve correctly
  // once mounted there, instead of the default root-absolute (/assets/...).
  base: '/dashboard/',
  build: {
    outDir: '../src/trade_pipeline/api/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/trades': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
    },
  },
})
