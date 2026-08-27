import type { AlternativeSailingResult, ConnectionAnalysis, YardForecast } from '../api/types'
import { formatDateTime, humanizeOperationalText, pluralize } from '../lib/format'

interface MetricsPanelProps {
  analysis: ConnectionAnalysis | null
  baselineYard: YardForecast | null
  sailings: AlternativeSailingResult | null
}

/*
 * What the engine wants the operator to know that a number cannot say: a
 * physical limit the scenario breaks, and a tool that failed and was answered
 * from cache. The four figures this panel used to repeat - at risk, misses, yard
 * peak, safe - are the same four the dashboard states at the top of its main
 * column, so they are stated once, there.
 */
export function MetricsPanel({ analysis, baselineYard, sailings }: MetricsPanelProps) {
  const shortages = baselineYard?.reefer_shortages ?? []
  const fallback = sailings?.status === 'TIMEOUT_CACHED_FALLBACK'
  const quiet = shortages.length === 0 && !fallback

  return (
    <section className="metrics-panel" aria-labelledby="metrics-title" data-tour="impact-summary">
      <div className="panel-heading">
        <h2 id="metrics-title">Engine notices</h2>
        <span className="calculated-badge">DETERMINISTIC</span>
      </div>

      {quiet && (
        <p className="panel-placeholder">
          {analysis
            ? 'No physical constraint was breached and every tool answered. Figures come from the deterministic engine, not from a model.'
            : 'Constraint warnings and tool failures are reported here once the specialists run.'}
        </p>
      )}

      {shortages.length > 0 && (
        <aside
          className="operational-notice operational-notice--critical"
          role="alert"
          aria-labelledby="reefer-shortage-title"
          data-tour="reefer-alert"
        >
          <h3 id="reefer-shortage-title">Reefer plug shortage</h3>
          {shortages.map((shortage) => {
            const needed = pluralize(shortage.required_plugs, 'electrical plug')
            const availability = shortage.available_plugs === 1 ? 'is' : 'are'
            return (
              <p key={`${shortage.block_id}-${shortage.start_time}`}>
                {`Block ${shortage.block_id} needs ${needed}, but only ${shortage.available_plugs} `}
                {`${availability} available from ${formatDateTime(shortage.start_time)}.`}
              </p>
            )
          })}
        </aside>
      )}

      {fallback && (
        <aside
          className="operational-notice operational-notice--warning sailing-fallback-notice"
          role="status"
          aria-labelledby="fallback-title"
          data-tour="sailing-fallback"
        >
          <h3 id="fallback-title">Sailing lookup timed out</h3>
          <p>Cached sailing data was used. It may be stale, so this result has medium confidence.</p>
          {sailings?.stale_notice && <p>{humanizeOperationalText(sailings.stale_notice)}</p>}
        </aside>
      )}
    </section>
  )
}
