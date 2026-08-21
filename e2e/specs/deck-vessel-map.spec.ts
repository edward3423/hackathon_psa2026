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
  await expect(map.getByLabel('3 built-in simulated ships and their routes')).toBeVisible()
  await expect(map.getByText(/AISSTREAM (LIVE|OFFLINE|CONNECTING)/)).toBeVisible()
  await expect(map.getByText(/MAPBOX (ACTIVE|LOADING)|LOCAL MAP FALLBACK/)).toBeVisible()
  await expect(map.locator('canvas')).toBeVisible()

  await page.getByRole('button', { name: 'Start demo replay' }).click()
  await resolveReeferDispute(page)
  await expect(page.getByRole('region', { name: 'Human approval' })).toBeVisible()
  await page.getByRole('button', { name: 'Restart' }).click()
  await expect(page.getByRole('button', { name: 'Next Event' })).toBeEnabled()
  await expect(map).toHaveAttribute('data-route-progress', '0.000')
  await page.getByRole('button', { name: 'Next Event' }).click()
  await expect(map).not.toHaveAttribute('data-route-progress', '0.000')
})

test('Mapbox mode renders every simulated ship as a native marker', async ({ page }) => {
  test.skip(
    !process.env.VITE_MAPBOX_ACCESS_TOKEN,
    'Mapbox mode needs a public test token; the local fallback is covered above.',
  )
  await page.route('https://api.mapbox.com/styles/v1/mapbox/dark-v11*', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ version: 8, sources: {}, layers: [] }),
    })
  })
  await page.route('https://events.mapbox.com/**', (route) => route.abort())

  await openDashboard(page)
  await navigateTo(page, 'Replay')

  const map = page.getByRole('region', { name: 'World vessel simulation' })
  await expect(map.getByText('MAPBOX ACTIVE')).toBeVisible()

  for (const ship of ['MV ATLAS STAR', 'MV PACIFIC LINK', 'MV BORNEO FEEDER']) {
    await expect(
      map.getByRole('button', { name: `${ship}, simulated optimized position` }),
    ).toBeVisible()
  }

  const atlas = map.getByRole('button', {
    name: 'MV ATLAS STAR, simulated optimized position',
  })
  await atlas.hover()
  await expect(map.getByRole('tooltip').filter({ hasText: 'Cape reroute to Singapore' })).toBeVisible()
})
