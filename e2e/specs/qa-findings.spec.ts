import { expect, test, type Page } from '@playwright/test'

import {
  approvePlan,
  navigateTo,
  openDashboard,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
  startRun,
} from './helpers'

/*
 * Regressions for a manual QA pass that the rest of the suite could not see.
 *
 * Each of these went unnoticed because the existing specs assert that a control
 * exists and responds, never that what it says agrees with the rest of the
 * product or is large enough to read. They are grouped here so the reason they
 * exist stays attached to them.
 */

/** The smallest rendered text anywhere on the page, in CSS pixels. */
async function smallestRenderedFontSize(page: Page): Promise<number> {
  return page.evaluate(() => {
    let smallest = Number.POSITIVE_INFINITY
    for (const element of document.body.querySelectorAll('*')) {
      const hasOwnText = [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
      )
      if (!hasOwnText) continue
      const rect = element.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) continue
      const style = getComputedStyle(element)
      if (style.visibility === 'hidden' || style.display === 'none') continue
      smallest = Math.min(smallest, Number.parseFloat(style.fontSize))
    }
    return smallest
  })
}

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('every agent reports COMPLETED once the run completes', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)
  await resolveReeferDispute(page)
  await approvePlan(page, 'OPTIMIZED_HYBRID')
  await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 30_000 })

  // The workflow said COMPLETE while the Coordinator card still said RUNNING:
  // the live event reducer had no case for RUN_COMPLETED, so whichever agent
  // was mid-step when the run ended stayed there forever.
  await navigateTo(page, 'Command Center')
  const statuses = page.locator('.agent-card .agent-status')
  await expect(statuses.first()).toBeVisible()
  const texts = await statuses.allTextContents()
  expect(texts.length).toBeGreaterThan(0)
  for (const status of texts) expect(status.trim()).toBe('COMPLETED')
})

test('the pre-run preview survives the run starting', async ({ page }) => {
  await openDashboard(page)

  // The panel used to promise hand-written figures that the engine then
  // replaced with its own, so the first thing a run did was contradict the
  // page it started from.
  // Everything the panel reports about the disruption itself. The workflow
  // stage next to them is meant to change; these are not.
  const figures = page.locator('.operations-overview__metric:not(:has-text("workflow stage"))')
  await expect(figures.first()).toBeVisible()
  const before = await figures.allInnerTexts()
  expect(before.length).toBeGreaterThan(3)

  await startRun(page)
  await resolveReeferDispute(page)
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })

  expect(await figures.allInnerTexts()).toEqual(before)
})

test('operational pages say they are the pre-recovery baseline', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)
  await resolveReeferDispute(page)
  await approvePlan(page, 'OPTIMIZED_HYBRID')
  await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 30_000 })

  // Recovery reports what the approved plan projects; Connections and Reefers
  // report what it is measured against. Both are right, and the product has to
  // say which is which or the two read as rival answers.
  await navigateTo(page, 'Connections')
  await expect(page.locator('.connections-page__source')).toContainText('PRE-RECOVERY BASELINE')
  await expect(page.locator('.connections-page__baseline-notice')).toContainText(
    /baseline, before recovery/i,
  )

  await navigateTo(page, 'Reefers')
  await expect(page.locator('.yard-cursor-context').last()).toContainText(
    /residual shortfall can remain/i,
  )

  await navigateTo(page, 'Recovery')
  await expect(page.locator('.deterministic-notice')).toContainText(/not expected to match/i)
})

test('the connections table paginates instead of running thousands of pixels long', async ({
  page,
}) => {
  await openDashboard(page)
  await startRun(page)
  await resolveReeferDispute(page)
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })
  await navigateTo(page, 'Connections')

  const rows = page.locator('.connections-table tbody tr')
  await expect(rows).toHaveCount(50)

  const pager = page.getByRole('navigation', { name: 'Connection table pages' })
  await expect(pager.getByRole('button', { name: 'Previous' })).toBeDisabled()
  const firstContainer = await rows.first().innerText()
  await pager.getByRole('button', { name: 'Next' }).click()
  expect(await rows.first().innerText()).not.toBe(firstContainer)

  // A page of rows fits in a few screens rather than the 13,000px the whole
  // set occupied.
  const height = await page.locator('.connections-page').evaluate((node) => node.scrollHeight)
  expect(height).toBeLessThan(4_000)

  await page.getByLabel('Rows per page').selectOption('250')
  await expect(rows).toHaveCount(250)
  await expect(pager.getByRole('button', { name: 'Previous' })).toBeDisabled()
})

test('the approval bar reserves its own space instead of covering the workspace', async ({
  page,
}) => {
  await openDashboard(page)
  await startRun(page)
  await resolveReeferDispute(page)
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })

  const bar = page.getByRole('region', { name: 'Human approval' })
  await expect(bar).toBeVisible()
  const barBox = await bar.boundingBox()
  expect(barBox).not.toBeNull()

  // The forecast timeline sticks to the bottom of the viewport, which is
  // exactly where the fixed approval bar sits. It has to come to rest above it.
  const timeline = page.locator('.operations-timeline')
  await expect(timeline).toBeVisible()
  const timelineBox = await timeline.boundingBox()
  expect(timelineBox).not.toBeNull()
  expect(timelineBox!.y + timelineBox!.height).toBeLessThanOrEqual(barBox!.y + 1)

  // Scrolled to the very bottom, the last of the workspace is still clear of
  // the bar: the reserved space is real padding under the content, not a gap
  // the content is free to scroll into.
  await page.mouse.wheel(0, 20_000)
  await page.waitForTimeout(200)
  const lastContentEdge = await page.locator('.app-content').evaluate((node) => {
    const padding = Number.parseFloat(getComputedStyle(node).paddingBottom)
    return node.getBoundingClientRect().bottom - padding
  })
  expect(lastContentEdge).toBeLessThanOrEqual(barBox!.y + 1)
})

for (const pageName of ['Command Center', 'Connections', 'Replay']) {
  test(`${pageName} renders no text below the 12px floor`, async ({ page }) => {
    await openDashboard(page)
    await startRun(page)
    await resolveReeferDispute(page)
    await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })
    if (pageName !== 'Command Center') await navigateTo(page, pageName)

    expect(await smallestRenderedFontSize(page)).toBeGreaterThanOrEqual(12)
  })
}
