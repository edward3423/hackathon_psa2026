import { expect, test } from '@playwright/test'

import { openDashboard, startRun } from './helpers'

// PRD 9.12 controlled failure path: alternative-sailing lookup timeout,
// labeled cached fallback, MEDIUM confidence, approval still required.
//
// test.fixme: awaits the full workflow backend (find_alternative_sailings
// timeout branch with cached fixture fallback and confidence downgrade) and
// the dashboard elements that surface the timeout error, the cached-data
// label, and the approval bar. The stub backend ignores the failure toggle.

test.fixme('timeout path: visible error, labeled cached fallback, MEDIUM confidence, approval required', async ({ page }) => {
  await openDashboard(page)

  // Enable the controlled failure (checkbox defaults on; assert then keep on).
  const failureToggle = page.getByRole('checkbox', { name: /sailing lookup timeout/i })
  await failureToggle.check()
  await expect(failureToggle).toBeChecked()

  await startRun(page)

  // Resolve the dispute so the workflow reaches the sailing lookup stage.
  const disputePanel = page.getByRole('dialog', { name: /dispute/i })
  await expect(disputePanel).toBeVisible({ timeout: 60_000 })
  await disputePanel.getByRole('button', { name: /reefer plug capacity/i }).click()

  // The timeout is reported as a visible error in the trace (PRD 9.12).
  await expect(page.getByText(/timeout|timed out/i).first()).toBeVisible({ timeout: 60_000 })
  const errorEntry = page.locator('.trace-list li', { hasText: /find_alternative_sailings/i })
  await expect(errorEntry.first()).toContainText(/timeout|timed out|error/i)

  // The fallback data is explicitly labeled as cached and possibly stale.
  await expect(page.getByText(/cached/i).first()).toBeVisible()
  await expect(page.getByText(/stale/i).first()).toBeVisible()

  // Confidence drops to MEDIUM because cached sailing data was used.
  await expect(page.getByText('MEDIUM', { exact: true }).first()).toBeVisible()

  // The workflow still reaches the approval gate and cannot auto-dispatch.
  await expect(page.getByText('AWAITING APPROVAL', { exact: true })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: /approve/i })).toBeVisible()
  await expect(page.getByText(/receipt/i)).toHaveCount(0)
})
