import { ArrowDown, GitFork } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { AgentActivity, AgentName, TraceEvent } from '../api/types'
import { deriveAgentViews } from '../lib/derive'
import { formatElapsed } from '../lib/format'

interface AgentTopologyProps {
  events: TraceEvent[]
  activities?: AgentActivity[]
}

const FLOW: Array<AgentName | AgentName[]> = [
  'Coordinator Agent',
  ['Impact Agent', 'Yard Agent'],
  'Recovery Agent',
  'Execution Agent',
]

export function AgentTopology({ events, activities }: AgentTopologyProps) {
  const views = useMemo(() => deriveAgentViews(events, activities), [activities, events])
  const [selectedAgent, setSelectedAgent] = useState<AgentName>('Coordinator Agent')
  const selected = views.find((view) => view.agent === selectedAgent) ?? views[0]

  const node = (agent: AgentName) => {
    const view = views.find((candidate) => candidate.agent === agent)
    if (!view) return null
    return (
      <button
        type="button"
        className={`agent-topology__node status-${view.status.toLowerCase()}`}
        aria-pressed={selectedAgent === agent}
        onClick={() => setSelectedAgent(agent)}
      >
        <span>{view.agent.replace(' Agent', '')}</span>
        <strong>{view.status}</strong>
        <small>{view.toolsCalled.at(-1) ?? 'No tool call'}</small>
      </button>
    )
  }

  return (
    <section className="agent-topology" aria-labelledby="agent-topology-title">
      <header className="page-section-header">
        <div>
          <h2 id="agent-topology-title">Agent handoff topology</h2>
          <p>Inspect each specialist’s inputs, tools, evidence, and next handoff.</p>
        </div>
      </header>
      <div className="agent-topology__workspace">
        <div className="agent-topology__flow" aria-label="Agent workflow">
          {FLOW.map((step, index) => (
            <div className="agent-topology__step" key={Array.isArray(step) ? step.join('-') : step}>
              {Array.isArray(step) ? (
                <div className="agent-topology__parallel">
                  <span className="agent-topology__parallel-label">
                    <GitFork size={15} aria-hidden="true" /> Parallel specialists
                  </span>
                  <div>{step.map((agent) => node(agent))}</div>
                </div>
              ) : (
                node(step)
              )}
              {index < FLOW.length - 1 && (
                <ArrowDown className="agent-topology__connector" size={18} aria-hidden="true" />
              )}
            </div>
          ))}
        </div>

        <aside className="agent-topology__inspection" aria-live="polite">
          <header>
            <h3>{selected.agent}</h3>
            <span className={`agent-status status-${selected.status.toLowerCase()}`}>
              {selected.status}
            </span>
          </header>
          <p>{selected.objective}</p>
          <dl>
            <div>
              <dt>Active or latest tool</dt>
              <dd>
                <code>{selected.toolsCalled.at(-1) ?? 'None recorded'}</code>
              </dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{formatElapsed(selected.elapsedMs)}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>{selected.evidence.at(-1) ?? selected.lastSummary ?? 'Waiting for evidence.'}</dd>
            </div>
            <div>
              <dt>Assumptions</dt>
              <dd>{selected.assumptions.join(' ') || 'No assumptions recorded.'}</dd>
            </div>
            <div>
              <dt>Next handoff</dt>
              <dd>{selected.nextHandoff ?? 'Not assigned'}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </section>
  )
}
