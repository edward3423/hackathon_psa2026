import { expect, test } from '@playwright/test'

import { navigateTo, openDashboard, resetBackend } from './helpers'

// Act 2: the Red Sea 2024 blind replay. A cold run is dominated by
// calibration and takes roughly half a minute, so this spec gets its own
// generous budget rather than the suite default.
//
// What is checked is what the page has to be honest about: three arms drawn
// and named, the recorded arm labelled as a reconstruction, the blind audit
// reading PASS, the KPI tiles carrying real figures, and the benchmark's
// scope notice on screen rather than only in the payload.

const RUN_TIMEOUT = 120_000
const TEST_TIMEOUT = 240_000

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('crisis benchmark: three arms render, blind audit passes, KPI tiles populate', async ({
  page,
}) => {
  test.setTimeout(TEST_TIMEOUT)

  await openDashboard(page)
  await navigateTo(page, 'Crisis Benchmark')

  const heading = page.getByRole('heading', { name: /blind replay benchmark/i })
  await expect(heading).toBeVisible()

  // Nothing is claimed before a run: no tiles, no audit verdict.
  await expect(page.locator('.benchmark-arm-card')).toHaveCount(0)
  await expect(page.locator('.benchmark-audit')).toHaveCount(0)

  await page.getByRole('button', { name: 'Run benchmark' }).click()

  // The chart fills in as day ticks stream over SSE.
  const lines = page.locator('.benchmark-chart .recharts-line')
  await expect(lines).toHaveCount(3, { timeout: RUN_TIMEOUT })

  const legend = page.locator('.benchmark-chart .recharts-legend-wrapper')
  await expect(legend).toContainText('Recorded 2024 (reconstructed)')
  await expect(legend).toContainText('Reactive baseline')
  await expect(legend).toContainText('CASCADE agentic')

  // The completed result: one tile group per arm.
  const cards = page.locator('.benchmark-arm-card')
  await expect(cards).toHaveCount(3, { timeout: RUN_TIMEOUT })

  const historical = page.locator('.benchmark-arm-card[data-arm="HISTORICAL"]')
  await expect(historical).toContainText('RECONSTRUCTED')
  await expect(historical).toContainText(/reconstructed, not measured/i)

  for (const arm of ['REACTIVE_BASELINE', 'CASCADE_AGENTIC']) {
    await expect(page.locator(`.benchmark-arm-card[data-arm="${arm}"]`)).toContainText('SIMULATED')
  }

  // Every KPI tile carries a figure; none is blank or broken.
  const values = page.locator('.benchmark-arm-card .benchmark-kpis dd')
  await expect(values).toHaveCount(12)
  for (const text of await values.allInnerTexts()) {
    expect(text.trim()).not.toBe('')
    expect(text).not.toContain('NaN')
    expect(text).not.toContain('undefined')
  }
  await expect(page.locator('.benchmark-arm-card[data-arm="CASCADE_AGENTIC"]')).toContainText(
    /\d+\.\d{2} d/,
  )

  // The blind audit is the claim that no arm read a day it had not reached.
  const audit = page.locator('.benchmark-audit')
  await expect(audit).toBeVisible({ timeout: RUN_TIMEOUT })
  await expect(audit).toContainText('BLIND AUDIT PASS')
  await expect(audit).toContainText('0 violations')
  await expect(audit).toHaveClass(/is-pass/)
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await expect(audit).toBeInViewport()

  // The scope notice and the anchor readings have to reach the user.
  const scope = page.locator('.benchmark-scope-notice')
  await expect(scope).toBeVisible()
  await expect(scope).toContainText(/not a reproduction of history/i)
  await expect(scope.getByText('Methodology and limitations')).toBeVisible()
  await expect(scope.locator('details')).not.toHaveAttribute('open')

  const anchors = page.locator('.benchmark-anchors')
  await expect(anchors).toBeVisible()
  await expect(anchors).toContainText(/context, not a score/i)
  const readings = anchors.locator('.benchmark-anchor-reading')
  expect(await readings.count()).toBeGreaterThan(0)
  for (const text of await readings.allInnerTexts()) {
    expect(text.trim()).not.toBe('')
  }
})
