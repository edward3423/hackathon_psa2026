import { expect, test } from '@playwright/test'

import { resetBackend, stageReadout } from './helpers'

/**
 * Recording rehearsal: the tour at recording speed. Unlike tour.spec.ts this
 * does not pass ?tour=fast, so the dwells are the ones the video will have.
 * Asserts the take lands close to the demo plan's 5:21 runtime. Takes five and
 * a half minutes, so it runs only when asked for:
 *
 *   CASCADE_REALSPEED_TOUR=1 npx playwright test specs/realspeed-tour.spec.ts
 */

test('real-speed take reaches the closing card on schedule', async ({ page }) => {
  test.skip(
    !process.env.CASCADE_REALSPEED_TOUR,
    'Five-and-a-half-minute rehearsal; set CASCADE_REALSPEED_TOUR=1 to run it.',
  )
  test.setTimeout(480_000)
  await resetBackend(page.request)

  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  const started = Date.now()
  await page.goto('/?tour=auto')

  await expect(page.locator('.benchmark-audit')).toContainText('BLIND AUDIT PASS', {
    timeout: 420_000,
  })
  await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 60_000 })
  await expect(page.getByRole('heading', { name: 'That is CASCADE' })).toBeVisible({
    timeout: 120_000,
  })

  const seconds = (Date.now() - started) / 1000
  console.log(`real-speed tour completed in ${seconds.toFixed(0)}s`)
  // The plan says 5:21; give slack for stream latency, none for a stall.
  expect(seconds).toBeGreaterThan(280)
  expect(seconds).toBeLessThan(420)

  expect(consoleErrors).toEqual([])
})
