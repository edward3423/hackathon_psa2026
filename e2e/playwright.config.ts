import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'

// The e2e project lives inside the repository but is intentionally not part of
// the npm workspace. Both web servers are launched from the repository root.
const repoRoot = path.resolve(__dirname, '..')

export default defineConfig({
  testDir: './specs',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 900 } },
    },
  ],
  webServer: [
    {
      command: 'uv --cache-dir .uv-cache run uvicorn cascade.api:app --port 8000',
      cwd: repoRoot,
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm --workspace frontend run dev',
      cwd: repoRoot,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
