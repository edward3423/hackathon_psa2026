import { expect, test } from '@playwright/test'

import {
  approvePlan,
  openDashboard,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
} from './helpers'

// PRD 9.20 honest Replay Mode: a previously captured valid run replays
// offline with a persistent, visible DEMO REPLAY label and the normal
// approval interaction preserved.

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('replay mode: persistent DEMO REPLAY label and offline completion', async ({ page }) => {
  // Block every non-local request to prove the replay works fully offline.
  await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => route.abort())

  await openDashboard(page)

  await page.getByRole('button', { name: 'Start demo replay' }).click()

  // The DEMO REPLAY label is visible immediately and stays visible.
  const replayLabel = page.locator('.replay-badge')
  await expect(replayLabel).toBeVisible({ timeout: 15_000 })
  await expect(replayLabel).toHaveText('DEMO REPLAY')

  // The replay preserves the dispute interaction.
  await resolveReeferDispute(page)
  await expect(replayLabel).toBeVisible()

  // The replay preserves the normal approval interaction (PRD 9.20).
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })
  await expect(replayLabel).toBeVisible()
  await approvePlan(page, 'OPTIMIZED_HYBRID')

  // The captured run completes offline and the label is still visible.
  await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 30_000 })
  await expect(page.getByText('EXECUTION RECEIPTS (MOCKED)')).toBeVisible()
  await expect(replayLabel).toBeVisible()
})
