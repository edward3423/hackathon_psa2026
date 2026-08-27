import type { TraceEvent, WorkflowStage } from '../api/types'

const TIMELINE_HOURS = [0, 6, 12, 24, 48, 72] as const

export interface OperationsTimelineProps {
  cursorHour: number
  onCursorChange: (hour: number) => void
  stage: WorkflowStage
  events: TraceEvent[]
}

function nearestMilestoneIndex(cursorHour: number): number {
  return TIMELINE_HOURS.reduce<number>((nearestIndex, hour, index) => {
    const nearestHour = TIMELINE_HOURS[nearestIndex] ?? TIMELINE_HOURS[0]
    return Math.abs(hour - cursorHour) < Math.abs(nearestHour - cursorHour) ? index : nearestIndex
  }, 0)
}

function milestoneLabels(events: TraceEvent[], stage: WorkflowStage): string[] {
  const hasKind = (kind: TraceEvent['kind']) => events.some((event) => event.kind === kind)
  const hasAgent = (agent: TraceEvent['agent']) => events.some((event) => event.agent === agent)

  return [
    hasKind('RUN_STARTED') ? 'Delay alert received' : 'Alert window',
    hasAgent('Impact Agent') ? 'Connection impact assessed' : 'Connection impact',
    hasAgent('Yard Agent') ? 'Yard and reefer forecast updated' : 'Capacity forecast',
    hasKind('APPROVAL_REQUIRED')
      ? 'Recovery plans awaiting approval'
      : hasKind('DISPUTE_OPENED')
        ? 'Constraint conflict raised'
        : hasAgent('Recovery Agent')
          ? 'Recovery planning active'
          : 'Recovery planning',
    hasKind('ACTION_DISPATCHED')
      ? 'Mock actions recorded'
      : hasKind('HUMAN_DECISION')
        ? 'Operator decision recorded'
        : 'Recovery execution',
    hasKind('RUN_COMPLETED') || stage === 'COMPLETE' ? 'Run completed' : 'Horizon review',
  ]
}

/*
 * A scrubber, and the name of the hour it is on. This was a full panel: a
 * heading, a sentence explaining what a scrubber is, the slider, six milestone
 * buttons each carrying its own sentence, and a paragraph restating the stage
 * and the trace count the masthead and the trace drawer already show. Nearly
 * 200px of a control that moves one number.
 */
export function OperationsTimeline({
  cursorHour,
  onCursorChange,
  events,
  stage,
}: OperationsTimelineProps) {
  const selectedIndex = nearestMilestoneIndex(cursorHour)
  const selectedHour = TIMELINE_HOURS[selectedIndex]
  const labels = milestoneLabels(events, stage)

  return (
    <section className="operations-timeline" aria-label="72-hour forecast scrubber">
      <label htmlFor="operations-timeline-range">Forecast</label>
      <input
        id="operations-timeline-range"
        type="range"
        min={0}
        max={TIMELINE_HOURS.length - 1}
        step={1}
        value={selectedIndex}
        onChange={(event) => onCursorChange(TIMELINE_HOURS[Number(event.target.value)])}
        aria-valuetext={`H plus ${selectedHour} hours, ${labels[selectedIndex]}`}
      />

      <ol className="operations-timeline__milestones" aria-label="Forecast milestones">
        {TIMELINE_HOURS.map((hour, index) => (
          <li key={hour} className={index === selectedIndex ? 'is-current' : undefined}>
            <button
              type="button"
              onClick={() => onCursorChange(hour)}
              aria-current={index === selectedIndex ? 'step' : undefined}
              aria-label={`H plus ${hour} hours: ${labels[index]}`}
              title={labels[index]}
            >
              H+{hour}
            </button>
          </li>
        ))}
      </ol>

      <output className="operations-timeline__selection" aria-live="polite">
        {labels[selectedIndex]}
      </output>
    </section>
  )
}
