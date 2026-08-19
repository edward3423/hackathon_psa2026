import type { AlternativeSailingResult, ConnectionAnalysis, YardForecast } from '../api/types'
import { groupTotals, yardPeakPercent } from '../lib/derive'
import { formatDateTime } from '../lib/format'

interface MetricsPanelProps {
  analysis: ConnectionAnalysis | null
  baselineYard: YardForecast | null
  sailings: AlternativeSailingResult | null
}

export function MetricsPanel({ analysis, baselineYard, sailings }: MetricsPanelProps) {
  const totals = analysis ? groupTotals(analysis) : null

  return (
    <section className="metrics-panel" aria-labelledby="metrics-title" data-tour="impact-summary">
      <div className="panel-heading">
        <div>
          <h2 id="metrics-title">Impact summary</h2>
          <p className="panel-description">Calculated connection and terminal pressure.</p>
        </div>
      </div>

      {totals ? (
        <dl className="metric-grid">
          <div className="status-safe">
            <dt>Safe connections</dt>
            <dd>{totals.safe}</dd>
          </div>
          <div className="status-at-risk">
            <dt>At risk</dt>
            <dd>{totals.atRisk}</dd>
          </div>
          <div className="status-missed">
            <dt>Expected misses</dt>
            <dd>{totals.missed}</dd>
          </div>
          <div>
            <dt>Yard peak</dt>
            <dd>{baselineYard ? `${yardPeakPercent(baselineYard)}%` : '-'}</dd>
          </div>
        </dl>
      ) : (
        <p className="panel-placeholder">Impact figures appear after specialist analysis.</p>
      )}

      {baselineYard && baselineYard.reefer_shortages.length > 0 && (
        <aside
          className="operational-notice operational-notice--critical"
          role="alert"
          aria-labelledby="reefer-shortage-title"
          data-tour="reefer-alert"
        >
          <h3 id="reefer-shortage-title">Refrigerated container plug shortage</h3>
          {baselineYard.reefer_shortages.map((shortage) => (
            <p key={`${shortage.block_id}-${shortage.start_time}`}>
              Block {shortage.block_id} needs {shortage.required_plugs} electrical plugs, but only{' '}
              {shortage.available_plugs} are available from {formatDateTime(shortage.start_time)}.
            </p>
          ))}
        </aside>
      )}

      {sailings?.status === 'TIMEOUT_CACHED_FALLBACK' && (
        <aside
          className="operational-notice operational-notice--warning sailing-fallback-notice"
          role="status"
          aria-labelledby="fallback-title"
          data-tour="sailing-fallback"
        >
          <h3 id="fallback-title">Sailing lookup timed out</h3>
          <p>
            Cached sailing data was used. It may be stale, so this result has medium confidence.
          </p>
          {sailings.stale_notice && <p>{sailings.stale_notice}</p>}
        </aside>
      )}
    </section>
  )
}
