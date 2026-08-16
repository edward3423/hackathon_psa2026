import type {
  ActionReceipt,
  AlternativeSailingResult,
  ConnectionAnalysis,
  PlanArchetype,
  PlanComparison,
  YardForecast,
} from '../api/types'
import { groupTotals, yardPeakPercent } from '../lib/derive'
import { formatDateTime, formatMoney, titleCase } from '../lib/format'

interface MetricsPanelProps {
  analysis: ConnectionAnalysis | null
  baselineYard: YardForecast | null
  comparison: PlanComparison | null
  sailings: AlternativeSailingResult | null
  selectedPlan: PlanArchetype | null
  onSelectPlan: (plan: PlanArchetype) => void
  receipts: ActionReceipt[]
}

export function MetricsPanel({
  analysis,
  baselineYard,
  comparison,
  sailings,
  selectedPlan,
  onSelectPlan,
  receipts,
}: MetricsPanelProps) {
  const totals = analysis ? groupTotals(analysis) : null
  const selectedEvaluation = comparison?.evaluations.find(
    (evaluation) => evaluation.plan.archetype === selectedPlan,
  )

  return (
    <section className="metrics-panel" aria-labelledby="metrics-title">
      <div className="panel-heading">
        <div>
          <p className="section-label">OPERATIONAL METRICS</p>
          <h2 id="metrics-title">Impact and recovery</h2>
        </div>
      </div>

      {totals ? (
        <dl className="metric-grid">
          <div className="status-safe">
            <dt>SAFE</dt>
            <dd>{totals.safe}</dd>
          </div>
          <div className="status-at-risk">
            <dt>AT RISK</dt>
            <dd>{totals.atRisk}</dd>
          </div>
          <div className="status-missed">
            <dt>MISSED</dt>
            <dd>{totals.missed}</dd>
          </div>
          <div>
            <dt>YARD PEAK</dt>
            <dd>{baselineYard ? `${yardPeakPercent(baselineYard)}%` : '-'}</dd>
          </div>
        </dl>
      ) : (
        <p className="panel-placeholder">Metrics appear when specialist analysis completes.</p>
      )}

      {baselineYard && baselineYard.reefer_shortages.length > 0 && (
        <div className="shortage-callout" role="alert">
          <strong>REEFER PLUG SHORTAGE</strong>
          {baselineYard.reefer_shortages.map((shortage) => (
            <p key={`${shortage.block_id}-${shortage.start_time}`}>
              Block {shortage.block_id}: {shortage.required_plugs} plugs needed,{' '}
              {shortage.available_plugs} available from {formatDateTime(shortage.start_time)}
            </p>
          ))}
        </div>
      )}

      {sailings?.status === 'TIMEOUT_CACHED_FALLBACK' && (
        <div className="fallback-callout" role="status">
          <strong>SAILING LOOKUP TIMEOUT - CACHED FALLBACK</strong>
          <p>
            The alternative-sailing lookup timed out. Cached sailing data was used and may be
            stale, so confidence is limited to{' '}
            <span className="confidence-chip medium">MEDIUM</span>.
          </p>
          {sailings.stale_notice && <p>{sailings.stale_notice}</p>}
        </div>
      )}

      {selectedEvaluation && (
        <p className="cost-line">
          Disruption cost (illustrative):{' '}
          <strong>{formatMoney(selectedEvaluation.metrics.cost.total)}</strong>
        </p>
      )}

      {comparison && (
        <div className="plan-list" aria-label="Recovery plans">
          <p className="section-label">RECOVERY PLANS</p>
          {comparison.evaluations.map((evaluation) => {
            const archetype = evaluation.plan.archetype
            const isSelected = archetype === selectedPlan
            const isRecommended = archetype === comparison.recommended
            return (
              <article
                key={archetype}
                aria-label={`Recovery plan: ${titleCase(archetype)}`}
                className={`plan-card${isSelected ? ' selected' : ''}${
                  evaluation.feasible ? '' : ' infeasible'
                }`}
              >
                <header>
                  <button
                    type="button"
                    className="plan-select"
                    aria-pressed={isSelected}
                    onClick={() => onSelectPlan(archetype)}
                  >
                    {titleCase(archetype)}
                  </button>
                  <span className="plan-flags">
                    {isRecommended && <span className="recommended-badge">Recommended</span>}
                    <span className={`feasibility ${evaluation.feasible ? 'ok' : 'rejected'}`}>
                      {evaluation.feasible ? 'FEASIBLE' : 'INFEASIBLE'}
                    </span>
                  </span>
                </header>
                <p className="plan-archetype-code">{archetype}</p>
                <dl className="plan-metrics">
                  <div>
                    <dt>Cost</dt>
                    <dd>{formatMoney(evaluation.metrics.cost.total)}</dd>
                  </div>
                  <div>
                    <dt>Missed</dt>
                    <dd>{evaluation.metrics.missed_connections}</dd>
                  </div>
                  <div>
                    <dt>Critical protected</dt>
                    <dd>{Math.round(evaluation.metrics.critical_cargo_protected_pct)}%</dd>
                  </div>
                  <div>
                    <dt>Yard peak</dt>
                    <dd>{Math.round(evaluation.metrics.yard_peak_occupancy_pct)}%</dd>
                  </div>
                  <div>
                    <dt>Max delay</dt>
                    <dd>+{evaluation.metrics.max_additional_delay_hours} h</dd>
                  </div>
                </dl>
                {!evaluation.feasible && evaluation.rejection_reasons && (
                  <p className="rejection-reasons">{evaluation.rejection_reasons.join(' ')}</p>
                )}
              </article>
            )
          })}
          <p className="plan-rationale">
            <span className="section-label">WHY RECOMMENDED</span>
            {comparison.rationale}{' '}
            <span className={`confidence-chip ${comparison.confidence.toLowerCase()}`}>
              {comparison.confidence}
            </span>
          </p>
        </div>
      )}

      {receipts.length > 0 && (
        <div className="receipt-list">
          <p className="section-label">EXECUTION RECEIPTS (MOCKED)</p>
          <ul>
            {receipts.map((receipt) => (
              <li key={receipt.action_id} className={receipt.status.toLowerCase()}>
                <span className="receipt-status">{receipt.status}</span>
                <span className="receipt-detail">{receipt.detail}</span>
                {receipt.receipt_ref && <span className="receipt-ref">{receipt.receipt_ref}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
