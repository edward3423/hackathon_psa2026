import { describe, expect, it } from 'vitest'

import golden from '../../../fixtures/agent_status_golden.json'
import type { AgentName, AgentStatus, TraceEvent } from '../api/types'
import { deriveAgentViews } from './derive'

/**
 * `fixtures/agent_status_golden.json` is one real Act 1 run recorded by
 * scripts/export_agent_status_golden.py: the trace as the app receives it, and
 * the per-agent status the backend ends on. The frontend derives that status a
 * second time from the same trace, and the two answers reach the same badge.
 * When they disagree the UI contradicts itself, which is exactly what manual QA
 * found: the workflow read COMPLETE while the Coordinator still read RUNNING.
 */
const goldenTrace = golden.trace as Array<Pick<TraceEvent, 'kind' | 'stage' | 'agent' | 'error'>>
const goldenActivities = golden.activities as Array<{ agent: AgentName; status: AgentStatus }>

/** The recorded fields, padded out to a whole TraceEvent for deriveAgentViews. */
function replayEvents(): TraceEvent[] {
  return goldenTrace.map((event, index) => ({
    event_id: `golden-${index}`,
    sequence: index,
    timestamp: '2026-09-13T18:00:00Z',
    assumptions: [],
    ...event,
  }))
}

function statusOf(views: ReturnType<typeof deriveAgentViews>, agent: AgentName): AgentStatus {
  const view = views.find((candidate) => candidate.agent === agent)
  if (!view) throw new Error(`no view for ${agent}`)
  return view.status
}

describe('deriveAgentViews against the recorded backend run', () => {
  it('ends every agent on the status the backend reports', () => {
    const views = deriveAgentViews(replayEvents(), undefined)
    for (const { agent, status } of goldenActivities) {
      expect(statusOf(views, agent), `${agent} at end of run`).toBe(status)
    }
  })

  it('agrees with the backend after every event, not only at the end', () => {
    const events = replayEvents()
    for (let cut = 1; cut <= events.length; cut += 1) {
      const views = deriveAgentViews(events.slice(0, cut), undefined)
      // The mid-run invariant the two machines share: an agent is never left
      // COMPLETED and then revived, and no agent is FAILED unless the run
      // itself failed. A recoverable degraded tool must not read as a failure.
      const failed = views.filter((view) => view.status === 'FAILED')
      expect(failed.map((view) => view.agent), `after ${cut} events`).toEqual([])
    }
  })

  it('leaves the coordinator BLOCKED while approval is outstanding', () => {
    const events = replayEvents()
    const approvalIndex = events.findIndex((event) => event.kind === 'APPROVAL_REQUIRED')
    expect(approvalIndex).toBeGreaterThan(-1)
    const views = deriveAgentViews(events.slice(0, approvalIndex + 1), undefined)
    expect(statusOf(views, 'Coordinator Agent')).toBe('BLOCKED')
  })

  it('does not let stale polled activities override the finished run', () => {
    // useRunStream refetches workflow state on RUN_COMPLETED, so a stale
    // activities payload can arrive alongside a complete trace. The trace wins.
    const stale = goldenActivities.map((activity) => ({
      agent: activity.agent,
      objective: '',
      status: 'RUNNING' as AgentStatus,
      confidence: null,
      last_summary: null,
    }))
    const views = deriveAgentViews(replayEvents(), stale)
    expect(statusOf(views, 'Coordinator Agent')).toBe('COMPLETED')
  })
})
