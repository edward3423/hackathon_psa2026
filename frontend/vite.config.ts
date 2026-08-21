import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  build: {
    // Mapbox is an optional lazy chunk loaded only when a token is configured.
    chunkSizeWarningLimit: 2_000,
  },
  server: {
    host: '127.0.0.1',
    port: 5620,
    proxy: {
      '/api': 'http://127.0.0.1:8620',
    },
  },
})
