import { useMemo } from 'react'

import type { CargoType, ConnectionAnalysis, ConnectionStatus } from '../api/types'
import { groupTotals, STATUS_LABEL } from '../lib/derive'

const GRAPH_CARGO_LABEL: Record<CargoType, string> = {
  PHARMA_REEFER: 'Refrigerated medicine',
  TIME_CRITICAL_MANUFACTURING: 'Time-critical manufacturing',
  GENERAL_DRY: 'Standard dry cargo',
}

const STATUS_CLASS: Record<ConnectionStatus, string> = {
  SAFE: 'safe',
  AT_RISK: 'at-risk',
  MISSED: 'missed',
  RESOLVED: 'resolved',
}

const STATUS_ORDER: Record<ConnectionStatus, number> = {
  MISSED: 0,
  AT_RISK: 1,
  RESOLVED: 2,
  SAFE: 3,
}

interface CascadeGraphProps {
  inboundVessel: string
  delayHours: number
  analysis: ConnectionAnalysis | null
}

/**
 * A readable connection map rather than a force-fitted node diagram.
 *
 * The old canvas tried to fit all 23 cargo groups and their edges into one
 * viewport. At desktop sizes that reduced labels to a few visible pixels and
 * left most of the canvas empty. Grouping the same facts into one lane per
 * onward vessel preserves the flow while keeping every label at normal size.
 */
export function CascadeGraph({ inboundVessel, delayHours, analysis }: CascadeGraphProps) {
  const lanes = useMemo(() => {
    if (!analysis) return []
    const byVessel = new Map<string, ConnectionAnalysis['groups']>()
    for (const group of analysis.groups) {
      const groups = byVessel.get(group.onward_vessel) ?? []
      groups.push(group)
      byVessel.set(group.onward_vessel, groups)
    }
    return [...byVessel.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([vessel, groups]) => ({
        vessel,
        groups: [...groups].sort(
          (left, right) =>
            STATUS_ORDER[left.status] - STATUS_ORDER[right.status] ||
            left.cargo_type.localeCompare(right.cargo_type),
        ),
        total: groups.reduce((sum, group) => sum + group.container_count, 0),
      }))
  }, [analysis])

  const totals = analysis ? groupTotals(analysis) : null
  const affected = totals ? totals.safe + totals.atRisk + totals.missed + totals.resolved : 0

  return (
    <section className="graph-panel" aria-labelledby="graph-title">
      <div className="panel-heading">
        <div>
          <h2 id="graph-title">Connection flows</h2>
          <p className="panel-description">Grouped by onward vessel, cargo, and transfer risk.</p>
        </div>
        {totals && (
          <dl className="graph-totals">
            <div className="status-safe">
              <dt>SAFE</dt>
              <dd data-testid="total-safe">{totals.safe}</dd>
            </div>
            <div className="status-at-risk">
              <dt>AT RISK</dt>
              <dd data-testid="total-at-risk">{totals.atRisk}</dd>
            </div>
            <div className="status-missed">
              <dt>MISSED</dt>
              <dd data-testid="total-missed">{totals.missed}</dd>
            </div>
            <div className="status-resolved">
              <dt>RESOLVED</dt>
              <dd data-testid="total-resolved">{totals.resolved}</dd>
            </div>
          </dl>
        )}
      </div>

      <div className="connection-map">
        <article className="connection-map__origin">
          <span>Delayed inbound</span>
          <strong>{inboundVessel}</strong>
          <small>+{delayHours} hours late</small>
          {analysis && <b>{affected} connecting containers</b>}
        </article>

        {analysis ? (
          <>
            <div className="connection-map__handoff" aria-hidden="true">
              <span />
              <small>transfer to</small>
              <span />
            </div>
            <div className="connection-map__lanes" aria-label="Connections grouped by onward vessel">
              {lanes.map((lane) => (
                <article className="connection-lane" key={lane.vessel}>
                  <header>
                    <div>
                      <span>Onward vessel</span>
                      <h3>{lane.vessel}</h3>
                    </div>
                    <strong>{lane.total}</strong>
                  </header>
                  <ul>
                    {lane.groups.map((group) => (
                      <li
                        className={`connection-group connection-group--${STATUS_CLASS[group.status]}`}
                        key={`${group.cargo_type}:${group.status}`}
                      >
                        <div>
                          <strong>{group.container_count}</strong>
                          <span>{GRAPH_CARGO_LABEL[group.cargo_type]}</span>
                        </div>
                        <em>{STATUS_LABEL[group.status]}</em>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </>
        ) : (
          <p className="panel-placeholder">
            Grouped container flows appear when connection analysis completes.
          </p>
        )}
      </div>
    </section>
  )
}
