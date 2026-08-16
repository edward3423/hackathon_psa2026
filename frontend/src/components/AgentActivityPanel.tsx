import { useState } from 'react'

import type { AgentActivity, TraceEvent } from '../api/types'
import { deriveAgentViews, type AgentView } from '../lib/derive'
import { formatElapsed } from '../lib/format'

interface AgentActivityPanelProps {
  events: TraceEvent[]
  activities: AgentActivity[] | undefined
  streaming: boolean
}

function AgentCard({ view, index }: { view: AgentView; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const showDetail = expanded || view.status === 'COMPLETED'

  return (
    <article
      className={`agent-card ${view.status.toLowerCase()}${view.parallelGroup ? ' parallel' : ''}`}
    >
      <header>
        <div className="agent-index">{String(index + 1).padStart(2, '0')}</div>
        <div>
          <h3>{view.agent}</h3>
          <p>{view.objective}</p>
        </div>
        <div className="agent-badges">
          <span className="agent-status">{view.status}</span>
          {view.confidence && (
            <span className={`confidence-chip ${view.confidence.toLowerCase()}`}>
              {view.confidence}
            </span>
          )}
        </div>
      </header>

      {view.parallelGroup && (
        <p className="parallel-tag">PARALLEL / {view.parallelGroup}</p>
      )}

      <p className="agent-result">
        {view.result ?? view.lastSummary ?? 'Waiting for coordinator handoff.'}
      </p>

      {view.eventCount > 0 && (
        <button
          className="detail-toggle"
          type="button"
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={showDetail}
        >
          {showDetail ? 'Hide details' : 'Show details'}
        </button>
      )}

      {view.eventCount > 0 && showDetail && (
        <dl className="agent-detail-grid">
          {view.inputSummaries.length > 0 && (
            <div>
              <dt>Inputs</dt>
              <dd>{view.inputSummaries.join(' ')}</dd>
            </div>
          )}
          {view.toolsCalled.length > 0 && (
            <div>
              <dt>Tools called</dt>
              <dd>{view.toolsCalled.join(', ')}</dd>
            </div>
          )}
          {view.evidence.length > 0 && (
            <div>
              <dt>Evidence</dt>
              <dd>
                <ul>
                  {view.evidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
          {view.assumptions.length > 0 && (
            <div>
              <dt>Assumptions</dt>
              <dd>
                <ul>
                  {view.assumptions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
          {view.result && (
            <div>
              <dt>Result</dt>
              <dd>{view.result}</dd>
            </div>
          )}
          <div>
            <dt>Elapsed</dt>
            <dd>{formatElapsed(view.elapsedMs)}</dd>
          </div>
          {view.nextHandoff && (
            <div>
              <dt>Next handoff</dt>
              <dd>{view.nextHandoff}</dd>
            </div>
          )}
        </dl>
      )}
    </article>
  )
}

export function AgentActivityPanel({ events, activities, streaming }: AgentActivityPanelProps) {
  const views = deriveAgentViews(events, activities)

  return (
    <section className="activity-panel" aria-labelledby="activity-title">
      <div className="panel-heading">
        <div>
          <p className="section-label">LIVE ORCHESTRATION</p>
          <h2 id="activity-title">Agent activity</h2>
        </div>
        <span className={streaming ? 'live-indicator active' : 'live-indicator'}>
          {streaming ? 'STREAMING' : 'IDLE'}
        </span>
      </div>

      <div className="agent-stack">
        {views.map((view, index) => (
          <AgentCard key={view.agent} view={view} index={index} />
        ))}
      </div>
    </section>
  )
}
