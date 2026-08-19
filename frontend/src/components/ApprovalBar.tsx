import { ShieldAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { ApprovalDecision, PlanArchetype, PlanComparison } from '../api/types'
import { formatMoney, titleCase } from '../lib/format'
import { usePublishedHeight } from '../lib/usePublishedHeight'

interface ApprovalBarProps {
  comparison: PlanComparison | null
  selectedPlan: PlanArchetype | null
  onSelectPlan: (plan: PlanArchetype) => void
  onDecide: (plan: PlanArchetype, decision: ApprovalDecision, note?: string) => Promise<void>
}

export function ApprovalBar({ comparison, selectedPlan, onSelectPlan, onDecide }: ApprovalBarProps) {
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingDecision, setPendingDecision] = useState<ApprovalDecision | null>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)
  const barRef = useRef<HTMLElement>(null)

  const evaluation = comparison?.evaluations.find(
    (candidate) => candidate.plan.archetype === selectedPlan,
  )

  const decide = async (decision: ApprovalDecision) => {
    if (!selectedPlan) return
    setSubmitting(true)
    setError(null)
    try {
      await onDecide(selectedPlan, decision, note.trim() || undefined)
      setPendingDecision(null)
    } catch {
      setError('The decision could not be submitted. Try again.')
      setSubmitting(false)
    }
  }

  /*
   * The bar is fixed to the bottom of the viewport and sits above everything
   * else on the page, so while it is up it hides whatever the last 100-odd
   * pixels of the workspace happen to be - including the sticky forecast
   * timeline, which pins itself to the same edge. The layout gets out of its
   * way by reserving exactly the height it occupies.
   */
  usePublishedHeight(barRef, '--approval-bar-height')

  useEffect(() => {
    if (!pendingDecision) return undefined
    confirmButtonRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting) setPendingDecision(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [pendingDecision, submitting])

  return (
    <>
      <aside
        ref={barRef}
        className="approval-bar"
        role="region"
        aria-label="Human approval"
        data-tour="approval-bar"
      >
        <div className="approval-icon" aria-hidden="true">
          <ShieldAlert size={21} />
        </div>
        <div className="approval-copy">
          <p className="approval-label">Human authorization required</p>
          {evaluation ? (
            <>
              <strong>
                {titleCase(evaluation.plan.archetype)}
                {evaluation.plan.archetype === comparison?.recommended && (
                  <span className="recommended-badge">Recommended</span>
                )}
              </strong>
              <p className="approval-consequences">
                {formatMoney(evaluation.metrics.cost.total)} illustrative cost,{' '}
                {evaluation.metrics.missed_connections} missed connections,{' '}
                {Math.round(evaluation.metrics.critical_cargo_protected_pct)}% critical cargo
                protected, {Math.round(evaluation.metrics.yard_peak_occupancy_pct)}% yard peak, up
                to +{evaluation.metrics.max_additional_delay_hours} h added delay.
              </p>
            </>
          ) : (
            <p className="approval-consequences">
              Plan details are loading. Approve or reject once a plan is selected.
            </p>
          )}
        </div>

        <div className="approval-actions">
          {comparison && (
            <label className="plan-switcher">
              Plan
              <select
                value={selectedPlan ?? ''}
                onChange={(event) => onSelectPlan(event.target.value as PlanArchetype)}
              >
                {comparison.evaluations.map((candidate) => (
                  <option
                    key={candidate.plan.archetype}
                    value={candidate.plan.archetype}
                    disabled={!candidate.feasible}
                  >
                    {titleCase(candidate.plan.archetype)}
                    {candidate.feasible ? '' : ' (infeasible)'}
                  </option>
                ))}
              </select>
            </label>
          )}
          <input
            type="text"
            className="approval-note"
            aria-label="Decision note"
            placeholder="Optional operator note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          <button
            className="primary-action"
            type="button"
            data-tour="approval-approve"
            disabled={submitting || !selectedPlan || !evaluation?.feasible}
            onClick={() => setPendingDecision('APPROVED')}
          >
            Approve
          </button>
          <button
            className="danger-action"
            type="button"
            disabled={submitting || !selectedPlan}
            onClick={() => setPendingDecision('REJECTED')}
          >
            Reject
          </button>
        </div>

        {error && <p className="error-banner" role="alert">{error}</p>}
      </aside>

      {pendingDecision && evaluation && (
        <div
          className="approval-confirmation-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !submitting) setPendingDecision(null)
          }}
        >
          <section
            className="approval-confirmation"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-confirmation-title"
            aria-describedby="approval-confirmation-consequences"
          >
            <header>
              <ShieldAlert size={20} aria-hidden="true" />
              <div>
                <h2 id="approval-confirmation-title">
                  {pendingDecision === 'APPROVED'
                    ? 'Confirm simulated execution'
                    : 'Confirm plan rejection'}
                </h2>
                <p>{titleCase(evaluation.plan.archetype)}</p>
              </div>
            </header>
            <p id="approval-confirmation-consequences">
              {pendingDecision === 'APPROVED'
                ? `This authorizes mocked actions for ${formatMoney(
                    evaluation.metrics.cost.total,
                  )} illustrative cost, ${evaluation.metrics.missed_connections} missed connections, and ${Math.round(
                    evaluation.metrics.yard_peak_occupancy_pct,
                  )}% forecast yard occupancy.`
                : 'This ends the run without creating any mocked actions.'}
            </p>
            <p className="approval-confirmation-safety">
              Simulation only. No real terminal or carrier system will be contacted.
            </p>
            <div className="approval-confirmation-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() => setPendingDecision(null)}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                ref={confirmButtonRef}
                type="button"
                data-tour={pendingDecision === 'APPROVED' ? 'approval-confirm' : undefined}
                className={pendingDecision === 'APPROVED' ? 'primary-action' : 'danger-action'}
                onClick={() => void decide(pendingDecision)}
                disabled={submitting}
              >
                {submitting
                  ? 'Submitting...'
                  : pendingDecision === 'APPROVED'
                    ? 'Confirm simulated execution'
                    : 'Confirm rejection'}
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}
