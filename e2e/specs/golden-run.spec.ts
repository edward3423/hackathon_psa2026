import { expect, test } from '@playwright/test'

import { expectNoDispatchArtifacts, openDashboard, startRun } from './helpers'

// PRD 9.x golden acceptance flow: alert -> parallel analysis -> dispute ->
// three plans with recommendation -> approval -> mocked receipts.
//
// test.fixme: awaits the full workflow backend (dispute pause at
// DISPUTE_OPENED, POST /api/runs/{id}/dispute-resolution, approval pause at
// APPROVAL_REQUIRED, POST /api/runs/{id}/approval, mocked dispatch results)
// and the dashboard dispute panel, plan cards, and approval bar UI.
// The stub backend streams straight through with no pauses and the shell UI
// has no dispute, plan, or approval elements yet.

test.fixme('golden run: parallel analysis, dispute resolution, three plans, approval, receipts', async ({ page }) => {
  await openDashboard(page)
  await startRun(page)

  // Parallel specialist work: Impact and Yard agent cards are both active
  // before either reports completion (PRD 9.17).
  const impactCard = page.locator('.agent-card', { hasText: 'Impact Agent' })
  const yardCard = page.locator('.agent-card', { hasText: 'Yard Agent' })
  await expect(impactCard).not.toContainText('WAITING', { timeout: 30_000 })
  await expect(yardCard).not.toContainText('WAITING', { timeout: 30_000 })

  // No dispatch-like element exists this early in the run.
  await expectNoDispatchArtifacts(page)

  // The reefer plug capacity dispute pauses the workflow (PRD 9.18).
  const disputePanel = page.getByRole('dialog', { name: /dispute/i })
  await expect(disputePanel).toBeVisible({ timeout: 60_000 })
  await expect(disputePanel).toContainText(/reefer/i)
  await expect(disputePanel).toContainText('Impact Agent')
  await expect(disputePanel).toContainText('Yard Agent')

  // The human confirms the governing constraint; planning resumes.
  await disputePanel.getByRole('button', { name: /reefer plug capacity/i }).click()
  await expect(disputePanel).toBeHidden({ timeout: 15_000 })

  // Exactly three recovery plans with a visible recommendation (PRD 9.8/9.9).
  const planCards = page.getByRole('article', { name: /plan/i })
  await expect(planCards).toHaveCount(3, { timeout: 60_000 })
  await expect(page.getByText(/recommended/i).first()).toBeVisible()
  await expect(page.getByText(/OPTIMIZED[_ ]HYBRID/i).first()).toBeVisible()

  // Approval gate: still nothing dispatch-like before the human approves.
  await expect(page.getByText('AWAITING APPROVAL', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expectNoDispatchArtifacts(page)

  // Approve the hybrid plan from the approval bar (PRD 9.10).
  await page.getByRole('button', { name: /approve/i }).click()

  // Mocked receipts appear only after approval (PRD 9.15).
  await expect(page.getByText(/receipt/i).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('ACCEPTED').first()).toBeVisible()
  await expect(page.getByText('COMPLETE', { exact: true })).toBeVisible({ timeout: 30_000 })
})
