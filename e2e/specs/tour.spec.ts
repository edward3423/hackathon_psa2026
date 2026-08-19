import { expect, test } from '@playwright/test'

import {
  approvePlan,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
  startRun,
} from './helpers'

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
  'The agents disagree',
  'Command Center',
  'The agent room',
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
    test.setTimeout(120_000)
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

  test('resets a completed run before showing the cold open', async ({ page }) => {
    await page.goto('/?tour=fast')
    await startRun(page)
    await resolveReeferDispute(page)
    await approvePlan(page, 'OPTIMIZED_HYBRID')
    await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 30_000 })

    await page.getByRole('button', { name: 'Start tour' }).click()
    const transport = page.getByRole('group', { name: 'Tour controls' })
    await expect(transport).toBeVisible()
    await transport.getByRole('button', { name: 'Pause tour' }).click()

    await expect(stageReadout(page)).toHaveText('READY')
    await expect(page.locator('.run-id')).toHaveText('NOT STARTED')
    await expect(page.getByText('Step 1 of 44')).toBeVisible()
  })

  test('keeps the sailing timeout notice inside the step 11 spotlight', async ({ page }) => {
    test.setTimeout(120_000)
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Start tour' }).click()

    const transport = page.getByRole('group', { name: 'Tour controls' })
    await expect(transport.getByText('Step 11 of 44')).toBeVisible({ timeout: 100_000 })
    const notice = page.locator('[data-tour="sailing-fallback"]')
    await expect(notice).toBeVisible({ timeout: 30_000 })
    await transport.getByRole('button', { name: 'Pause tour' }).click()
    await page.waitForTimeout(1_000)

    const spotlight = page.locator('.tour-spotlight')
    await expect(spotlight).toBeVisible()
    const [noticeBox, spotlightBox] = await Promise.all([notice.boundingBox(), spotlight.boundingBox()])
    expect(noticeBox).not.toBeNull()
    expect(spotlightBox).not.toBeNull()
    expect(noticeBox!.y).toBeGreaterThanOrEqual(0)
    expect(noticeBox!.y + noticeBox!.height).toBeLessThanOrEqual(1080)
    expect(noticeBox!.x).toBeGreaterThanOrEqual(spotlightBox!.x)
    expect(noticeBox!.x + noticeBox!.width).toBeLessThanOrEqual(
      spotlightBox!.x + spotlightBox!.width,
    )
  })
})
