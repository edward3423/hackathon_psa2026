import { useState } from 'react'

import type { ApprovalDecision, PlanArchetype, PlanComparison } from '../api/types'
import { formatMoney, titleCase } from '../lib/format'

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

  const evaluation = comparison?.evaluations.find(
    (candidate) => candidate.plan.archetype === selectedPlan,
  )

  const decide = async (decision: ApprovalDecision) => {
    if (!selectedPlan) return
    setSubmitting(true)
    setError(null)
    try {
      await onDecide(selectedPlan, decision, note.trim() || undefined)
    } catch {
      setError('The decision could not be submitted. Try again.')
      setSubmitting(false)
    }
  }

  return (
    <aside className="approval-bar" role="region" aria-label="Human approval">
      <div className="approval-copy">
        <p className="section-label">HUMAN APPROVAL REQUIRED</p>
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
              protected, {Math.round(evaluation.metrics.yard_peak_occupancy_pct)}% yard peak, up to
              +{evaluation.metrics.max_additional_delay_hours} h added delay.
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
          placeholder="Optional note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <button
          className="primary-action"
          type="button"
          disabled={submitting || !selectedPlan}
          onClick={() => decide('APPROVED')}
        >
          Approve
        </button>
        <button
          className="danger-action"
          type="button"
          disabled={submitting || !selectedPlan}
          onClick={() => decide('REJECTED')}
        >
          Reject
        </button>
      </div>

      {error && <p className="error-banner" role="alert">{error}</p>}
    </aside>
  )
}
