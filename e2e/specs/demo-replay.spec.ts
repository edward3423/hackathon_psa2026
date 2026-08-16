import { expect, test } from '@playwright/test'

import { openDashboard } from './helpers'

// PRD 9.20 honest Replay Mode: a previously captured valid run replays
// offline with a persistent, visible DEMO REPLAY label.
//
// test.fixme: awaits a UI control to start a DEMO_REPLAY run (the shell has
// no run-mode selector; POST /api/runs currently always creates LIVE_STUB)
// and the persistent DEMO REPLAY banner in the dashboard.

test.fixme('replay mode: persistent DEMO REPLAY label and offline completion', async ({ page }) => {
  // Block every non-local request to prove the replay works fully offline.
  await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => route.abort())

  await openDashboard(page)

  // Start a replay run from the UI (awaited capability: run-mode control).
  await page.getByRole('button', { name: /demo replay/i }).click()

  // The DEMO REPLAY label is visible immediately.
  const replayLabel = page.getByText('DEMO REPLAY', { exact: true }).first()
  await expect(replayLabel).toBeVisible({ timeout: 15_000 })

  // The label persists while replay events stream.
  await expect(page.locator('.trace-list li').first()).toBeVisible({ timeout: 30_000 })
  await expect(replayLabel).toBeVisible()

  // Replay preserves the normal approval interaction (PRD 9.20).
  await expect(page.getByText('AWAITING APPROVAL', { exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(replayLabel).toBeVisible()
  await page.getByRole('button', { name: /approve/i }).click()

  // The captured run completes offline and the label is still visible.
  await expect(page.getByText('COMPLETE', { exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(replayLabel).toBeVisible()
})
