import { expect, type Page, type APIRequestContext } from '@playwright/test'

export const REEFER_CONSTRAINT = 'Respect physical reefer plug capacity'

/** Clear any dangling paused runs from earlier tests. */
export async function resetBackend(request: APIRequestContext): Promise<void> {
  await request.post('http://127.0.0.1:8620/api/reset')
}

/** Load the dashboard and wait for the scenario to render. */
export async function openDashboard(page: Page): Promise<void> {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'CASCADE' })).toBeVisible()
  await expect(page.locator('.alert-vessel')).toHaveText('MV ATLAS STAR')
}

/** Start a live-stub run from the UI using the primary action button. */
export async function startRun(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Start run' }).click()
}

/** Move between the persistent mission-control workspaces. */
export async function navigateTo(page: Page, label: string): Promise<void> {
  const navigation = page.getByRole('navigation', { name: 'CASCADE sections' })
  const destination = navigation.getByRole('button', { name: label, exact: true })
  await destination.click()
  await expect(destination).toHaveAttribute('aria-current', 'page')
}

/** The workflow-stage readout in the top bar (scoped: the stage track repeats stage names). */
export function stageReadout(page: Page) {
  return page.locator('.run-state strong')
}

/**
 * Resolve the golden reefer-capacity dispute: wait for the dialog, confirm
 * the reefer plug capacity constraint, and wait for the dialog to close.
 */
export async function resolveReeferDispute(page: Page): Promise<void> {
  const dialog = page.getByRole('dialog', { name: /dispute/i })
  await expect(dialog).toBeVisible({ timeout: 30_000 })
  await expect(dialog).toContainText('Impact Agent')
  await expect(dialog).toContainText('Yard Agent')
  await expect(dialog).toContainText(/reefer/i)
  await dialog.getByRole('button', { name: REEFER_CONSTRAINT }).click()
  await dialog.getByRole('button', { name: 'Confirm constraint' }).click()
  await expect(dialog).toBeHidden({ timeout: 15_000 })
}

/**
 * Wait for the approval bar, pick the given plan, and approve it.
 */
export async function approvePlan(page: Page, archetype: string): Promise<void> {
  const approvalBar = page.getByRole('region', { name: 'Human approval' })
  await expect(approvalBar).toBeVisible({ timeout: 30_000 })
  await approvalBar.getByLabel('Plan').selectOption(archetype)
  await approvalBar.getByRole('button', { name: 'Approve' }).click()

  const confirmation = page.getByRole('dialog', { name: 'Confirm simulated execution' })
  await expect(confirmation).toBeVisible()
  await expect(confirmation).toContainText(/simulation only/i)
  await confirmation.getByRole('button', { name: 'Confirm simulated execution' }).click()
  await expect(confirmation).toBeHidden({ timeout: 15_000 })
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
