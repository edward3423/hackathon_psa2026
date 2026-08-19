import { expect, test } from '@playwright/test'

import { navigateTo, openDashboard, resetBackend, resolveReeferDispute } from './helpers'

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('Deck.gl vessel map replays routes and reports AISStream state', async ({ page }) => {
  await openDashboard(page)
  await navigateTo(page, 'Replay')

  const map = page.getByRole('region', { name: 'World vessel simulation' })
  await expect(map).toBeVisible()
  await expect(map.getByText('DECK.GL SIMULATION')).toBeVisible()
  await expect(map.getByText(/AISSTREAM (LIVE|OFFLINE|CONNECTING)/)).toBeVisible()
  await expect(map.locator('canvas')).toBeVisible()

  await page.getByRole('button', { name: 'Start demo replay' }).click()
  await resolveReeferDispute(page)
  await expect(page.getByRole('button', { name: 'Next Event' })).toBeEnabled()
  await expect(map).toHaveAttribute('data-route-progress', '0.000')
  await page.getByRole('button', { name: 'Next Event' }).click()
  await expect(map).not.toHaveAttribute('data-route-progress', '0.000')
})
