import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // The backend (ARCHITECTURE.md Section 9/10) runs standalone on 8000
    // with no CORS middleware; proxying /api in dev keeps requests
    // same-origin so the browser never needs a CORS exception.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
