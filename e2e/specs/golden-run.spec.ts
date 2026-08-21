import { expect, test } from '@playwright/test'

import {
  approvePlan,
  expectNoDispatchArtifacts,
  navigateTo,
  openDashboard,
  resetBackend,
  resolveReeferDispute,
  stageReadout,
  startRun,
} from './helpers'

// PRD golden acceptance flow: alert -> parallel analysis -> dispute ->
// three plans with recommendation -> approval -> mocked receipts.

test.beforeEach(async ({ request }) => {
  await resetBackend(request)
})

test('golden run: parallel analysis, dispute resolution, three plans, approval, receipts', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)

  // Parallel specialist work: Impact and Yard agent cards are both active
  // before the dispute pauses the workflow (PRD 9.17).
  const impactCard = page.locator('.agent-card', { hasText: 'Impact Agent' })
  const yardCard = page.locator('.agent-card', { hasText: 'Yard Agent' })
  await expect(impactCard).not.toContainText('WAITING', { timeout: 30_000 })
  await expect(yardCard).not.toContainText('WAITING', { timeout: 30_000 })

  // No dispatch-like element exists this early in the run.
  await expectNoDispatchArtifacts(page)

  // The reefer plug capacity dispute pauses the workflow until the human
  // confirms the governing constraint (PRD 9.18).
  await resolveReeferDispute(page)

  // Exactly three recovery plans with a visible recommendation (PRD 9.8/9.9).
  await navigateTo(page, 'Recovery')
  const planCards = page.getByRole('article', { name: /^Recovery plan:/ })
  await expect(planCards).toHaveCount(3, { timeout: 30_000 })
  const recommendedCard = planCards.filter({ hasText: 'Recommended' })
  await expect(recommendedCard).toHaveCount(1)
  await expect(recommendedCard).toContainText(/rush critical cargo and rebook the rest/i)

  // Approval gate: still nothing dispatch-like before the human approves.
  await expect(stageReadout(page)).toHaveText('AWAITING APPROVAL', { timeout: 30_000 })
  await expectNoDispatchArtifacts(page)

  // Approve the hybrid plan from the approval bar (PRD 9.10).
  await approvePlan(page, 'OPTIMIZED_HYBRID')

  // Mocked receipts appear only after approval (PRD 9.15).
  await navigateTo(page, 'Execution')
  await expect(page.getByText('EXECUTION RECEIPTS (MOCKED)')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.receipt-list .receipt-status').first()).toHaveText('ACCEPTED')
  await expect(stageReadout(page)).toHaveText('COMPLETE', { timeout: 30_000 })
})
