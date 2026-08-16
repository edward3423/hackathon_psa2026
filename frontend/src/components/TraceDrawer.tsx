import { useState } from 'react'

import type { TraceEvent } from '../api/types'
import { formatElapsed, formatTime, spaced } from '../lib/format'

interface TraceDrawerProps {
  events: TraceEvent[]
}

function TraceRow({ event }: { event: TraceEvent }) {
  const [open, setOpen] = useState(false)

  return (
    <li className={`trace-row kind-${event.kind.toLowerCase()}`}>
      <button
        type="button"
        className="trace-summary"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="trace-seq">{String(event.sequence).padStart(3, '0')}</span>
        <time>{formatTime(event.timestamp)} UTC</time>
        <span className="trace-kind">{spaced(event.kind)}</span>
        <span className="trace-stage">{spaced(event.stage)}</span>
        <strong>{event.agent ?? 'System'}</strong>
        <span className="trace-tool">{event.tool ?? ''}</span>
        <span className="trace-text">
          {event.error ?? event.result ?? event.decision_summary ?? event.objective ?? ''}
        </span>
      </button>

      {open && (
        <dl className="trace-detail">
          {event.objective && (
            <div>
              <dt>Objective</dt>
              <dd>{event.objective}</dd>
            </div>
          )}
          {event.input_summary && (
            <div>
              <dt>Input</dt>
              <dd>{event.input_summary}</dd>
            </div>
          )}
          {event.tool && (
            <div>
              <dt>Tool</dt>
              <dd>{event.tool}</dd>
            </div>
          )}
          {event.decision_summary && (
            <div>
              <dt>Decision</dt>
              <dd>{event.decision_summary}</dd>
            </div>
          )}
          {event.result && (
            <div>
              <dt>Result</dt>
              <dd>{event.result}</dd>
            </div>
          )}
          {event.error && (
            <div className="trace-error">
              <dt>Error</dt>
              <dd>{event.error}</dd>
            </div>
          )}
          {event.confidence && (
            <div>
              <dt>Confidence</dt>
              <dd>
                <span className={`confidence-chip ${event.confidence.toLowerCase()}`}>
                  {event.confidence}
                </span>
              </dd>
            </div>
          )}
          {(event.assumptions?.length ?? 0) > 0 && (
            <div>
              <dt>Assumptions</dt>
              <dd>{event.assumptions?.join('; ')}</dd>
            </div>
          )}
          <div>
            <dt>Elapsed</dt>
            <dd>{formatElapsed(event.elapsed_ms)}</dd>
          </div>
          {event.next_handoff && (
            <div>
              <dt>Next handoff</dt>
              <dd>{event.next_handoff}</dd>
            </div>
          )}
          {event.parallel_group && (
            <div>
              <dt>Parallel group</dt>
              <dd>{event.parallel_group}</dd>
            </div>
          )}
        </dl>
      )}
    </li>
  )
}

export function TraceDrawer({ events }: TraceDrawerProps) {
  const [open, setOpen] = useState(false)
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence)

  return (
    <section className={`trace-drawer${open ? ' open' : ''}`} aria-labelledby="trace-title">
      <button
        type="button"
        className="drawer-toggle"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="section-label" id="trace-title">
          EXECUTION TRACE
        </span>
        <span className="drawer-count">{events.length} events</span>
        <span className="drawer-chevron">{open ? 'Collapse' : 'Expand'}</span>
      </button>

      {open &&
        (ordered.length === 0 ? (
          <p className="empty-trace">Start a run to record agent decisions and tool results.</p>
        ) : (
          <ol className="trace-list" aria-label="Execution trace events">
            {ordered.map((event) => (
              <TraceRow key={event.event_id} event={event} />
            ))}
          </ol>
        ))}
    </section>
  )
}
