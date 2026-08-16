import { expect, test } from '@playwright/test'

import { openDashboard, startRun } from './helpers'

// This spec passes against the current stub backend. It proves that the
// Playwright harness (webServer startup, SSE streaming, UI selectors) works
// end to end before the full workflow lands.

test('stub run streams trace events to the dashboard and reaches stream end', async ({ page }) => {
  await openDashboard(page)

  // Before the run: empty trace and idle stream indicator.
  await expect(page.getByText('Start analysis to stream agent decisions and tool results.')).toBeVisible()
  await expect(page.getByText('IDLE', { exact: true })).toBeVisible()

  await startRun(page)

  // Trace events render as the stub stream arrives (the fixture has 7 events).
  const traceItems = page.locator('.trace-list li')
  await expect(traceItems).toHaveCount(7, { timeout: 20_000 })
  await expect(page.getByText('7 events')).toBeVisible()

  // The first event comes from the coordinator starting the run.
  await expect(traceItems.first()).toContainText('Coordinator Agent')
  await expect(traceItems.first()).toContainText('RUN STARTED')

  // Stream end state: indicator back to IDLE, start button re-enabled,
  // and the workflow stage reflects the final stub event.
  await expect(page.getByText('IDLE', { exact: true })).toBeVisible({ timeout: 20_000 })
  await expect(page.getByRole('button', { name: 'Start analysis' })).toBeEnabled()
  await expect(page.getByText('AWAITING APPROVAL', { exact: true })).toBeVisible()

  // Agent cards left the WAITING state for every agent that produced events.
  await expect(page.locator('.agent-card', { hasText: 'Impact Agent' })).toContainText('COMPLETE')
  await expect(page.locator('.agent-card', { hasText: 'Yard Agent' })).toContainText('COMPLETE')
})

test('reset returns the dashboard to the original scenario state', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)

  await expect(page.locator('.trace-list li')).toHaveCount(7, { timeout: 20_000 })

  await page.getByRole('button', { name: 'Reset' }).click()

  await expect(page.getByText('Start analysis to stream agent decisions and tool results.')).toBeVisible()
  await expect(page.getByText('0 events')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start analysis' })).toBeEnabled()
})
