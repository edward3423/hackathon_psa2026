import { anchorPresent, findAnchor } from './anchors'
import type { TourChapter } from './types'

/**
 * The five-minute guided tour, as data.
 *
 * Bubbles name what is on screen and say why it matters. Where the product
 * already explains a figure - the scope notice, the deterministic-engine badge,
 * the blind-audit sentence - the bubble points at that copy rather than
 * restating it, so the viewer learns to read the product instead of the tour.
 *
 * Dwell budgets are reading time. The work itself is fast: an Act 1 run emits 23
 * events at 50 ms and the Act 2 playback is 153 days at 40 ms, so nearly all of
 * the five minutes is deliberate pacing rather than waiting on a backend.
 */

/** Whether an anchored control is present and accepting clicks. */
function controlEnabled(anchor: Parameters<typeof findAnchor>[0]): boolean {
  const element = findAnchor(anchor)
  return element instanceof HTMLButtonElement && !element.disabled
}

/** Whether an anchored control is present and refusing clicks. */
function controlBusy(anchor: Parameters<typeof findAnchor>[0]): boolean {
  const element = findAnchor(anchor)
  return element instanceof HTMLButtonElement && element.disabled
}

/** The workflow stage as the top bar renders it, for step conditions. */
function stageReadout(): string {
  const readout = document.querySelector('[data-tour="run-state"] strong')
  return readout?.textContent?.trim() ?? ''
}

export const TOUR_CHAPTERS: TourChapter[] = [
  {
    id: 'cold-open',
    title: 'Cold open',
    steps: [
      {
        id: 'opening',
        placement: 'center',
        title: 'CASCADE',
        body: 'A port disruption arrives. Five agents work out what it breaks, argue about the fix, and hand a human three options. Nothing reaches a real system. This tour drives the product itself, one control at a time.',
        dwellMs: 6000,
      },
      {
        id: 'masthead',
        anchor: 'masthead',
        title: 'One run, always in view',
        body: 'The masthead never changes shape. Run identity, agent mode, stream health and workflow stage stay in the same five places for the whole demonstration.',
        dwellMs: 5000,
      },
      {
        id: 'disruption',
        anchor: 'disruption-strip',
        title: 'The disruption',
        body: 'MV ATLAS STAR arrives eighteen hours late into port call SGSIN-PSA-2042. Every number that follows is derived from this one fact and the synthetic port behind it.',
        dwellMs: 6000,
      },
      {
        id: 'stages',
        anchor: 'stage-track',
        title: 'Seven stages, two of them human',
        body: 'DISPUTE and AWAITING APPROVAL are gates, not steps. The workflow stops at both and will not continue until a person decides.',
        dwellMs: 6000,
      },
      {
        id: 'controls',
        // Reset clears any earlier run, so every take starts from the same state.
        click: 'control-reset',
        anchor: 'controls-bar',
        title: 'The scenario is yours to change',
        body: 'Six presets, an adjustable delay, a priority emphasis, a choice of agent brain, and a switch that makes a tool time out on purpose. The tour leaves all of them at their defaults so every take is identical.',
        until: () => stageReadout() === 'READY',
        dwellMs: 5000,
      },
      {
        id: 'start',
        click: 'control-start',
        anchor: 'run-state',
        title: 'Start the run',
        body: 'Events stream from the backend over SSE. Watch the stage readout and the trace count, and watch how quickly the run stops itself.',
        until: () => stageReadout() !== 'READY' && stageReadout() !== '',
        dwellMs: 2000,
      },
    ],
  },
  {
    // The dispute comes second, not later: the backend streams 23 events at
    // 50 ms, so the run halts on the conflict about a second after Start. A
    // chapter placed between the two would narrate the Command Center from
    // behind a modal the operator has not answered yet.
    id: 'dispute',
    title: 'The agents disagree',
    steps: [
      {
        id: 'dispute-open',
        anchor: 'dispute-dialog',
        title: 'The workflow stops itself',
        body: 'Within a second of starting, Impact and Yard reached incompatible conclusions and the run halted. This is designed behaviour: the agents surface the conflict instead of quietly picking a side.',
        until: () => anchorPresent('dispute-dialog'),
        dwellMs: 8000,
      },
      {
        id: 'dispute-positions',
        anchor: 'dispute-positions',
        title: 'Both cases, stated plainly',
        body: 'Impact wants every threatened pharmaceutical reefer rushed. Yard says the terminal does not have the plugs. Both are right about their own domain, which is exactly why a human has to choose.',
        dwellMs: 9000,
      },
      {
        id: 'dispute-choice',
        anchor: 'dispute-constraint-reefer',
        title: 'The human picks the constraint',
        body: 'Not the plan, the constraint. The operator decides which rule the plans must respect, and the planner works inside it.',
        dwellMs: 7000,
      },
      {
        id: 'dispute-select',
        click: 'dispute-constraint-reefer',
        anchor: 'dispute-confirm',
        title: 'Physical capacity wins',
        body: 'Choosing the plug limit means no plan may promise a reefer socket that does not exist. The decision is recorded in the trace with the human as its author.',
        // Confirm stays disabled until a constraint is selected, so an enabled
        // Confirm is the proof that the choice registered.
        until: () => controlEnabled('dispute-confirm'),
        dwellMs: 6000,
      },
      {
        id: 'dispute-confirm',
        click: 'dispute-confirm',
        anchor: 'sailing-fallback',
        title: 'A tool times out, and the agent says so',
        body: 'Planning resumed and the alternative-sailing lookup failed. Rather than inventing a result, the agent falls back to cached data and marks the finding medium confidence.',
        until: () => anchorPresent('sailing-fallback'),
        dwellMs: 8000,
      },
    ],
  },
  {
    // Still on the Command Center: confirming the constraint dismissed the
    // dialog and the run has carried itself to the approval gate, so every
    // panel below is populated and nothing is covering them.
    id: 'command-center',
    title: 'Command Center',
    steps: [
      {
        id: 'workflow-rail',
        anchor: 'workflow-rail',
        title: 'What ran, and in what order',
        body: 'Impact and Yard ran in parallel, not in sequence. Both specialists were on the problem before either had finished, and the rail has already carried the run to the approval gate.',
        dwellMs: 8000,
      },
      {
        id: 'situation',
        anchor: 'situation-card',
        title: 'The shape of the problem',
        body: 'Containers affected, connections at risk, expected misses. These are the counts the three recovery plans are scored against.',
        dwellMs: 6000,
      },
      {
        id: 'schematic',
        anchor: 'port-schematic',
        title: 'The port, not a dashboard',
        body: 'Berths, the approach channel, yard blocks and reefer racks. Vessels and blocks are clickable, and the colours are the same risk scale used everywhere else in the app.',
        dwellMs: 9000,
      },
      {
        id: 'cargo',
        anchor: 'cargo-order',
        title: 'What gets protected first',
        body: 'Cargo is ranked before any plan exists. Pharmaceutical reefers outrank standard dry cargo, and that ordering is what the two agents just disagreed over.',
        dwellMs: 7000,
      },
      {
        id: 'agents',
        anchor: 'agent-panel',
        title: 'Five specialists, each with a receipt',
        body: 'Each card shows the agent, its status and the tool it called. Expand one and it names the arguments it passed and the evidence it got back.',
        dwellMs: 8000,
      },
      {
        id: 'impact',
        anchor: 'impact-summary',
        title: 'Calculated, not narrated',
        body: 'The agents decide what to look at. Deterministic Python computes every figure on this panel, so the same scenario produces the same numbers every time.',
        dwellMs: 7000,
      },
      {
        id: 'trace',
        anchor: 'trace-drawer',
        title: 'Every step is on the record',
        body: 'One entry per agent action and per tool call, in order, with the arguments. The trace is the audit surface for every figure the tour has shown and every one still to come.',
        dwellMs: 5000,
      },
    ],
  },
  {
    id: 'agent-room',
    title: 'The agent room',
    steps: [
      {
        id: 'topology',
        click: 'nav-agents',
        anchor: 'agent-topology',
        title: 'How the handoffs actually ran',
        body: 'The topology draws the path this run took between the five agents. Click any node for what that agent contributed and when.',
        until: () => anchorPresent('agent-topology'),
        dwellMs: 9000,
      },
      {
        id: 'agent-log',
        anchor: 'agent-panel',
        title: 'The same agents, in detail',
        body: 'Coordinator, Impact, Yard, Recovery and Execution. Every status change beside it came from a real event on the stream, not a scripted animation.',
        dwellMs: 8000,
      },
    ],
  },
  {
    id: 'recovery',
    title: 'Three plans, one decision',
    steps: [
      {
        id: 'plans',
        click: 'nav-recovery',
        anchor: 'plan-cards',
        title: 'Three strategies, not one answer',
        body: 'Protect every connection, minimise congestion, or the hybrid. Each is fully costed against the constraint the operator just confirmed.',
        until: () => anchorPresent('plan-cards'),
        dwellMs: 9000,
      },
      {
        id: 'recommended',
        anchor: 'plan-recommended',
        title: 'A recommendation, with its reasoning',
        body: 'One plan is marked recommended and carries the rationale that earned it. An infeasible plan is still shown, with the constraint it violates named.',
        dwellMs: 8000,
      },
      {
        id: 'deterministic',
        anchor: 'deterministic-notice',
        title: 'The line the whole project is built on',
        body: 'Agents propose actions. Deterministic engines calculate every outcome and enforce every physical limit. The language model never changes a number.',
        dwellMs: 9000,
      },
      {
        id: 'tradeoffs',
        anchor: 'plan-tradeoffs',
        title: 'Trade-offs, side by side',
        body: 'Connections saved, containers rehandled, cost, and yard pressure. Nothing here is a preference; every column comes out of the same engine.',
        dwellMs: 8000,
      },
      {
        id: 'yard-forecast',
        anchor: 'yard-forecast',
        title: 'What it does to the yard',
        body: 'Baseline against planned occupancy over seventy-two hours. A plan that fixes connections by overflowing a block is visible here before anyone approves it.',
        dwellMs: 7000,
      },
      {
        id: 'approval',
        anchor: 'approval-bar',
        title: 'The second human gate',
        body: 'The run is finished thinking and has stopped again. Nothing is dispatched, no receipt exists, and no work order has been written.',
        until: () => anchorPresent('approval-bar'),
        dwellMs: 9000,
      },
      {
        id: 'approve',
        click: 'approval-approve',
        anchor: 'approval-confirm',
        title: 'Approval is deliberate',
        body: 'Approving opens a confirmation that states plainly that this is a simulation and that no carrier or terminal system will be contacted.',
        until: () => anchorPresent('approval-confirm'),
        dwellMs: 7000,
      },
      {
        id: 'confirm',
        click: 'approval-confirm',
        anchor: 'execution-safety',
        title: 'Confirmed',
        body: 'The app moves itself to Execution, which is the only page that can show a dispatched action.',
        until: () => anchorPresent('execution-safety'),
        dwellMs: 3000,
      },
    ],
  },
  {
    id: 'execution',
    title: 'Nothing moves without approval',
    steps: [
      {
        id: 'safety',
        anchor: 'execution-safety',
        title: 'Said out loud, on the page',
        body: 'No real-world actions were executed. The notice is part of the product, not a disclaimer added for a demonstration.',
        dwellMs: 9000,
      },
      {
        id: 'actions',
        anchor: 'execution-actions',
        title: 'What would have been sent',
        body: 'Each mocked action names its target system and its payload. Before approval this register was empty, and the tour did not skip a step to make that true.',
        dwellMs: 8000,
      },
      {
        id: 'receipts',
        anchor: 'execution-receipts',
        title: 'Receipts, clearly mocked',
        body: 'Acknowledgements from the synthetic environment, labelled as mocked in the heading itself so a screenshot cannot be mistaken for a real dispatch.',
        until: () => anchorPresent('execution-receipts'),
        dwellMs: 8000,
      },
      {
        id: 'complete',
        anchor: 'stage-track',
        title: 'Act 1, complete',
        body: 'Alert to mocked execution, with two human decisions on the record and every figure reproducible from the trace.',
        until: () => stageReadout() === 'COMPLETE',
        dwellMs: 5000,
      },
    ],
  },
  {
    id: 'benchmark',
    title: 'Act 2: the blind benchmark',
    steps: [
      {
        id: 'benchmark-open',
        click: 'nav-benchmark',
        anchor: 'masthead',
        title: 'A different question entirely',
        body: 'The vessel strip, the stage rail and the seventy-two hour scrubber are all gone, because none of them describe a five-month fleet replay. The page asks for the masthead alone.',
        until: () => anchorPresent('benchmark-run'),
        dwellMs: 7000,
      },
      {
        id: 'benchmark-run',
        click: 'benchmark-run',
        anchor: 'benchmark-chart',
        title: 'The real 2024 arrival stream, one day at a time',
        body: 'Singapore, April to August 2024, during the Red Sea diversions. Parameters were fitted on 2023 only, and no arm can read a day it has not yet entered.',
        // The button reads Running while the replay streams. The dwell that
        // follows is the beat where the three curves draw across the chart.
        until: () => controlBusy('benchmark-run'),
        dwellMs: 12000,
      },
      {
        id: 'benchmark-headline',
        anchor: 'benchmark-headline',
        title: 'The result, and its limits',
        body: 'CASCADE cut the peak wait against a reactive baseline running the identical engine. The page says in the same breath that this is one pinned run and the robustness claim is the sweep win-rate.',
        until: () => anchorPresent('benchmark-headline'),
        dwellMs: 9000,
      },
      {
        id: 'benchmark-arms',
        anchor: 'benchmark-arms',
        title: 'Three arms, honestly labelled',
        body: 'Every tile carries a provenance chip. The historical curve is marked RECONSTRUCTED wherever it is drawn, and where a figure was never reconstructed the tile says so instead of printing a zero.',
        dwellMs: 9000,
      },
      {
        id: 'benchmark-audit',
        anchor: 'benchmark-audit',
        title: 'Blindness is enforced, not asserted',
        body: 'The feed has no accessor for the full stream, and a read past the simulation clock raises. Every read is logged, and the badge reports the count and the maximum lookahead.',
        dwellMs: 9000,
      },
      {
        id: 'benchmark-anchors',
        anchor: 'benchmark-anchors',
        title: 'Context, not a score',
        body: 'Published 2024 figures against what the blind simulation produced. Each row states which way it should miss and why, including the one that lands inside tolerance for the wrong reason.',
        dwellMs: 7000,
      },
      {
        id: 'benchmark-decisions',
        anchor: 'benchmark-decisions',
        title: 'What the agent actually did',
        body: 'Berth reactivation with its lead time enforced, a change of queue discipline, fast connection mode. Repeated holds collapse into one row so the decisions that changed the port stand out.',
        dwellMs: 8000,
      },
      {
        id: 'benchmark-footer',
        anchor: 'benchmark-footer',
        title: 'Where the data came from',
        body: 'IMF PortWatch for the arrivals, published figures for the anchors, and the calibration and blind windows stated separately so the split can be checked.',
        dwellMs: 4000,
      },
    ],
  },
  {
    id: 'closing',
    title: 'What we are not claiming',
    steps: [
      {
        id: 'system-health',
        click: 'nav-system',
        anchor: 'system-health',
        title: 'The environment, described',
        body: 'Component health, the transport state, and which brain the agents are running on. Switching between the scripted brain and a live model is a control, not a rebuild.',
        until: () => anchorPresent('system-health'),
        dwellMs: 6000,
      },
      {
        id: 'boundaries',
        anchor: 'system-boundaries',
        title: 'The boundaries, in writing',
        body: 'A synthetic port, a reconstructed historical curve, vessel-level abstraction at fleet scale. The limitations are shipped with the product rather than left for a reviewer to find.',
        dwellMs: 6000,
      },
      {
        id: 'not-visited',
        anchor: 'nav-list',
        title: 'Four pages this tour skipped',
        body: 'Connections, Yard, Reefers and Replay are all live and populated by the run you just watched. They were left out for time, not because they are empty.',
        dwellMs: 5000,
      },
      {
        id: 'closing-card',
        placement: 'center',
        title: 'That is CASCADE',
        body: 'One vessel in close-up, then a fleet across five months, with the same rule holding throughout: agents decide what to look at, deterministic engines decide what the numbers are, and a human decides what happens.',
        dwellMs: 3000,
      },
    ],
  },
]
