import { GitFork } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { AgentActivity, AgentName, TraceEvent } from '../api/types'
import { deriveAgentViews } from '../lib/derive'
import { formatElapsed, humanizeOperationalText } from '../lib/format'

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
    const tool = view.toolsCalled.at(-1)
    return (
      <button
        // Keyed here rather than at the call site, because the parallel branch
        // renders a list of these and each agent appears in the flow once.
        key={agent}
        type="button"
        className={`agent-topology__node status-${view.status.toLowerCase()}`}
        aria-pressed={selectedAgent === agent}
        onClick={() => setSelectedAgent(agent)}
      >
        <span className="agent-topology__node-name">{view.agent.replace(' Agent', '')}</span>
        <span className="agent-topology__node-state">{view.status}</span>
        {/* A tool badge only when a tool was actually called. Printing
            "no tool call" under all five idle nodes gave the loudest line on
            the diagram to the least information on it. */}
        {tool && (
          <span className="agent-topology__node-tool">{humanizeOperationalText(tool)}</span>
        )}
      </button>
    )
  }

  return (
    <section className="agent-topology" aria-labelledby="agent-topology-title" data-tour="agent-topology">
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
                <span className="agent-topology__connector" aria-hidden="true" />
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
          <p>{humanizeOperationalText(selected.objective)}</p>
          {/*
            Before this agent has done anything there is nothing to tabulate, and
            five rows reading "none recorded" filled half the card with the
            absence of information. Say what will appear here instead.
          */}
          {selected.eventCount === 0 ? (
            <div className="agent-topology__pending">
              <p>
                Nothing recorded yet. Once the coordinator hands off, this panel
                reports the tool this agent called, the evidence it got back, the
                assumptions it declared, how long it took, and who it hands to
                next.
              </p>
              <p className="agent-topology__pending-hint">
                Start a run from the Command Center to populate it.
              </p>
            </div>
          ) : (
          <dl>
            <div>
              <dt>Active or latest tool</dt>
              <dd>
                {selected.toolsCalled.at(-1)
                  ? humanizeOperationalText(selected.toolsCalled.at(-1) ?? '')
                  : 'No tool called yet'}
              </dd>
            </div>
            <div>
              <dt>Elapsed</dt>
              <dd>{formatElapsed(selected.elapsedMs)}</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>
                {humanizeOperationalText(
                  selected.evidence.at(-1) ?? selected.lastSummary ?? 'Waiting for evidence.',
                )}
              </dd>
            </div>
            <div>
              <dt>Assumptions</dt>
              <dd>
                {humanizeOperationalText(
                  selected.assumptions.join(' ') || 'No assumptions recorded.',
                )}
              </dd>
            </div>
            <div>
              <dt>Next handoff</dt>
              <dd>{selected.nextHandoff ?? 'Set on handoff'}</dd>
            </div>
          </dl>
          )}
        </aside>
      </div>
    </section>
  )
}
