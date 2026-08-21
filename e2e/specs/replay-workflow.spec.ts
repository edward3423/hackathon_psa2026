import { expect, test } from '@playwright/test'

import { navigateTo, openDashboard, resetBackend, startRun } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('starting a run preserves the selected workspace', async ({ page }) => {
  await openDashboard(page)
  await navigateTo(page, 'Agents')

  await startRun(page)

  const navigation = page.getByRole('navigation', { name: 'CASCADE sections' })
  await expect(navigation.getByRole('button', { name: 'Agents', exact: true })).toHaveAttribute(
    'aria-current',
    'page',
  )
})

test('a selected scenario can be followed as a live replay', async ({ page }) => {
  await openDashboard(page)
  await page.getByLabel('Scenario', { exact: true }).selectOption('moderate-delay')

  await startRun(page)
  await navigateTo(page, 'Replay')

  await expect(page.getByRole('heading', { name: 'Moderate Delay replay' })).toBeVisible()
  await expect(page.getByRole('status', { name: 'Replay mode' })).toContainText('Following live')
  await expect(page.getByRole('button', { name: 'Pause live follow' })).toBeVisible()
})
