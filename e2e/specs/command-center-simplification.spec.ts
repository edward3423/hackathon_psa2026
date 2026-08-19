import { expect, test } from '@playwright/test'

import { openDashboard, resetBackend } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('command center uses a quiet port map with hover vessel details', async ({ page }) => {
  await openDashboard(page)

  const navigation = page.getByRole('navigation', { name: 'CASCADE sections' })
  await expect(navigation.getByRole('button', { name: 'System' })).toHaveCount(0)

  const vessel = page.getByRole('button', { name: /MV ATLAS STAR/ })
  const bounds = await vessel.boundingBox()
  expect(bounds).not.toBeNull()
  expect(Math.abs((bounds?.width ?? 0) - (bounds?.height ?? 0))).toBeLessThanOrEqual(2)

  await vessel.hover()
  const details = page.getByRole('tooltip').filter({ hasText: 'MV ATLAS STAR' })
  await expect(details).toBeVisible()
  await expect(details).toContainText('T1 B06')
  await expect(details).toContainText('1,284 containers')

  await expect(page.locator('.operations-overview__storage-building')).toHaveCount(5)
})

test('any selected scenario can be watched as a live replay', async ({ page }) => {
  await openDashboard(page)

  await page.getByLabel('Scenario', { exact: true }).selectOption('moderate-delay')
  await page.getByRole('button', { name: 'Start run' }).click()
  await page.getByRole('navigation', { name: 'CASCADE sections' })
    .getByRole('button', { name: 'Replay' })
    .click()

  await expect(page.getByRole('heading', { name: 'Moderate Delay replay' })).toBeVisible()
  await expect(page.getByRole('status', { name: 'Replay mode' })).toContainText('Following live')
  await expect(page.getByRole('button', { name: 'Pause live follow' })).toBeVisible()
})
