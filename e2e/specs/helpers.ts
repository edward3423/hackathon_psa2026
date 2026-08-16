import { expect, type Page } from '@playwright/test'

/** Load the dashboard and wait for the scenario to render. */
export async function openDashboard(page: Page): Promise<void> {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'CASCADE' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'MV ATLAS STAR' })).toBeVisible()
}

/** Start a run from the UI using the primary action button. */
export async function startRun(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Start analysis' }).click()
}

/**
 * Assert that nothing dispatch-like is on screen. Used to prove that no
 * mocked work order, carrier notice, or receipt appears before approval.
 */
export async function expectNoDispatchArtifacts(page: Page): Promise<void> {
  await expect(page.getByText(/work order/i)).toHaveCount(0)
  await expect(page.getByText(/carrier notice/i)).toHaveCount(0)
  await expect(page.getByText(/receipt/i)).toHaveCount(0)
  await expect(page.getByText(/dispatched/i)).toHaveCount(0)
}
