import { expect, test } from '@playwright/test'

import {
  openDashboard,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
  startRun,
} from './helpers'

// Harness smoke tests against the real LIVE_STUB workflow: a run starts from
// the UI, trace events render, the workflow pauses at the reefer dispute
// (instead of streaming to the end unattended), and reset restores the shell.
//
// The dispute overlay is modal over the main content, but the top-bar
// controls (Reset in particular) stay above the backdrop so the presenter
// is never stranded mid-dispute (PRD 9.16).

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('stub run streams trace events and pauses at the dispute', async ({ page }) => {
  await openDashboard(page)

  // Before the run: idle indicator and no recorded events.
  await expect(page.getByText('IDLE', { exact: true })).toBeVisible()
  await expect(page.getByText('0 events')).toBeVisible()

  // Expand the trace drawer up front; the modal dispute overlay would block
  // the toggle once the workflow pauses.
  await page.getByRole('button', { name: /execution trace/i }).click()

  await startRun(page)

  // Trace events arrive over SSE and render in the open drawer.
  const rows = page.locator('.trace-list li')
  await expect(rows.first()).toBeVisible({ timeout: 20_000 })
  await expect(rows.first()).toContainText('Coordinator Agent')
  await expect(rows.first()).toContainText('RUN STARTED')
  await expect(page.getByText('STREAMING', { exact: true })).toBeVisible()

  // The run pauses at the reefer dispute and waits for the human.
  await expect(page.getByRole('dialog', { name: /dispute/i })).toBeVisible({ timeout: 30_000 })
  await expect(stageReadout(page)).toHaveText('DISPUTE')
  expect(await rows.count()).toBeGreaterThanOrEqual(2)
})

test('reset returns the dashboard to the original scenario state', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)

  // Reach the dispute pause, resolve it, then reset mid-run during planning.
  await resolveReeferDispute(page)
  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.getByRole('dialog', { name: /dispute/i })).toBeHidden()
  await expect(page.getByText('0 events')).toBeVisible()
  await expect(page.getByText('IDLE', { exact: true })).toBeVisible()
  await expect(stageReadout(page)).toHaveText('READY')
  await expect(page.getByRole('button', { name: 'Start run' })).toBeEnabled()
})

test('reset works while the dispute overlay is open', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)

  // The workflow pauses at the dispute; the overlay must not intercept the
  // top-bar Reset (Playwright's actionability check fails on an obscured
  // button, so this genuinely proves the backdrop does not cover it).
  await expect(page.getByRole('dialog', { name: /dispute/i })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.getByRole('dialog', { name: /dispute/i })).toBeHidden()
  await expect(stageReadout(page)).toHaveText('READY')
  await expect(page.getByText('IDLE', { exact: true })).toBeVisible()
})
