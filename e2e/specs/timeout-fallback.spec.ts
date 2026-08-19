import { expect, test } from '@playwright/test'

import {
  navigateTo,
  openDashboard,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
  startRun,
} from './helpers'

// PRD 9.12 controlled failure path: alternative-sailing lookup timeout,
// labeled cached fallback, MEDIUM confidence, approval still required.

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('timeout path: visible error, labeled cached fallback, MEDIUM confidence, approval required', async ({ page }) => {
  await openDashboard(page)
  await navigateTo(page, 'Recovery')

  // Enable the controlled failure (defaults on; assert then keep on).
  const failureToggle = page.getByRole('checkbox', { name: /sailing lookup timeout/i })
  await failureToggle.check()
  await expect(failureToggle).toBeChecked()

  await startRun(page)

  // Resolve the dispute so the workflow reaches the sailing lookup stage.
  await resolveReeferDispute(page)

  // The timeout is surfaced as a labeled cached-fallback callout (PRD 9.12).
  const fallback = page.locator('.sailing-fallback-notice')
  await expect(fallback).toBeVisible({ timeout: 30_000 })
  await expect(fallback).toContainText('Sailing lookup timed out')
  await expect(fallback).toContainText('Cached sailing data was used')
  await expect(fallback).toContainText(/timed out/i)
  await expect(fallback).toContainText(/stale/i)
  await expect(fallback).toContainText(/medium confidence/i)

  // The trace records the tool error itself, not just the summary callout.
  await navigateTo(page, 'Agents')
  await page.getByRole('button', { name: /execution trace/i }).click()
  const errorRow = page.locator('.trace-list li', { hasText: 'find_alternative_sailings' })
  await expect(errorRow.first()).toContainText(/timed out/i)

  // The workflow still reaches the approval gate and cannot auto-dispatch.
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })
  await expect(page.getByRole('region', { name: 'Human approval' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve' })).toBeVisible()
  await expect(page.getByText('EXECUTION RECEIPTS (MOCKED)')).toHaveCount(0)
})
