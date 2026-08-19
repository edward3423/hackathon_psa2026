import { useRef } from 'react'

import type { TraceEvent, WorkflowStage } from '../api/types'
import { spaced } from '../lib/format'
import { usePublishedHeight } from '../lib/usePublishedHeight'

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
    return Math.abs(hour - cursorHour) < Math.abs(nearestHour - cursorHour)
      ? index
      : nearestIndex
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

export function OperationsTimeline({
  cursorHour,
  onCursorChange,
  stage,
  events,
}: OperationsTimelineProps) {
  const timelineRef = useRef<HTMLElement>(null)
  // Pinned to the bottom of the workspace, so anything that wants to stay clear
  // of the bottom of the viewport needs to know how much of it this covers.
  usePublishedHeight(timelineRef, '--operations-timeline-height')

  const selectedIndex = nearestMilestoneIndex(cursorHour)
  const selectedHour = TIMELINE_HOURS[selectedIndex]
  const labels = milestoneLabels(events, stage)
  const latestEvent = events.reduce<TraceEvent | null>(
    (latest, event) => (!latest || event.sequence > latest.sequence ? event : latest),
    null,
  )

  return (
    <section
      ref={timelineRef}
      className="operations-timeline"
      aria-labelledby="operations-timeline-title"
    >
      <header className="operations-timeline__header">
        <div>
          <h2 id="operations-timeline-title">72-hour operations timeline</h2>
          <p>Move through the forecast horizon to inspect how port pressure changes over time.</p>
        </div>
        <output className="operations-timeline__selection" aria-live="polite">
          H+{selectedHour}: {labels[selectedIndex]}
        </output>
      </header>

      <div className="operations-timeline__scrubber">
        <label htmlFor="operations-timeline-range">Forecast hour</label>
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
      </div>

      <ol className="operations-timeline__milestones" aria-label="Forecast milestones">
        {TIMELINE_HOURS.map((hour, index) => {
          const selected = index === selectedIndex
          return (
            <li key={hour} className={selected ? 'is-current' : undefined}>
              <button
                type="button"
                onClick={() => onCursorChange(hour)}
                aria-current={selected ? 'step' : undefined}
                aria-label={`H plus ${hour} hours: ${labels[index]}`}
              >
                <time>H+{hour}</time>
                <span>{labels[index]}</span>
              </button>
            </li>
          )
        })}
      </ol>

      <p className="operations-timeline__trace-context">
        Current workflow: {spaced(stage).toLowerCase()}.
        {latestEvent
          ? ` ${events.length} trace ${events.length === 1 ? 'record' : 'records'} received. Latest: ${spaced(
              latestEvent.kind,
            ).toLowerCase()}${latestEvent.agent ? ` from ${latestEvent.agent}` : ''}.`
          : ' No trace records have arrived yet.'}
      </p>
    </section>
  )
}
