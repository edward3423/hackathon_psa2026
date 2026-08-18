import { expect, test } from '@playwright/test'

import { openDashboard, resetBackend } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('desktop header scrolls away instead of covering workspace content', async ({ page }) => {
  await page.setViewportSize({ width: 1600, height: 900 })
  await openDashboard(page)

  const header = page.locator('.top-bar')
  const workspace = page.locator('#main-content')

  await expect(header).toBeInViewport()
  await workspace.evaluate((element) =>
    element.insertAdjacentHTML(
      'beforeend',
      '<div data-scroll-test-spacer aria-hidden="true" style="height: 1200px"></div>',
    ),
  )

  await page.evaluate(() => window.scrollTo({ top: 700, behavior: 'instant' }))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(500)

  const headerBounds = await header.boundingBox()
  expect(headerBounds).not.toBeNull()
  expect(headerBounds!.y + headerBounds!.height).toBeLessThanOrEqual(0)
})
