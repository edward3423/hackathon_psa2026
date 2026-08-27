import {
  BrainCircuit,
  ClipboardCheck,
  Container,
  Network,
  Route,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'

import type { AgentActivity, TraceEvent } from '../api/types'
import { deriveAgentViews, type AgentView } from '../lib/derive'
import { formatElapsed, humanizeOperationalText } from '../lib/format'

interface AgentActivityPanelProps {
  events: TraceEvent[]
  activities: AgentActivity[] | undefined
  streaming: boolean
}

const AGENT_ICON: Record<AgentView['agent'], LucideIcon> = {
  'Coordinator Agent': Network,
  'Impact Agent': Container,
  'Yard Agent': BrainCircuit,
  'Recovery Agent': Route,
  'Execution Agent': ClipboardCheck,
}

/*
 * One line per agent. Each card used to carry the agent's name, its standing
 * role description, its status, its confidence, a parallel-group line, an
 * active-tool chip and a result paragraph - five of those stacked filled the
 * whole rail with "Waiting for coordinator handoff" before anything had
 * happened. The role description now shows only while the agent has nothing to
 * report, so the panel explains itself before a run and reports during one.
 */
function AgentCard({ view }: { view: AgentView }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = AGENT_ICON[view.agent]
  const activeTool = view.toolsCalled.at(-1)
  const statusLabel = view.status === 'RUNNING' && activeTool ? 'CALLING TOOL' : view.status
  /*
   * Two lines: the objective it currently holds, and what it last reported.
   * Both are load-bearing. The objective is where the revision loop becomes
   * visible - "Revise the rejected Optimized Hybrid proposal" is the only place
   * a viewer sees a plan being sent back - and the report is the outcome.
   */
  const reported = view.result ?? view.lastSummary

  return (
    <article
      className={`agent-card ${view.status.toLowerCase()}${view.parallelGroup ? ' parallel' : ''}`}
      aria-label={`${view.agent}: ${statusLabel}`}
    >
      <header>
        <span className="agent-symbol" aria-hidden="true">
          <Icon size={15} />
        </span>
        <h3>{view.agent}</h3>
        {view.confidence && (
          <span className={`confidence-chip ${view.confidence.toLowerCase()}`}>
            {view.confidence}
          </span>
        )}
        <span className="agent-status">
          <i aria-hidden="true" />
          {statusLabel}
        </span>
      </header>

      <p className="agent-objective">{humanizeOperationalText(view.objective)}</p>
      <p className="agent-result">
        {humanizeOperationalText(reported ?? 'Waiting for coordinator handoff.')}
      </p>

      {view.eventCount > 0 && (
        <button
          className="detail-toggle"
          type="button"
          onClick={() => setExpanded((current) => !current)}
          aria-expanded={expanded}
        >
          {expanded ? 'Hide details' : 'Show details'}
        </button>
      )}

      {view.eventCount > 0 && expanded && (
        <dl className="agent-detail-grid">
          {view.parallelGroup && (
            <div>
              <dt>Parallel group</dt>
              <dd>{view.parallelGroup}</dd>
            </div>
          )}
          {view.inputSummaries.length > 0 && (
            <div>
              <dt>Inputs</dt>
              <dd>{humanizeOperationalText(view.inputSummaries.join(' '))}</dd>
            </div>
          )}
          {view.toolsCalled.length > 0 && (
            <div>
              <dt>Tools called</dt>
              <dd>{humanizeOperationalText(view.toolsCalled.join(', '))}</dd>
            </div>
          )}
          {view.evidence.length > 0 && (
            <div>
              <dt>Evidence</dt>
              <dd>
                {/* Keyed by position: an agent can report the same line twice,
                    for instance when a plan is re-evaluated after revision. */}
                <ul>
                  {view.evidence.map((item, index) => (
                    <li key={index}>{humanizeOperationalText(item)}</li>
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
                  {view.assumptions.map((item, index) => (
                    <li key={index}>{humanizeOperationalText(item)}</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
          {view.result && (
            <div>
              <dt>Result</dt>
              <dd>{humanizeOperationalText(view.result)}</dd>
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
    <section className="activity-panel" aria-labelledby="activity-title" data-tour="agent-panel">
      <div className="panel-heading">
        <h2 id="activity-title">Agents</h2>
        <span className={streaming ? 'live-indicator active' : 'live-indicator'}>
          {streaming ? 'STREAMING' : 'IDLE'}
        </span>
      </div>

      <div className="agent-stack">
        {views.map((view) => (
          <AgentCard key={view.agent} view={view} />
        ))}
      </div>
    </section>
  )
}
