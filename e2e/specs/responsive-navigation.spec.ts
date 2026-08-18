import { expect, test } from '@playwright/test'

import { openDashboard, resetBackend } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('narrow viewport keeps navigation usable and contains the connections table', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openDashboard(page)

  await page.getByRole('button', { name: 'Open navigation' }).click()
  const navigation = page.getByRole('navigation', { name: 'CASCADE sections' })
  await expect(navigation).toBeVisible()
  await navigation.getByRole('button', { name: 'Connections', exact: true }).click()

  await expect(page.getByRole('button', { name: 'Close navigation' })).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: 'Threatened transshipment connections' }),
  ).toBeVisible()

  const tableRegion = page.getByRole('region', { name: 'Threatened connection table' })
  await expect(tableRegion).toBeVisible()
  await expect
    .poll(() => tableRegion.evaluate((element) => getComputedStyle(element).overflowX))
    .toMatch(/auto|scroll/)

  const bounds = await tableRegion.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(391)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(
    true,
  )
})
