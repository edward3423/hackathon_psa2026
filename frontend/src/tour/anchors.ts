/**
 * The elements the guided tour is allowed to point at.
 *
 * Components carry `data-tour="<id>"` on the element a step spotlights, and the
 * script names the same id. Keeping the list in one place makes the contract
 * greppable from either side: whoever edits a component can see that a tour step
 * depends on that element, and `script.test.ts` fails if a step names an id that
 * no longer exists here.
 *
 * A class name would have done the job today, but a class is a styling detail
 * that gets renamed without a second thought. This attribute exists for no other
 * reason, which is exactly what makes it safe to rely on.
 */
export const TOUR_ANCHORS = {
  'nav-overview': 'nav-overview',
  'nav-connections': 'nav-connections',
  'nav-yard': 'nav-yard',
  'nav-reefers': 'nav-reefers',
  'nav-agents': 'nav-agents',
  'nav-recovery': 'nav-recovery',
  'nav-execution': 'nav-execution',
  'nav-replay': 'nav-replay',
  'nav-benchmark': 'nav-benchmark',
  'nav-system': 'nav-system',
  'nav-list': 'nav-list',

  masthead: 'masthead',
  'disruption-strip': 'disruption-strip',
  'stage-track': 'stage-track',
  'run-state': 'run-state',
  'tour-launch': 'tour-launch',

  'controls-bar': 'controls-bar',
  'control-start': 'control-start',
  'control-reset': 'control-reset',
  'control-setup': 'control-setup',

  'situation-card': 'situation-card',
  'workflow-rail': 'workflow-rail',
  'port-schematic': 'port-schematic',
  'cargo-order': 'cargo-order',

  'agent-panel': 'agent-panel',
  'impact-summary': 'impact-summary',
  'reefer-alert': 'reefer-alert',
  'sailing-fallback': 'sailing-fallback',
  'trace-drawer': 'trace-drawer',

  'dispute-dialog': 'dispute-dialog',
  'dispute-positions': 'dispute-positions',
  'dispute-constraint-reefer': 'dispute-constraint-reefer',
  'dispute-confirm': 'dispute-confirm',

  'agent-topology': 'agent-topology',

  'plan-cards': 'plan-cards',
  'plan-recommended': 'plan-recommended',
  'deterministic-notice': 'deterministic-notice',
  'plan-tradeoffs': 'plan-tradeoffs',
  'yard-forecast': 'yard-forecast',

  'approval-bar': 'approval-bar',
  'approval-approve': 'approval-approve',
  'approval-confirm': 'approval-confirm',

  'execution-safety': 'execution-safety',
  'execution-actions': 'execution-actions',
  'execution-receipts': 'execution-receipts',

  'benchmark-run': 'benchmark-run',
  'benchmark-chart': 'benchmark-chart',
  'benchmark-headline': 'benchmark-headline',
  'benchmark-arms': 'benchmark-arms',
  'benchmark-audit': 'benchmark-audit',
  'benchmark-anchors': 'benchmark-anchors',
  'benchmark-decisions': 'benchmark-decisions',
  'benchmark-footer': 'benchmark-footer',

  'system-health': 'system-health',
  'system-mode': 'system-mode',
  'system-boundaries': 'system-boundaries',
} as const

export type TourAnchor = keyof typeof TOUR_ANCHORS

/** The live element for an anchor, or null if this page does not render it. */
export function findAnchor(anchor: TourAnchor): HTMLElement | null {
  return document.querySelector<HTMLElement>(`[data-tour="${anchor}"]`)
}

/** Whether an anchor is currently on the page. The script's usual predicate. */
export function anchorPresent(anchor: TourAnchor): boolean {
  return findAnchor(anchor) !== null
}
