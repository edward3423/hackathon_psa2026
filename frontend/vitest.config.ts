import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    // The App specs mount every lazy page chunk. That is comfortably under a
    // second alone, but the 5s default times out when the suites run together
    // on a loaded machine, which shows up as a flake rather than a real fault.
    testTimeout: 20_000,
  },
})
