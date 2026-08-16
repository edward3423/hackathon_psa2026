import type {
  AgentActivity,
  AgentName,
  AgentStatus,
  ConnectionAnalysis,
  ConnectionStatus,
  TraceEvent,
  YardForecast,
} from '../api/types'

export const AGENT_ORDER: AgentName[] = [
  'Coordinator Agent',
  'Impact Agent',
  'Yard Agent',
  'Recovery Agent',
  'Execution Agent',
]

export const DEFAULT_OBJECTIVES: Record<AgentName, string> = {
  'Coordinator Agent': 'Interpret the alert, delegate work, and reconcile evidence.',
  'Impact Agent': 'Classify onward connections and cargo urgency.',
  'Yard Agent': 'Forecast yard occupancy and reefer plug capacity.',
  'Recovery Agent': 'Generate and revise three validated recovery plans.',
  'Execution Agent': 'Prepare validated mocked actions after approval.',
}

export interface AgentView {
  agent: AgentName
  status: AgentStatus
  objective: string
  confidence: TraceEvent['confidence']
  parallelGroup: string | null
  lastSummary: string | null
  result: string | null
  nextHandoff: AgentName | null
  toolsCalled: string[]
  inputSummaries: string[]
  evidence: string[]
  assumptions: string[]
  handoffNotes: string[]
  elapsedMs: number
  eventCount: number
}

/**
 * Merge trace events with any AgentActivity records from the polled workflow
 * state into one per-agent view. Trace events are the primary live source;
 * activities fill status and objective when present.
 */
export function deriveAgentViews(
  events: TraceEvent[],
  activities: AgentActivity[] | undefined,
): AgentView[] {
  const byAgent = new Map<AgentName, AgentView>()
  for (const agent of AGENT_ORDER) {
    byAgent.set(agent, {
      agent,
      status: 'WAITING',
      objective: DEFAULT_OBJECTIVES[agent],
      confidence: null,
      parallelGroup: null,
      lastSummary: null,
      result: null,
      nextHandoff: null,
      toolsCalled: [],
      inputSummaries: [],
      evidence: [],
      assumptions: [],
      handoffNotes: [],
      elapsedMs: 0,
      eventCount: 0,
    })
  }

  for (const activity of activities ?? []) {
    const view = byAgent.get(activity.agent)
    if (!view) continue
    view.status = activity.status
    view.objective = activity.objective || view.objective
    view.confidence = activity.confidence ?? view.confidence
    view.lastSummary = activity.last_summary ?? view.lastSummary
  }

  for (const event of events) {
    if (!event.agent) continue
    const view = byAgent.get(event.agent)
    if (!view) continue

    view.eventCount += 1
    if (event.objective) view.objective = event.objective
    if (event.confidence) view.confidence = event.confidence
    if (event.parallel_group) view.parallelGroup = event.parallel_group
    if (event.input_summary) view.inputSummaries.push(event.input_summary)
    if (event.tool && !view.toolsCalled.includes(event.tool)) view.toolsCalled.push(event.tool)
    if (event.result) {
      view.evidence.push(event.result)
      view.result = event.result
    }
    if (event.decision_summary) view.lastSummary = event.decision_summary
    for (const assumption of event.assumptions ?? []) {
      if (!view.assumptions.includes(assumption)) view.assumptions.push(assumption)
    }
    if (event.elapsed_ms != null) view.elapsedMs += event.elapsed_ms
    if (event.next_handoff) {
      view.nextHandoff = event.next_handoff
      const note = `${event.kind === 'HANDOFF' ? 'Handoff' : 'Next'}: ${event.next_handoff}`
      if (view.handoffNotes.at(-1) !== note) view.handoffNotes.push(note)
    }

    switch (event.kind) {
      case 'AGENT_STARTED':
        view.status = 'RUNNING'
        break
      case 'TOOL_CALLED':
        if (view.status === 'WAITING') view.status = 'RUNNING'
        break
      case 'AGENT_COMPLETED':
        view.status = 'COMPLETED'
        break
      case 'DISPUTE_OPENED':
        view.status = 'BLOCKED'
        break
      case 'HUMAN_DECISION':
        if (view.status === 'BLOCKED') view.status = 'RUNNING'
        break
      case 'ERROR':
        if (event.error) view.status = 'FAILED'
        break
      default:
        break
    }
  }

  // Agents whose last event handed off to someone else and produced a result
  // are effectively done even without an explicit AGENT_COMPLETED event.
  const last = events.at(-1)
  for (const view of byAgent.values()) {
    if (
      view.status === 'RUNNING' &&
      view.result !== null &&
      last?.agent !== view.agent &&
      view.nextHandoff !== null &&
      view.nextHandoff !== view.agent
    ) {
      view.status = 'COMPLETED'
    }
  }

  return AGENT_ORDER.map((agent) => byAgent.get(agent) as AgentView)
}

export interface StatusTotals {
  safe: number
  atRisk: number
  missed: number
  resolved: number
}

/** Sum grouped container counts by connection status. */
export function groupTotals(analysis: ConnectionAnalysis): StatusTotals {
  const totals: StatusTotals = { safe: 0, atRisk: 0, missed: 0, resolved: 0 }
  for (const group of analysis.groups) {
    if (group.status === 'SAFE') totals.safe += group.container_count
    else if (group.status === 'AT_RISK') totals.atRisk += group.container_count
    else if (group.status === 'MISSED') totals.missed += group.container_count
    else totals.resolved += group.container_count
  }
  return totals
}

/** Highest peak occupancy across blocks, as a percentage of block capacity. */
export function yardPeakPercent(yard: YardForecast): number {
  let peak = 0
  for (const block of yard.blocks) {
    if (block.container_capacity <= 0) continue
    peak = Math.max(peak, (block.peak_occupancy / block.container_capacity) * 100)
  }
  return Math.round(peak)
}

export const STATUS_LABEL: Record<ConnectionStatus, string> = {
  SAFE: 'SAFE',
  AT_RISK: 'AT RISK',
  MISSED: 'MISSED',
  RESOLVED: 'RESOLVED',
}

export const CARGO_LABEL: Record<string, string> = {
  PHARMA_REEFER: 'Pharma reefer',
  TIME_CRITICAL_MANUFACTURING: 'Time-critical mfg',
  GENERAL_DRY: 'General dry',
}
