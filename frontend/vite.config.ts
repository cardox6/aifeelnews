import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  server: {
    // Pin the dev server to 5173 and fail loudly if it's taken, instead of
    // silently drifting to 5174/5175. The backend CORS allowlist only includes
    // :5173 (app/main.py), so a drifted port would break every API call with an
    // opaque CORS error. strictPort surfaces the conflict immediately.
    port: 5173,
    strictPort: true,
  },
})
