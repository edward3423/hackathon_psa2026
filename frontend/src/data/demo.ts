import type {
  AlternativeSailingResult,
  AnchorComparison,
  ArmResult,
  BenchmarkResult,
  ConnectionAnalysis,
  DailyKpi,
  Dispute,
  FleetArm,
  FleetMetrics,
  MockedAction,
  PlanComparison,
  PriorityEmphasis,
  RecordedDecision,
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
  | 'benchmark'
  | 'system'

/**
 * A named starting position for the scenario controls, and nothing more.
 *
 * A preset used to carry its own container, risk, yard and reefer figures.
 * They were hand-written, they disagreed with what the engine actually
 * produced, and the run overwrote them the moment it started. The expected
 * figures now come from `scenarioPreview()`, computed by the engine for
 * whatever the controls currently say - including after the delay slider moves,
 * which a per-preset constant could never follow.
 */
export interface ScenarioPreset {
  id: string
  title: string
  summary: string
  delayHours: number
  priorityEmphasis: PriorityEmphasis
  lookupFailure: boolean
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: 'moderate-delay',
    title: 'Moderate Delay',
    summary: 'A 6-hour arrival delay compresses two transfer windows.',
    delayHours: 6,
    priorityEmphasis: 'BALANCED',
    lookupFailure: false,
  },
  {
    id: 'severe-delay',
    title: 'Severe Delay',
    summary: 'An 18-hour delay threatens three onward vessels and terminal capacity.',
    delayHours: 18,
    priorityEmphasis: 'BALANCED',
    lookupFailure: true,
  },
  {
    id: 'reefer-crisis',
    title: 'Reefer Crisis',
    summary: 'Refrigerated cargo demand is forecast to exceed available plugs.',
    delayHours: 14,
    priorityEmphasis: 'CARGO_PROTECTION',
    lookupFailure: false,
  },
  {
    id: 'yard-congestion',
    title: 'Yard Congestion',
    summary: 'Overlapping vessel calls push two yard blocks beyond safe occupancy.',
    delayHours: 12,
    priorityEmphasis: 'CONGESTION_REDUCTION',
    lookupFailure: false,
  },
  {
    id: 'agent-conflict',
    title: 'Agent Conflict',
    summary: 'Cargo protection and yard capacity recommendations cannot both be satisfied.',
    delayHours: 18,
    priorityEmphasis: 'CARGO_PROTECTION',
    lookupFailure: false,
  },
  {
    id: 'lookup-failure',
    title: 'Lookup Failure',
    summary: 'The onward sailing lookup times out and cached data is used.',
    delayHours: 18,
    priorityEmphasis: 'BALANCED',
    lookupFailure: true,
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
}

/**
 * The port call as fixtures/golden_world.json models it. `connections` is the
 * count of transshipment containers moving off MV ATLAS STAR onto that vessel,
 * so the vessel detail cannot disagree with the Command Center's own totals.
 */
export const PORT_VESSELS: PortVessel[] = [
  {
    id: 'SGSIN-PSA-2042',
    name: 'MV ATLAS STAR',
    role: 'INBOUND',
    berth: 'T1 B06',
    eta: '2026-09-15T00:00:00Z',
    departure: '2026-09-15T16:00:00Z',
    containers: 1284,
    connections: 360,
    risk: 'CRITICAL',
  },
  {
    id: 'SGSIN-PSA-2043',
    name: 'MV MERIDIAN WAVE',
    role: 'OUTBOUND',
    berth: 'T1 B03',
    eta: '2026-09-14T20:00:00Z',
    departure: '2026-09-15T10:00:00Z',
    containers: 208,
    connections: 105,
    risk: 'HIGH',
  },
  {
    id: 'SGSIN-PSA-2044',
    name: 'MV CORAL EMPRESS',
    role: 'OUTBOUND',
    berth: 'T1 B04',
    eta: '2026-09-15T04:00:00Z',
    departure: '2026-09-15T18:00:00Z',
    containers: 146,
    connections: 105,
    risk: 'HIGH',
  },
  {
    id: 'SGSIN-PSA-2045',
    name: 'MV PACIFIC HARRIER',
    role: 'OUTBOUND',
    berth: 'T1 B07',
    eta: '2026-09-15T08:00:00Z',
    departure: '2026-09-15T22:00:00Z',
    containers: 164,
    connections: 90,
    risk: 'MEDIUM',
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

// --- Act 2 offline fallback -------------------------------------------------
//
// The Crisis Benchmark page has to stay legible when the API is unreachable
// (the same offline-fallback convention as the mocks above). These curves are
// hand-shaped illustrations, not the simulator's output: the page labels itself
// OFFLINE ILLUSTRATION whenever it is showing them, and the real run replaces
// every figure the moment the backend answers.
//
// The shapes are kept in the same relation as the real benchmark's: the
// reconstructed 2024 curve peaks at 7 days, and the two simulated arms peak
// far below it because the recorded arrival stream measures throughput, which
// congestion suppresses. An offline mock that had the simulation matching the
// recorded peak would rehearse a claim the benchmark explicitly does not make.

/** The honesty statement the backend attaches to every result, mirrored here. */
const BENCHMARK_NOTICE =
  'A controlled policy comparison, not a reproduction of history. The reactive baseline ' +
  'and CASCADE arms are discrete-event simulations of the recorded 2024 arrival stream, ' +
  'run blind: no arm can read a day it has not yet reached. They share one world, one ' +
  'calibration and one stream, and differ only in policy, so the comparison between them ' +
  'is the result this benchmark stands behind. The recorded arm is a reconstruction, not a ' +
  'measurement. The simulation does not reproduce the recorded 2024 congestion and is not ' +
  'claimed to: the recorded daily port calls and volumes measure throughput, ' +
  'which congestion suppresses. The recorded anchors are published alongside the simulated ' +
  'figures so that gap stays visible.'

/**
 * Shown in place of the backend's playback notice when the API is unreachable.
 * Kept separate from `BenchmarkResult.notice`: one says how the curves were
 * obtained, the other says what the benchmark does and does not claim.
 */
export const OFFLINE_BENCHMARK_NOTICE =
  'OFFLINE ILLUSTRATION. The API is unreachable, so these curves are hand-shaped ' +
  'placeholders, not simulator output.'

const BENCHMARK_DAYS = 153
const BENCHMARK_START = Date.UTC(2024, 3, 1)

interface ArmShape {
  arm: FleetArm
  label: string
  base: number
  peak: number
  /** Level the curve decays towards after the peak. */
  settle: number
  peakDay: number
  riseWidth: number
  fallWidth: number
}

const BENCHMARK_SHAPES: ArmShape[] = [
  {
    arm: 'HISTORICAL',
    label: 'Recorded 2024 (reconstructed)',
    base: 0.4,
    peak: 7.0,
    settle: 0.9,
    peakDay: 55,
    riseWidth: 16,
    fallWidth: 22,
  },
  {
    // The reactive arm never adds capacity, so it plateaus instead of
    // recovering. Its peak is nowhere near the reconstructed 7 days.
    arm: 'REACTIVE_BASELINE',
    label: 'Reactive baseline',
    base: 0.4,
    peak: 2.02,
    settle: 2.02,
    peakDay: 60,
    riseWidth: 18,
    fallWidth: 30,
  },
  {
    arm: 'CASCADE_AGENTIC',
    label: 'CASCADE agentic',
    base: 0.4,
    peak: 1.55,
    settle: 0.5,
    peakDay: 52,
    riseWidth: 15,
    fallWidth: 14,
  },
]

/** The controller reviews policy weekly, so most epochs end in a HOLD. */
const CASCADE_EPOCH_DAYS = 7
const RESERVE_DECISION_DAY = 28
/** Conservative Keppel reactivation lead, the same one the engine enforces. */
const RESERVE_LEAD_DAYS = 14
const RESERVE_EFFECTIVE_DAY = RESERVE_DECISION_DAY + RESERVE_LEAD_DAYS

function benchmarkDate(index: number): string {
  return new Date(BENCHMARK_START + index * 86_400_000).toISOString().slice(0, 10)
}

function shapedWait(shape: ArmShape, index: number): number {
  const rising = index <= shape.peakDay
  const width = rising ? shape.riseWidth : shape.fallWidth
  const floor = rising ? shape.base : shape.settle
  const offset = index - shape.peakDay
  const bump = Math.exp(-(offset * offset) / (2 * width * width))
  return Number((floor + (shape.peak - floor) * bump).toFixed(2))
}

function mockDaily(shape: ArmShape): DailyKpi[] {
  return Array.from({ length: BENCHMARK_DAYS }, (_, index) => {
    const wait = shapedWait(shape, index)
    const queue = Math.round(wait * 12)
    return {
      date: benchmarkDate(index),
      day_index: index,
      arrivals: 14,
      berthings: 14,
      departures: 14,
      queue_length: queue,
      mean_wait_days: wait,
      rolling_wait_days: wait,
      // Derived from the reserve decision below rather than stated twice, so
      // the extra berths appear exactly when the mock says they were ordered.
      active_berths:
        shape.arm === 'CASCADE_AGENTIC' && index >= RESERVE_EFFECTIVE_DAY ? 46 : 42,
      teu_waiting: queue * 1500,
      utilisation: Number(Math.min(0.99, 0.72 + wait * 0.03).toFixed(2)),
    }
  })
}

/**
 * The offline demo used to drop the decision panel entirely, which read as
 * "CASCADE did nothing" rather than "the backend is unreachable". These are the
 * weekly epochs of the agentic arm: three levers and a HOLD on every other
 * week, the same shape the scripted controller produces on a real run.
 */
function mockDecisions(daily: DailyKpi[]): RecordedDecision[] {
  const decisions: RecordedDecision[] = []
  for (let index = 0; index < daily.length; index += CASCADE_EPOCH_DAYS) {
    const common = { date: daily[index].date, day_index: index, accepted: true, source: 'SCRIPTED' as const }
    if (index === RESERVE_DECISION_DAY) {
      decisions.push({
        ...common,
        agent: 'Yard Agent',
        decision: {
          type: 'ACTIVATE_RESERVE_BERTHS',
          tranche_id: 'keppel-reserve-1',
          rationale: `Rolling wait is climbing; ordering the Keppel tranche now so it is live in ${RESERVE_LEAD_DAYS} days.`,
        },
        effective_date: daily[RESERVE_EFFECTIVE_DAY].date,
      })
    } else if (index === 35) {
      decisions.push({
        ...common,
        agent: 'Recovery Agent',
        decision: {
          type: 'SET_QUEUE_DISCIPLINE',
          discipline: 'CONNECTION_WEIGHTED',
          rationale: 'Backlog is deep enough that connection risk, not arrival order, decides the cost of waiting.',
        },
      })
    } else if (index === 42) {
      decisions.push({
        ...common,
        agent: 'Execution Agent',
        decision: {
          type: 'FAST_CONNECTION_MODE',
          enabled: true,
          rationale: 'Transhipment boxes are missing their onward sailings; expedite delivery for the connection window.',
        },
      })
    } else {
      decisions.push({
        ...common,
        agent: 'Coordinator Agent',
        decision: { type: 'HOLD', rationale: 'Queue within tolerance; no lever justified this week.' },
      })
    }
  }
  return decisions
}

function mockMetrics(daily: DailyKpi[]): FleetMetrics {
  const peak = daily.reduce((best, day) =>
    day.rolling_wait_days > best.rolling_wait_days ? day : best,
  )
  // An arm that never crossed the two-day threshold has nothing to recover
  // from; reporting a recovery date for it would invent an event.
  const breached = daily.some((day) => day.rolling_wait_days > 2)
  const recovered = breached
    ? daily.find((day) => day.day_index > peak.day_index && day.rolling_wait_days <= 2)
    : undefined
  const mean = daily.reduce((total, day) => total + day.rolling_wait_days, 0) / daily.length
  return {
    peak_wait_days: peak.rolling_wait_days,
    peak_wait_date: peak.date,
    recovery_date: recovered?.date ?? null,
    days_above_two_day_wait: daily.filter((day) => day.rolling_wait_days > 2).length,
    mean_wait_days: Number(mean.toFixed(2)),
    mean_port_stay_hours: Number((28 + mean * 18).toFixed(1)),
    port_stay_inflation_pct: Number((mean * 14).toFixed(1)),
    vessels_served: 2142,
    teu_served: 17_400_000,
    missed_connection_proxy: Math.round(mean * 420),
    wait_cost_usd: Math.round(mean * 9_600_000),
  }
}

function mockArm(shape: ArmShape): ArmResult {
  const daily = mockDaily(shape)
  const historical = shape.arm === 'HISTORICAL'
  return {
    arm: shape.arm,
    label: shape.label,
    provenance: historical ? 'RECONSTRUCTED' : 'SIMULATED',
    is_simulation: !historical,
    daily,
    // The reconstruction is a wait curve and nothing else, so its port-stay
    // fields are left at zero exactly as the backend leaves them, rather than
    // shaped into a number no source supports.
    metrics: historical
      ? { ...mockMetrics(daily), mean_port_stay_hours: 0, port_stay_inflation_pct: 0 }
      : mockMetrics(daily),
    decisions: shape.arm === 'CASCADE_AGENTIC' ? mockDecisions(daily) : [],
    blind_audit: historical
      ? null
      : { total_reads: 153, max_lookahead_seconds: 0, violations: 0, verdict: 'PASS' },
    calibration: null,
    caveat: historical
      ? 'Reconstructed from IMF PortWatch daily port calls, anchored to published 2024 figures.'
      : null,
  }
}

/**
 * Recorded anchors held next to what the reactive baseline produced. Each row
 * carries the reason it lands where it does, written from the structure of the
 * model rather than from the numbers, so a row that happens to fall inside
 * tolerance still says why that is not agreement.
 */
function mockAnchors(baseline: ArmResult): AnchorComparison[] {
  const lastDay = baseline.daily[baseline.daily.length - 1]
  const rows: Array<Omit<AnchorComparison, 'within_tolerance'>> = [
    {
      anchor_key: 'peak_berthing_delay_days',
      label: 'Peak berthing delay at Singapore, late May 2024',
      recorded_value: 7,
      recorded_provenance: 'RECORDED',
      simulated_value: baseline.metrics.peak_wait_days,
      unit: 'days',
      tolerance: 2,
      interpretation:
        'Expected to under-predict. The recorded peak was driven largely by vessels ' +
        'arriving off-schedule - 90% in 2024 against 77% in 2023 - and PortWatch records ' +
        'the day a ship arrived, not the day it was due, so that bunching is absent from ' +
        'the stream the simulation is fed.',
    },
    {
      anchor_key: 'recovered_wait_days',
      label: 'Average wait time at the port after mitigation',
      recorded_value: 2,
      recorded_provenance: 'RECORDED',
      simulated_value: lastDay.rolling_wait_days,
      unit: 'days',
      tolerance: 1,
      interpretation:
        'Read with care. This is the baseline wait on the last day of the window, not a ' +
        'recovery: the reactive arm never recovers, because it never adds capacity. The ' +
        'recorded port recovered because PSA reactivated Keppel berths and hired around ' +
        '1,500 staff. Proximity to the recorded figure here is coincidence, not agreement.',
    },
    {
      anchor_key: 'port_stay_inflation_pct',
      label: 'Vessel port stays at PSA versus the same period in 2023',
      recorded_value: 22,
      recorded_provenance: 'RECORDED',
      simulated_value: baseline.metrics.port_stay_inflation_pct,
      unit: 'percent',
      tolerance: 12,
      interpretation:
        'Expected to over-predict. The simulated figure compounds the recorded rise in ' +
        'volume per call with the congestion feedback in the model, while the recorded ' +
        '+22% is the net outcome at a port that was actively adding capacity throughout ' +
        'the period.',
    },
  ]
  return rows.map((row) => ({
    ...row,
    within_tolerance: Math.abs(row.simulated_value - row.recorded_value) <= row.tolerance,
  }))
}

export const MOCK_BENCHMARK_RESULT: BenchmarkResult = (() => {
  const arms = BENCHMARK_SHAPES.map(mockArm)
  const baseline = arms[1].metrics
  const cascade = arms[2].metrics
  return {
    benchmark_id: 'offline-benchmark',
    config: {
      seed: 42,
      arms: BENCHMARK_SHAPES.map((shape) => shape.arm),
      world: {
        seed: 42,
        berths: { active_berths: 42, reserve_tranches: [] },
        service: {
          base_hours: 2,
          cranes_per_berth: 4,
          moves_per_crane_hour: 28,
          teu_per_move: 1.6,
          efficiency: 1,
          congestion_alpha: 0.15,
          congestion_queue_ref: 20,
          congestion_cap: 3,
          surge_alpha_factor: 0.75,
          surge_efficiency_gain: 0.06,
          fast_connection_speedup: 0.92,
        },
        arrival_jitter_hours: 0,
        service_rate_multiplier: 1,
        berth_delta: 0,
        activation_lead_override_days: null,
      },
      brain: 'SCRIPTED',
      rolling_window_days: 3,
      recovery_threshold_days: 2,
      recovery_sustain_days: 5,
    },
    calibration_window: { label: 'Pre-crisis calibration', start: '2023-01-01', end: '2024-02-29' },
    blind_window: { label: 'Red Sea 2024 blind replay', start: '2024-04-01', end: '2024-08-31' },
    historical_arm_provenance: 'RECONSTRUCTED',
    arms,
    comparisons: [
      {
        arm: 'CASCADE_AGENTIC',
        versus: 'REACTIVE_BASELINE',
        peak_wait_delta_days: Number((cascade.peak_wait_days - baseline.peak_wait_days).toFixed(2)),
        peak_wait_reduction_pct: Number(
          (
            ((baseline.peak_wait_days - cascade.peak_wait_days) / baseline.peak_wait_days) *
            100
          ).toFixed(1),
        ),
        // The reactive arm never recovers, so there is no recovery gap to
        // quote; the page says so rather than inventing a day count.
        recovery_days_saved: null,
        mean_wait_delta_days: Number((cascade.mean_wait_days - baseline.mean_wait_days).toFixed(2)),
        wait_cost_delta_usd: cascade.wait_cost_usd - baseline.wait_cost_usd,
        wins_on_peak: true,
        wins_on_recovery: true,
      },
    ],
    anchor_comparisons: mockAnchors(arms[1]),
    fixture_hashes: {},
    runtime_ms: 0,
    notice: BENCHMARK_NOTICE,
  }
})()
