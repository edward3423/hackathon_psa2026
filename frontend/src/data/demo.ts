import type {
  AlternativeSailingResult,
  ConnectionAnalysis,
  Dispute,
  MockedAction,
  PlanComparison,
  PriorityEmphasis,
  ScenarioState,
  TraceEvent,
  WorkflowStage,
  YardForecast,
} from '../api/types'

export type PageId =
  | 'overview'
  | 'connections'
  | 'yard'
  | 'reefers'
  | 'recovery'
  | 'agents'
  | 'execution'
  | 'replay'

export interface ScenarioPreset {
  id: string
  title: string
  summary: string
  delayHours: number
  priorityEmphasis: PriorityEmphasis
  lookupFailure: boolean
  affected: number
  atRisk: number
  expectedMisses: number
  yardPeak: number
  reeferDemand: number
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: 'moderate-delay',
    title: 'Moderate Delay',
    summary: 'A 6-hour arrival delay compresses two transfer windows.',
    delayHours: 6,
    priorityEmphasis: 'BALANCED',
    lookupFailure: false,
    affected: 438,
    atRisk: 42,
    expectedMisses: 8,
    yardPeak: 78,
    reeferDemand: 386,
  },
  {
    id: 'severe-delay',
    title: 'Severe Delay',
    summary: 'An 18-hour delay threatens three onward vessels and terminal capacity.',
    delayHours: 18,
    priorityEmphasis: 'BALANCED',
    lookupFailure: true,
    affected: 400,
    atRisk: 126,
    expectedMisses: 60,
    yardPeak: 94,
    reeferDemand: 432,
  },
  {
    id: 'reefer-crisis',
    title: 'Reefer Crisis',
    summary: 'Refrigerated cargo demand is forecast to exceed available plugs.',
    delayHours: 14,
    priorityEmphasis: 'CARGO_PROTECTION',
    lookupFailure: false,
    affected: 472,
    atRisk: 151,
    expectedMisses: 41,
    yardPeak: 89,
    reeferDemand: 468,
  },
  {
    id: 'yard-congestion',
    title: 'Yard Congestion',
    summary: 'Overlapping vessel calls push two yard blocks beyond safe occupancy.',
    delayHours: 12,
    priorityEmphasis: 'CONGESTION_REDUCTION',
    lookupFailure: false,
    affected: 510,
    atRisk: 118,
    expectedMisses: 29,
    yardPeak: 99,
    reeferDemand: 409,
  },
  {
    id: 'agent-conflict',
    title: 'Agent Conflict',
    summary: 'Cargo protection and yard capacity recommendations cannot both be satisfied.',
    delayHours: 18,
    priorityEmphasis: 'CARGO_PROTECTION',
    lookupFailure: false,
    affected: 438,
    atRisk: 127,
    expectedMisses: 34,
    yardPeak: 92,
    reeferDemand: 439,
  },
  {
    id: 'lookup-failure',
    title: 'Lookup Failure',
    summary: 'The onward sailing lookup times out and cached data is used.',
    delayHours: 18,
    priorityEmphasis: 'BALANCED',
    lookupFailure: true,
    affected: 400,
    atRisk: 126,
    expectedMisses: 60,
    yardPeak: 94,
    reeferDemand: 432,
  },
]

export const FALLBACK_SCENARIO: ScenarioState = {
  name: 'MV ATLAS STAR 18-hour delay',
  description: 'A synthetic inbound vessel delay threatens three onward connections.',
  alert: {
    vessel_name: 'MV ATLAS STAR',
    port_call: 'SGSIN-PSA-2042',
    original_eta: '2026-09-14T06:00:00Z',
    revised_eta: '2026-09-15T00:00:00Z',
    event_time: '2026-09-13T18:00:00Z',
    synthetic: true,
    delay_hours: 18,
  },
  objective:
    'Protect critical cargo, reduce missed connections, avoid severe yard congestion, and minimize illustrative disruption cost.',
  planning_horizon_hours: 72,
  controls: {
    delay_hours: 18,
    priority_emphasis: 'BALANCED',
    alternative_sailing_failure: true,
  },
  synthetic_notice:
    'All vessels, containers, capacity values, costs, and actions are synthetic or illustrative.',
}

export interface PortVessel {
  id: string
  name: string
  role: 'INBOUND' | 'OUTBOUND'
  berth: string
  eta: string
  departure: string
  containers: number
  connections: number
  risk: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  x: number
  y: number
}

export const PORT_VESSELS: PortVessel[] = [
  {
    id: 'SGSIN-PSA-2042',
    name: 'MV ATLAS STAR',
    role: 'INBOUND',
    berth: 'T1 B06',
    eta: '15 Sep, 00:00 UTC',
    departure: '15 Sep, 16:00 UTC',
    containers: 1284,
    connections: 438,
    risk: 'CRITICAL',
    x: 18,
    y: 43,
  },
  {
    id: 'SGSIN-PSA-2043',
    name: 'MV MERIDIAN WAVE',
    role: 'OUTBOUND',
    berth: 'T1 B03',
    eta: '14 Sep, 20:00 UTC',
    departure: '15 Sep, 10:00 UTC',
    containers: 208,
    connections: 118,
    risk: 'HIGH',
    x: 36,
    y: 21,
  },
  {
    id: 'SGSIN-PSA-2044',
    name: 'MV CORAL EMPRESS',
    role: 'OUTBOUND',
    berth: 'T1 B04',
    eta: '15 Sep, 04:00 UTC',
    departure: '15 Sep, 18:00 UTC',
    containers: 146,
    connections: 86,
    risk: 'HIGH',
    x: 36,
    y: 47,
  },
  {
    id: 'SGSIN-PSA-2045',
    name: 'MV PACIFIC HARRIER',
    role: 'OUTBOUND',
    berth: 'T1 B07',
    eta: '15 Sep, 08:00 UTC',
    departure: '15 Sep, 22:00 UTC',
    containers: 164,
    connections: 74,
    risk: 'MEDIUM',
    x: 36,
    y: 72,
  },
]

const CONNECTIONS: ConnectionAnalysis['connections'] = [
  {
    container_id: 'CASU0000042',
    cargo_type: 'PHARMA_REEFER',
    onward_vessel: 'MV MERIDIAN WAVE',
    ready_time: '2026-09-15T05:10:00Z',
    connection_cutoff: '2026-09-15T04:00:00Z',
    margin_hours: -1.2,
    status: 'MISSED',
    priority_rank: 1,
    priority_reason: 'Temperature-controlled medicine with no safe dwell extension.',
  },
  {
    container_id: 'CASU0000087',
    cargo_type: 'PHARMA_REEFER',
    onward_vessel: 'MV MERIDIAN WAVE',
    ready_time: '2026-09-15T03:42:00Z',
    connection_cutoff: '2026-09-15T04:00:00Z',
    margin_hours: 0.3,
    status: 'AT_RISK',
    priority_rank: 1,
    priority_reason: 'Medicine reefer has an 18-minute operating margin.',
  },
  {
    container_id: 'CASU0000119',
    cargo_type: 'TIME_CRITICAL_MANUFACTURING',
    onward_vessel: 'MV MERIDIAN WAVE',
    ready_time: '2026-09-15T04:34:00Z',
    connection_cutoff: '2026-09-15T04:00:00Z',
    margin_hours: -0.6,
    status: 'MISSED',
    priority_rank: 2,
    priority_reason: 'Production-line components have a committed delivery window.',
  },
  {
    container_id: 'CASU0000148',
    cargo_type: 'TIME_CRITICAL_MANUFACTURING',
    onward_vessel: 'MV CORAL EMPRESS',
    ready_time: '2026-09-15T11:21:00Z',
    connection_cutoff: '2026-09-15T12:00:00Z',
    margin_hours: 0.7,
    status: 'AT_RISK',
    priority_rank: 2,
    priority_reason: 'Transfer margin is below the 90-minute reliability buffer.',
  },
  {
    container_id: 'CASU0000176',
    cargo_type: 'GENERAL_DRY',
    onward_vessel: 'MV CORAL EMPRESS',
    ready_time: '2026-09-15T09:05:00Z',
    connection_cutoff: '2026-09-15T12:00:00Z',
    margin_hours: 2.9,
    status: 'SAFE',
    priority_rank: 3,
    priority_reason: 'Standard cargo retains more than two hours of transfer margin.',
  },
  {
    container_id: 'CASU0000204',
    cargo_type: 'PHARMA_REEFER',
    onward_vessel: 'MV CORAL EMPRESS',
    ready_time: '2026-09-15T12:18:00Z',
    connection_cutoff: '2026-09-15T12:00:00Z',
    margin_hours: -0.3,
    status: 'MISSED',
    priority_rank: 1,
    priority_reason: 'Critical reefer reaches the transfer lane after cutoff.',
  },
  {
    container_id: 'CASU0000231',
    cargo_type: 'GENERAL_DRY',
    onward_vessel: 'MV PACIFIC HARRIER',
    ready_time: '2026-09-15T13:15:00Z',
    connection_cutoff: '2026-09-15T16:00:00Z',
    margin_hours: 2.8,
    status: 'SAFE',
    priority_rank: 3,
    priority_reason: 'Transfer window remains above the safe operating buffer.',
  },
  {
    container_id: 'CASU0000266',
    cargo_type: 'TIME_CRITICAL_MANUFACTURING',
    onward_vessel: 'MV PACIFIC HARRIER',
    ready_time: '2026-09-15T15:12:00Z',
    connection_cutoff: '2026-09-15T16:00:00Z',
    margin_hours: 0.8,
    status: 'AT_RISK',
    priority_rank: 2,
    priority_reason: 'Crane availability could consume the remaining 48 minutes.',
  },
  {
    container_id: 'CASU0000312',
    cargo_type: 'GENERAL_DRY',
    onward_vessel: 'MV JADE HORIZON',
    ready_time: '2026-09-16T09:10:00Z',
    connection_cutoff: '2026-09-16T18:00:00Z',
    margin_hours: 8.8,
    status: 'SAFE',
    priority_rank: 3,
    priority_reason: 'Later sailing leaves a wide transfer window.',
  },
]

export const MOCK_CONNECTION_ANALYSIS: ConnectionAnalysis = {
  delay_hours: 18,
  safe_count: 214,
  at_risk_count: 126,
  missed_count: 60,
  groups: [
    {
      onward_vessel: 'MV MERIDIAN WAVE',
      cargo_type: 'PHARMA_REEFER',
      status: 'AT_RISK',
      container_count: 40,
    },
    {
      onward_vessel: 'MV MERIDIAN WAVE',
      cargo_type: 'TIME_CRITICAL_MANUFACTURING',
      status: 'MISSED',
      container_count: 60,
    },
    {
      onward_vessel: 'MV CORAL EMPRESS',
      cargo_type: 'GENERAL_DRY',
      status: 'AT_RISK',
      container_count: 86,
    },
    {
      onward_vessel: 'MV PACIFIC HARRIER',
      cargo_type: 'GENERAL_DRY',
      status: 'SAFE',
      container_count: 214,
    },
  ],
  connections: CONNECTIONS,
}

const hour = (offset: number) =>
  new Date(Date.parse('2026-09-13T18:00:00Z') + offset * 3_600_000).toISOString()

function block(
  blockId: string,
  capacity: number,
  values: number[],
): YardForecast['blocks'][number] {
  const offsets = [0, 6, 12, 24, 36, 48, 60, 72]
  const peak = Math.max(...values)
  return {
    block_id: blockId,
    container_capacity: capacity,
    series: values.map((occupancy, index) => ({
      time: hour(offsets[index]),
      occupancy,
      congested: occupancy / capacity >= 0.85,
      full: occupancy >= capacity,
    })),
    peak_occupancy: peak,
    peak_time: hour(offsets[values.indexOf(peak)]),
  }
}

export const MOCK_YARD_FORECAST: YardForecast = {
  horizon_hours: 72,
  blocks: [
    block('YB1', 480, [310, 332, 358, 402, 438, 421, 388, 354]),
    block('YB2', 500, [320, 341, 376, 419, 472, 448, 405, 372]),
    block('YB3', 460, [280, 315, 352, 398, 460, 446, 399, 361]),
    block('YB4', 520, [330, 344, 362, 401, 429, 412, 386, 358]),
  ],
  reefer_shortages: [
    {
      block_id: 'YB3',
      start_time: '2026-09-14T06:00:00Z',
      required_plugs: 176,
      available_plugs: 150,
    },
  ],
}

export const MOCK_PLANNED_YARD: YardForecast = {
  horizon_hours: 72,
  blocks: [
    block('YB1', 480, [310, 328, 349, 379, 401, 388, 362, 340]),
    block('YB2', 500, [320, 337, 361, 394, 420, 409, 381, 356]),
    block('YB3', 460, [280, 306, 331, 365, 386, 372, 349, 329]),
    block('YB4', 520, [330, 343, 356, 382, 401, 390, 369, 348]),
  ],
  reefer_shortages: [],
}

const metrics = (
  total: number,
  missedConnections: number,
  protectedPct: number,
  yardPeakPct: number,
  maxDelayHours: number,
) => ({
  cost: {
    total,
    illustrative: true,
    components: [
      { name: 'Rehandling', amount: Math.round(total * 0.42), basis: 'Synthetic moves' },
      { name: 'Rebooking', amount: Math.round(total * 0.33), basis: 'Synthetic carrier fees' },
      { name: 'Dwell', amount: Math.round(total * 0.25), basis: 'Synthetic storage hours' },
    ],
  },
  missed_connections: missedConnections,
  critical_cargo_protected_pct: protectedPct,
  yard_peak_occupancy_pct: yardPeakPct,
  max_additional_delay_hours: maxDelayHours,
})

export const MOCK_PLAN_COMPARISON: PlanComparison = {
  evaluations: [
    {
      plan: {
        archetype: 'AGGRESSIVE_RUSH',
        title: 'Aggressive Rush',
        assumptions: ['Priority transfer lanes remain available for six hours.'],
        actions: [
          {
            action: 'RUSH',
            onward_vessel: 'MV MERIDIAN WAVE',
            cargo_type: 'PHARMA_REEFER',
            container_count: 60,
            target_sailing: 'MV MERIDIAN WAVE',
            rationale: 'Preserve the original connection for critical reefers.',
          },
        ],
      },
      metrics: metrics(184000, 8, 100, 92, 3.1),
      feasible: false,
      rejection_reasons: ['Peak reefer demand leaves less than the required reserve.'],
    },
    {
      plan: {
        archetype: 'STANDARD_REBOOK',
        title: 'Standard Rebooking',
        assumptions: ['Cached alternative sailing capacity remains valid.'],
        actions: [
          {
            action: 'REBOOK',
            onward_vessel: 'MV MERIDIAN WAVE',
            cargo_type: 'GENERAL_DRY',
            container_count: 84,
            target_sailing: 'MV NOVA CREST',
            rationale: 'Move lower-priority cargo to the next available sailing.',
          },
        ],
      },
      metrics: metrics(91000, 31, 78, 81, 12.4),
      feasible: true,
      rejection_reasons: [],
    },
    {
      plan: {
        archetype: 'OPTIMIZED_HYBRID',
        title: 'Optimized Hybrid',
        assumptions: ['Physical reefer plug capacity is the governing constraint.'],
        actions: [
          {
            action: 'RUSH',
            onward_vessel: 'MV MERIDIAN WAVE',
            cargo_type: 'PHARMA_REEFER',
            container_count: 42,
            target_sailing: 'MV MERIDIAN WAVE',
            rationale: 'Protect medicine cargo within the available plug reserve.',
          },
          {
            action: 'REBOOK',
            onward_vessel: 'MV CORAL EMPRESS',
            cargo_type: 'GENERAL_DRY',
            container_count: 58,
            target_sailing: 'MV BALTIC SPRING',
            rationale: 'Reduce yard pressure without displacing critical cargo.',
          },
        ],
      },
      metrics: metrics(126000, 14, 96, 84, 6.2),
      feasible: true,
      rejection_reasons: [],
    },
  ],
  recommended: 'OPTIMIZED_HYBRID',
  rationale:
    'The hybrid plan protects medicine cargo and keeps both yard occupancy and reefer demand below operating limits.',
  confidence: 'MEDIUM',
}

export const MOCK_SAILINGS: AlternativeSailingResult = {
  status: 'TIMEOUT_CACHED_FALLBACK',
  stale_notice: 'Schedule lookup timed out. Cached data is 34 minutes old.',
  sailings: [
    {
      vessel_name: 'MV NOVA CREST',
      replaces_onward_vessel: 'MV MERIDIAN WAVE',
      departs: '2026-09-16T20:00:00Z',
      connection_cutoff: '2026-09-16T14:00:00Z',
      available_capacity: 70,
    },
    {
      vessel_name: 'MV BALTIC SPRING',
      replaces_onward_vessel: 'MV CORAL EMPRESS',
      departs: '2026-09-17T06:00:00Z',
      connection_cutoff: '2026-09-17T00:00:00Z',
      available_capacity: 60,
    },
  ],
}

export const MOCK_DISPUTE: Dispute = {
  dispute_id: 'demo-dispute-1',
  question: 'Should the plan protect original connections or preserve the safe reefer reserve?',
  positions: [
    {
      agent: 'Impact Agent',
      position: 'Rush all 60 pharmaceutical reefers to protect their original connections.',
      evidence: ['This prevents 18 additional critical-cargo misses.'],
    },
    {
      agent: 'Yard Agent',
      position: 'Respect physical reefer plug capacity',
      evidence: ['The rush plan needs 176 plugs in YB3, but only 150 are available.'],
    },
  ],
  confirmed_constraint: null,
  resolved_by_human: false,
}

export const MOCK_ACTIONS: MockedAction[] = [
  {
    action_id: 'WO-84217',
    action_type: 'TERMINAL_WORK_ORDER',
    plan_archetype: 'OPTIMIZED_HYBRID',
    description: 'Move CASU0000042 from YB3 to Priority Transfer Lane 3.',
    payload_summary: 'Critical medicine reefer, simulated terminal move only.',
  },
  {
    action_id: 'RC-84218',
    action_type: 'REEFER_CHECK',
    plan_archetype: 'OPTIMIZED_HYBRID',
    description: 'Assign CASU0000042 to reefer rack R14.',
    payload_summary: 'Power available, validation passed in mock environment.',
  },
  {
    action_id: 'CN-84219',
    action_type: 'CARRIER_NOTICE',
    plan_archetype: 'OPTIMIZED_HYBRID',
    description: 'Notify synthetic carrier of 14 reassigned containers.',
    payload_summary: 'Message recorded locally, no external system contacted.',
  },
]

export const MOCK_RECEIPTS = MOCK_ACTIONS.map((action, index) => ({
  action_id: action.action_id,
  status: 'ACCEPTED' as const,
  receipt_ref: `MOCK-${2042 + index}`,
  detail: `${action.description} Completed in simulation mode.`,
}))

export interface OfflineStep {
  delayMs: number
  stage: WorkflowStage
  event: Omit<TraceEvent, 'event_id' | 'sequence' | 'timestamp'>
}

export const OFFLINE_OPENING_STEPS: OfflineStep[] = [
  {
    delayMs: 120,
    stage: 'ASSESSING',
    event: {
      kind: 'RUN_STARTED',
      stage: 'ASSESSING',
      agent: 'Coordinator Agent',
      objective: 'Assess the synthetic vessel delay and coordinate specialist analysis.',
      decision_summary: 'Parallel impact and yard analysis requested.',
      confidence: 'HIGH',
      assumptions: [],
      next_handoff: 'Impact Agent',
    },
  },
  {
    delayMs: 420,
    stage: 'ASSESSING',
    event: {
      kind: 'TOOL_CALLED',
      stage: 'ASSESSING',
      agent: 'Impact Agent',
      tool: 'calculate_connection_risk()',
      input_summary: '400 synthetic transshipment containers',
      result: '126 at risk and 60 expected misses.',
      confidence: 'HIGH',
      assumptions: [],
      parallel_group: 'impact-yard',
    },
  },
  {
    delayMs: 760,
    stage: 'ASSESSING',
    event: {
      kind: 'TOOL_CALLED',
      stage: 'ASSESSING',
      agent: 'Yard Agent',
      tool: 'forecast_yard_and_reefer()',
      input_summary: '72-hour synthetic terminal horizon',
      result: 'YB3 reaches capacity and reefer demand exceeds the safe reserve.',
      confidence: 'HIGH',
      assumptions: [],
      parallel_group: 'impact-yard',
    },
  },
  {
    delayMs: 1120,
    stage: 'DISPUTE',
    event: {
      kind: 'DISPUTE_OPENED',
      stage: 'DISPUTE',
      agent: 'Coordinator Agent',
      decision_summary: 'Cargo protection conflicts with the physical reefer plug limit.',
      confidence: 'LOW',
      assumptions: [],
    },
  },
]
