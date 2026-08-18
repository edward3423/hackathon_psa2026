import { useEffect, useMemo, useState } from 'react'
import { Clock3, Pause, Play, RotateCcw, SkipBack, SkipForward } from 'lucide-react'

import type { TraceEvent } from '../api/types'
import { formatTime, spaced } from '../lib/format'

interface ReplayPageProps {
  initialCursor?: number
  onCursorChange: (cursor: number) => void
  events?: TraceEvent[]
}

const SPEEDS = [0.5, 1, 2, 4] as const

function clampCursor(cursor: number, length: number): number {
  return Math.min(Math.max(Math.round(cursor), 0), Math.max(0, length - 1))
}

export function ReplayPage({ initialCursor = 0, onCursorChange, events = [] }: ReplayPageProps) {
  const milestones = useMemo(
    () =>
      events.length > 0
        ? [...events]
            .sort((left, right) => left.sequence - right.sequence)
            .map((event) => ({
              time: `${formatTime(event.timestamp)} UTC`,
              label:
                event.error ??
                event.result ??
                event.decision_summary ??
                event.objective ??
                spaced(event.kind),
              stage: event.stage,
              kind: spaced(event.kind),
              sequence: event.sequence,
            }))
        : [
            {
              time: 'H+0',
              label: 'Start a demo replay to load recorded workflow events.',
              stage: 'READY',
              kind: 'Waiting',
              sequence: 0,
            },
          ],
    [events],
  )
  const [cursor, setCursor] = useState(() => clampCursor(initialCursor, milestones.length))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1)

  useEffect(() => {
    onCursorChange(cursor)
  }, [cursor, onCursorChange])

  useEffect(() => {
    if (!playing) return undefined

    const timer = window.setInterval(() => {
      setCursor((current) => {
        if (current >= milestones.length - 1) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, 1200 / speed)

    return () => window.clearInterval(timer)
  }, [milestones.length, playing, speed])

  useEffect(() => {
    setCursor((currentCursor) => clampCursor(currentCursor, milestones.length))
  }, [milestones.length])

  const current = milestones[cursor]
  const setReplayCursor = (next: number) => setCursor(clampCursor(next, milestones.length))

  return (
    <section className="replay-page" aria-labelledby="replay-title">
      <header className="page-section-header">
        <div>
          <h2 id="replay-title">Disruption response timeline</h2>
          <p>Recorded synthetic events from the backend replay workflow.</p>
        </div>
        <div className="replay-position" aria-live="polite">
          <Clock3 aria-hidden="true" size={16} />
          <span>{current.time}</span>
          <strong>{current.label}</strong>
        </div>
      </header>

      <section className="replay-controls" aria-label="Replay controls">
        <div className="replay-transport">
          <button
            type="button"
            className="icon-action"
            onClick={() => setReplayCursor(cursor - 1)}
            disabled={cursor === 0}
            aria-label="Previous Event"
          >
            <SkipBack aria-hidden="true" size={18} />
          </button>
          <button
            type="button"
            className="primary-action replay-play-action"
            onClick={() => setPlaying((currentPlaying) => !currentPlaying)}
          >
            {playing ? (
              <Pause aria-hidden="true" size={17} />
            ) : (
              <Play aria-hidden="true" size={17} />
            )}
            {playing ? 'Pause' : 'Play'}
          </button>
          <button
            type="button"
            className="icon-action"
            onClick={() => setReplayCursor(cursor + 1)}
            disabled={cursor === milestones.length - 1}
            aria-label="Next Event"
          >
            <SkipForward aria-hidden="true" size={18} />
          </button>
          <button
            type="button"
            className="secondary-action"
            onClick={() => {
              setPlaying(false)
              setReplayCursor(0)
            }}
          >
            <RotateCcw aria-hidden="true" size={16} />
            Restart
          </button>
        </div>

        <label className="replay-speed-control">
          Playback Speed
          <select
            value={speed}
            onChange={(event) =>
              setSpeed(Number(event.target.value) as (typeof SPEEDS)[number])
            }
          >
            {SPEEDS.map((option) => (
              <option value={option} key={option}>
                {option}x
              </option>
            ))}
          </select>
        </label>
      </section>

      <div className="replay-scrubber">
        <label htmlFor="replay-timeline">
          Timeline position
          <span>
            {cursor + 1} of {milestones.length}
          </span>
        </label>
        <input
          id="replay-timeline"
          type="range"
          min={0}
          max={milestones.length - 1}
          step={1}
          value={cursor}
          onChange={(event) => {
            setPlaying(false)
            setReplayCursor(Number(event.target.value))
          }}
        />
      </div>

      <ol className="replay-milestone-list" aria-label="Recorded workflow milestones">
        {milestones.map((milestone, index) => (
          <li
            key={`${milestone.sequence}-${milestone.time}`}
            className={`${index === cursor ? 'is-current' : ''}${index < cursor ? ' is-past' : ''}`}
          >
            <button
              type="button"
              onClick={() => {
                setPlaying(false)
                setReplayCursor(index)
              }}
              aria-current={index === cursor ? 'step' : undefined}
            >
              <span className="milestone-marker" aria-hidden="true" />
              <time>{milestone.time}</time>
              <strong>{milestone.label}</strong>
              <small>
                {milestone.kind} · {milestone.stage.replaceAll('_', ' ')}
              </small>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
