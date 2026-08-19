import { useState } from 'react'

import type { Dispute, TraceEvent } from '../api/types'

interface DisputeOverlayProps {
  dispute: Dispute | null
  /** The DISPUTE_OPENED event, for rendering before the polled state arrives. */
  openEvent: TraceEvent | null
  onResolve: (disputeId: string, confirmedConstraint: string) => Promise<void>
}

const REEFER_PRESET = 'Respect physical reefer plug capacity'

function presetChoices(dispute: Dispute | null): string[] {
  if (!dispute) return []
  const choices = dispute.positions.map((position) => position.position)
  const text = [
    dispute.question,
    ...dispute.positions.flatMap((position) => [position.position, ...position.evidence]),
  ]
    .join(' ')
    .toLowerCase()
  if ((text.includes('reefer') || text.includes('plug')) && !choices.includes(REEFER_PRESET)) {
    choices.push(REEFER_PRESET)
  }
  return choices
}

export function DisputeOverlay({ dispute, openEvent, onResolve }: DisputeOverlayProps) {
  const [choice, setChoice] = useState<string>('')
  const [freeText, setFreeText] = useState('')
  const [useFreeText, setUseFreeText] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const question =
    dispute?.question ?? openEvent?.decision_summary ?? 'The agents need a human decision.'
  const constraint = useFreeText ? freeText.trim() : choice
  const canSubmit = dispute !== null && constraint.length > 0 && !submitting

  const submit = async () => {
    if (!dispute || constraint.length === 0) return
    setSubmitting(true)
    setError(null)
    try {
      await onResolve(dispute.dispute_id, constraint)
    } catch {
      setError('The constraint could not be submitted. Try again.')
      setSubmitting(false)
    }
  }

  return (
    <div className="overlay-backdrop" role="presentation">
      {/* Not aria-modal: the top-bar controls (Reset in particular) stay
          reachable while the workflow is paused at the dispute (PRD 9.16). */}
      <section
        className="dispute-overlay"
        role="dialog"
        aria-label="Agent dispute - human decision required"
        data-tour="dispute-dialog"
      >
        <p className="dialog-context">Agent disagreement requires an operator decision.</p>
        <h2>{question}</h2>

        {dispute ? (
          <div className="dispute-positions" data-tour="dispute-positions">
            {dispute.positions.map((position) => (
              <article key={position.agent} className="dispute-position">
                <h3>{position.agent}</h3>
                <p>{position.position}</p>
                <ul>
                  {position.evidence.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        ) : (
          <p className="panel-placeholder">Loading dispute evidence from the workflow state...</p>
        )}

        <div className="constraint-choice">
          <h3>Choose the governing constraint</h3>
          {presetChoices(dispute).map((preset) => (
            <button
              key={preset}
              type="button"
              className={`constraint-option${!useFreeText && choice === preset ? ' selected' : ''}`}
              data-tour={preset === REEFER_PRESET ? 'dispute-constraint-reefer' : undefined}
              aria-pressed={!useFreeText && choice === preset}
              onClick={() => {
                setChoice(preset)
                setUseFreeText(false)
              }}
            >
              {preset}
            </button>
          ))}
          <button
            type="button"
            className={`constraint-option${useFreeText ? ' selected' : ''}`}
            aria-pressed={useFreeText}
            onClick={() => setUseFreeText(true)}
          >
            State another constraint
          </button>
          {useFreeText && (
            <input
              type="text"
              className="constraint-freetext"
              aria-label="Custom constraint"
              placeholder="State the constraint the plans must respect"
              value={freeText}
              onChange={(event) => setFreeText(event.target.value)}
            />
          )}
        </div>

        {error && <p className="error-banner" role="alert">{error}</p>}

        <button
          className="primary-action"
          type="button"
          data-tour="dispute-confirm"
          onClick={submit}
          disabled={!canSubmit}
        >
          {submitting ? 'Submitting...' : 'Confirm constraint'}
        </button>
      </section>
    </div>
  )
}
