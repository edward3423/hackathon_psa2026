import { expect, test } from '@playwright/test'

import { resetBackend, stageReadout } from './helpers'

/**
 * The guided tour, played end to end against the live backend.
 *
 * This is the spec that proves the tour actually drives the product: it never
 * touches an app control itself, only the Start tour button, and then asserts
 * that the run reaches COMPLETE, the benchmark reaches BLIND AUDIT PASS, and
 * the closing card renders. Anything the tour fails to click shows up here as a
 * chapter that never arrives.
 *
 * `?tour=fast` scales every reading dwell by 0.05. Clicks, conditions and
 * timeouts are unchanged, so this exercises the same code path a recording does
 * in about a twentieth of the wall-clock.
 */

const CHAPTERS = [
  'Cold open',
  'Command Center',
  'The agents disagree',
  'Three plans, one decision',
  'Nothing moves without approval',
  'Act 2: the blind benchmark',
  'What we are not claiming',
]

test.describe('guided tour', () => {
  test.beforeEach(async ({ request }) => {
    await resetBackend(request)
  })

  test('plays every chapter and drives the product to the end', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push(message.text())
    })
    page.on('pageerror', (error) => consoleErrors.push(error.message))

    await page.goto('/?tour=fast')
    await expect(page.getByRole('heading', { name: 'CASCADE' })).toBeVisible()

    await page.getByRole('button', { name: 'Start tour' }).click()

    const transport = page.getByRole('group', { name: 'Tour controls' })
    await expect(transport).toBeVisible()

    for (const [index, title] of CHAPTERS.entries()) {
      await expect(transport.getByText(`${index + 1}. ${title}`)).toBeVisible({ timeout: 90_000 })

      // Asserted while the chapter is on screen. The closing chapter navigates
      // to System, and the benchmark page goes with it.
      if (title === 'Act 2: the blind benchmark') {
        await expect(page.locator('.benchmark-audit')).toContainText('BLIND AUDIT PASS', {
          timeout: 90_000,
        })
      }
    }

    // The tour resolved the dispute and approved a plan through the real
    // controls, so Act 1 has to have finished. The top bar keeps the readout
    // for the rest of the play.
    await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 90_000 })

    await expect(page.getByRole('heading', { name: 'That is CASCADE' })).toBeVisible({
      timeout: 90_000,
    })

    expect(consoleErrors).toEqual([])
  })

  test('says why it cannot play when the backend is unreachable', async ({ page }) => {
    // Every figure the tour shows is computed by the API, so with the API down
    // the honest behaviour is to explain the gap rather than play a hollow tour.
    // Matched on the pathname, not a glob: the frontend's own modules are served
    // from /src/api/ in dev and a glob would blank the page instead of the API.
    await page.route(
      (url) => url.pathname.startsWith('/api/'),
      (route) => route.abort(),
    )
    await page.goto('/')

    const launch = page.getByRole('button', { name: 'Start tour' })
    await expect(launch).toHaveClass(/is-unavailable/)
    await launch.click()

    await expect(page.getByRole('heading', { name: 'The tour needs the backend' })).toBeVisible()
    await expect(page.getByText(/port 8620/)).toBeVisible()
  })

  test('pauses, steps and exits on the transport controls', async ({ page }) => {
    await page.goto('/?tour=fast')
    await page.getByRole('button', { name: 'Start tour' }).click()

    const transport = page.getByRole('group', { name: 'Tour controls' })
    await transport.getByRole('button', { name: 'Pause tour' }).click()
    await expect(transport.getByRole('button', { name: 'Resume tour' })).toBeVisible()

    const progress = transport.getByRole('progressbar')
    const before = await progress.getAttribute('aria-valuenow')
    await transport.getByRole('button', { name: 'Skip to the next step' }).click()
    await transport.getByRole('button', { name: 'Pause tour' }).click()
    expect(Number(await progress.getAttribute('aria-valuenow'))).toBeGreaterThan(Number(before))

    await transport.getByRole('button', { name: 'Exit tour' }).click()
    await expect(transport).toBeHidden()
    // Exiting leaves the app usable, not stuck behind a scrim.
    await expect(page.locator('.tour-spotlight')).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Start tour' })).toBeVisible()
  })
})
