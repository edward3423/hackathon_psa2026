import type {
  ConnectionAnalysis,
  Dispute,
  PlanComparison,
  RunCreated,
  RunMode,
  ScenarioState,
  TraceEvent,
  WorkflowState,
  YardForecast,
} from '../api/types'

export const scenario: ScenarioState = {
  name: 'MV ATLAS STAR 18-hour delay',
  description: 'A synthetic delay threatens onward connections.',
  alert: {
    vessel_name: 'MV ATLAS STAR',
    port_call: 'SGSIN-PSA-2042',
    original_eta: '2026-09-14T06:00:00Z',
    revised_eta: '2026-09-15T00:00:00Z',
    event_time: '2026-09-13T18:00:00Z',
    synthetic: true,
    delay_hours: 18,
  },
  objective: 'Protect critical cargo and reduce missed connections.',
  planning_horizon_hours: 72,
  controls: {
    delay_hours: 18,
    priority_emphasis: 'BALANCED',
    alternative_sailing_failure: true,
  },
  synthetic_notice: 'All values are synthetic.',
}

export function runCreated(mode: RunMode = 'LIVE_STUB'): RunCreated {
  return {
    run_id: 'run-1',
    mode,
    stage: 'READY',
    events_url: '/api/runs/run-1/events',
  }
}

let sequence = 0

export function traceEvent(overrides: Partial<TraceEvent>): TraceEvent {
  sequence += 1
  return {
    event_id: `evt-${sequence}`,
    sequence,
    timestamp: '2026-09-13T18:00:01Z',
    kind: 'AGENT_STARTED',
    stage: 'ASSESSING',
    agent: 'Coordinator Agent',
    assumptions: [],
    ...overrides,
  }
}

export function resetSequence(): void {
  sequence = 0
}

export const analysis: ConnectionAnalysis = {
  delay_hours: 18,
  safe_count: 214,
  at_risk_count: 126,
  missed_count: 60,
  groups: [
    { onward_vessel: 'MV PACIFIC LINK', cargo_type: 'PHARMA_REEFER', status: 'AT_RISK', container_count: 40 },
    { onward_vessel: 'MV PACIFIC LINK', cargo_type: 'GENERAL_DRY', status: 'SAFE', container_count: 100 },
    { onward_vessel: 'MV MERIDIAN', cargo_type: 'TIME_CRITICAL_MANUFACTURING', status: 'MISSED', container_count: 60 },
    { onward_vessel: 'MV MERIDIAN', cargo_type: 'GENERAL_DRY', status: 'SAFE', container_count: 114 },
    { onward_vessel: 'MV CORAL GATE', cargo_type: 'GENERAL_DRY', status: 'AT_RISK', container_count: 86 },
  ],
  connections: [],
}

export const baselineYard: YardForecast = {
  horizon_hours: 72,
  blocks: [
    {
      block_id: 'A',
      container_capacity: 100,
      series: [
        { time: '2026-09-13T18:00:00Z', occupancy: 60, congested: false, full: false },
        { time: '2026-09-14T18:00:00Z', occupancy: 94, congested: true, full: false },
        { time: '2026-09-15T18:00:00Z', occupancy: 70, congested: false, full: false },
      ],
      peak_occupancy: 94,
      peak_time: '2026-09-14T18:00:00Z',
    },
  ],
  reefer_shortages: [
    {
      block_id: 'A',
      start_time: '2026-09-14T06:00:00Z',
      required_plugs: 176,
      available_plugs: 150,
    },
  ],
}

function metrics(cost: number, missed: number, protectedPct: number, yardPct: number, delay: number) {
  return {
    cost: { components: [], total: cost, illustrative: true },
    missed_connections: missed,
    critical_cargo_protected_pct: protectedPct,
    yard_peak_occupancy_pct: yardPct,
    max_additional_delay_hours: delay,
  }
}

export const planComparison: PlanComparison = {
  evaluations: [
    {
      plan: { archetype: 'AGGRESSIVE_RUSH', title: 'Rush all threatened cargo', actions: [], assumptions: [] },
      metrics: metrics(410000, 12, 100, 97, 6),
      feasible: false,
      rejection_reasons: ['Exceeds available reefer plugs.'],
    },
    {
      plan: { archetype: 'STANDARD_REBOOK', title: 'Rebook to later sailings', actions: [], assumptions: [] },
      metrics: metrics(295000, 48, 62, 88, 30),
      feasible: true,
      rejection_reasons: [],
    },
    {
      plan: { archetype: 'OPTIMIZED_HYBRID', title: 'Rush critical, rebook the rest', actions: [], assumptions: [] },
      metrics: metrics(318000, 24, 96, 91, 18),
      feasible: true,
      rejection_reasons: [],
    },
  ],
  recommended: 'OPTIMIZED_HYBRID',
  rationale: 'Hybrid protects critical cargo within plug capacity at moderate cost.',
  confidence: 'MEDIUM',
}

export const dispute: Dispute = {
  dispute_id: 'disp-1',
  question: 'Which constraint governs reefer handling?',
  positions: [
    {
      agent: 'Impact Agent',
      position: 'Rush all 60 pharmaceutical reefers to protect connections.',
      evidence: ['60 reefers miss their connection without rushing.'],
    },
    {
      agent: 'Yard Agent',
      position: 'Stay within 150 available reefer plugs.',
      evidence: ['Rushing all reefers needs 176 plugs; only 150 exist.'],
    },
  ],
  confirmed_constraint: null,
  resolved_by_human: false,
}

export function workflowState(overrides: Partial<WorkflowState> = {}): WorkflowState {
  return {
    run_id: 'run-1',
    mode: 'LIVE_STUB',
    stage: 'ASSESSING',
    scenario,
    activities: [],
    trace: [],
    active_dispute: null,
    results: null,
    ...overrides,
  }
}
