import { expect, test } from '@playwright/test'

import { navigateTo, openDashboard, resetBackend, resolveReeferDispute } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('replay map animates planned ships and identifies the traffic source', async ({ page }) => {
  await openDashboard(page)
  await navigateTo(page, 'Replay')
  await page.getByRole('button', { name: 'Start demo replay' }).click()

  const map = page.getByRole('region', { name: 'World vessel map' })
  await expect(map).toBeVisible()
  await expect(map.getByText('SIMULATED ROUTES')).toBeVisible()
  await expect(map.getByText(/Live AIS unavailable|LIVE AIS/)).toBeVisible()
  await resolveReeferDispute(page)

  const plannedShip = map.locator('[data-replay-vessel]').first()
  await expect(plannedShip).toBeVisible()
  await expect(page.getByRole('button', { name: 'Previous Event' })).toBeEnabled({ timeout: 15_000 })
  await page.getByRole('button', { name: 'Restart' }).click()
  await expect(page.getByRole('button', { name: 'Next Event' })).toBeEnabled()
  const startPosition = await plannedShip.getAttribute('transform')

  await page.getByRole('button', { name: 'Next Event' }).click()
  await expect(plannedShip).not.toHaveAttribute('transform', startPosition ?? '')

  await plannedShip.hover()
  await expect(map.getByRole('tooltip')).toContainText(/Planned position/)
  await expect(map.getByRole('tooltip')).toContainText(/kn/)
})
