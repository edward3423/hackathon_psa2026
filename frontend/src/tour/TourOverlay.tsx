import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play, X } from 'lucide-react'

import type { TourController } from './engine'
import type { TourPlacement } from './types'

/**
 * Everything the tour draws: the spotlight, the bubble, the cursor and the
 * transport bar. Purely presentational, so a test can hand it a controller.
 *
 * The spotlight is a fixed div sized to the anchor and given a viewport-sized
 * box-shadow, which dims the page around a hole without touching the anchor's
 * own stacking context. Raising a z-index on something inside `.approval-bar`
 * or `.dispute-overlay` would reorder real UI, which is the one thing a tour
 * over a live product must never do.
 */

const BUBBLE_WIDTH = 340
const BUBBLE_MAX_HEIGHT = 240
const GAP = 18
const MARGIN = 16
/** Bottom strip the transport occupies, including its shadow. */
const TRANSPORT_ZONE = 120

interface Viewport {
  width: number
  height: number
}

function useViewport(): Viewport {
  const [viewport, setViewport] = useState<Viewport>(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
  }))
  useEffect(() => {
    const onResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return viewport
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high)
}

interface BubblePlacement {
  left: number
  top: number
  side: TourPlacement
}

/**
 * Whichever side of the anchor has the most room, clamped to the viewport.
 *
 * `reservedTop` is the strip the transport occupies when it has flipped to the
 * top of the screen. The bubble stays below it rather than sharing the pixels,
 * which on a tall anchor is the difference between one readable card and two
 * sets of text on top of each other.
 */
function placeBubble(
  rect: DOMRect | null,
  requested: TourPlacement | undefined,
  viewport: Viewport,
  reservedTop: number,
): BubblePlacement {
  const minTop = MARGIN + reservedTop

  if (!rect || requested === 'center') {
    return {
      left: (viewport.width - BUBBLE_WIDTH) / 2,
      top: Math.max(minTop, viewport.height / 2 - BUBBLE_MAX_HEIGHT / 2),
      side: 'center',
    }
  }

  const room = {
    bottom: viewport.height - rect.bottom,
    top: rect.top,
    right: viewport.width - rect.right,
    left: rect.left,
  }
  const needsVertical = BUBBLE_MAX_HEIGHT + GAP + MARGIN
  const needsHorizontal = BUBBLE_WIDTH + GAP + MARGIN

  let side: TourPlacement
  if (requested && requested !== 'auto') side = requested
  else if (room.bottom >= needsVertical) side = 'bottom'
  else if (room.top >= needsVertical) side = 'top'
  else if (room.right >= needsHorizontal) side = 'right'
  else if (room.left >= needsHorizontal) side = 'left'
  else side = room.bottom >= room.top ? 'bottom' : 'top'

  const maxLeft = viewport.width - BUBBLE_WIDTH - MARGIN
  const maxTop = viewport.height - BUBBLE_MAX_HEIGHT - MARGIN

  if (side === 'bottom' || side === 'top') {
    const left = clamp(rect.left + rect.width / 2 - BUBBLE_WIDTH / 2, MARGIN, Math.max(MARGIN, maxLeft))
    const top =
      side === 'bottom' ? rect.bottom + GAP : Math.max(minTop, rect.top - GAP - BUBBLE_MAX_HEIGHT)
    return { left, top: clamp(top, minTop, Math.max(minTop, maxTop)), side }
  }

  const left = side === 'right' ? rect.right + GAP : Math.max(MARGIN, rect.left - GAP - BUBBLE_WIDTH)
  const top = clamp(
    rect.top + rect.height / 2 - BUBBLE_MAX_HEIGHT / 2,
    minTop,
    Math.max(minTop, maxTop),
  )
  return { left: clamp(left, MARGIN, Math.max(MARGIN, maxLeft)), top, side }
}

/**
 * The transport bar dims itself when the pointer is still, so a hands-off
 * recording is not narrated by a control bar nobody is using.
 */
function useIdlePointer(active: boolean): boolean {
  const [idle, setIdle] = useState(false)
  useEffect(() => {
    if (!active) return
    let timer = window.setTimeout(() => setIdle(true), 3000)
    const wake = () => {
      setIdle(false)
      window.clearTimeout(timer)
      timer = window.setTimeout(() => setIdle(true), 3000)
    }
    window.addEventListener('pointermove', wake)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('pointermove', wake)
    }
  }, [active])
  return idle
}

export interface TourOverlayProps {
  tour: TourController
}

export function TourOverlay({ tour }: TourOverlayProps) {
  const viewport = useViewport()
  const idle = useIdlePointer(tour.status === 'PLAYING')

  if (tour.status === 'IDLE') return null

  if (tour.status === 'BLOCKED') {
    return (
      <div className="tour-root" role="dialog" aria-label="Guided tour unavailable">
        <div className="tour-scrim" />
        <div className="tour-bubble tour-bubble--center" data-side="center">
          <h2>The tour needs the backend</h2>
          <p>
            The walkthrough starts real runs so every figure it shows is genuinely computed. Start
            the API on port 8620 and reload this page.
          </p>
          <button type="button" className="secondary-action" onClick={tour.exit}>
            Close
          </button>
        </div>
      </div>
    )
  }

  const position = tour.position
  if (!position) return null

  const { step, chapter, chapterIndex, globalIndex, globalCount } = position
  // The transport docks at the bottom, which is also where the approval bar
  // lives. When the spotlit element reaches down there, the controls move to the
  // top instead, and the bubble has to give them that strip.
  const transportAtTop = Boolean(tour.rect && tour.rect.bottom > viewport.height - TRANSPORT_ZONE)
  const placement = placeBubble(
    tour.rect,
    step.placement,
    viewport,
    transportAtTop ? TRANSPORT_ZONE : 0,
  )
  const finished = tour.status === 'FINISHED'
  const paused = tour.status === 'PAUSED' || tour.status === 'STALLED'

  return (
    <div className="tour-root" data-status={tour.status}>
      {tour.rect ? (
        <div
          className="tour-spotlight"
          style={{
            left: tour.rect.left - 6,
            top: tour.rect.top - 6,
            width: tour.rect.width + 12,
            height: tour.rect.height + 12,
          }}
        />
      ) : (
        <div className="tour-scrim" />
      )}

      {/* An anchored step whose element has not arrived yet reads centred, then
          glides onto the anchor when it renders. Narration never blanks. */}
      <div
        className={`tour-bubble${placement.side === 'center' ? ' tour-bubble--center' : ''}`}
        style={{ left: placement.left, top: placement.top, width: BUBBLE_WIDTH }}
        data-side={placement.side}
        role="dialog"
        aria-live="polite"
        aria-label={`Guided tour: ${step.title}`}
      >
        <span className="tour-bubble__chapter">{chapter.title}</span>
        <h2>{step.title}</h2>
        <p>{step.body}</p>
        {tour.stall && <p className="tour-bubble__stall">{tour.stall}</p>}
      </div>

      {tour.cursor && (
        <div
          className={`tour-cursor${tour.pressing ? ' is-pressing' : ''}`}
          style={{ transform: `translate(${tour.cursor.x}px, ${tour.cursor.y}px)` }}
          aria-hidden="true"
        />
      )}

      <div
        className={`tour-transport${idle && !paused ? ' is-idle' : ''}${
          transportAtTop ? ' is-top' : ''
        }`}
        role="group"
        aria-label="Tour controls"
      >
        <div className="tour-transport__identity">
          <strong>
            {chapterIndex + 1}. {chapter.title}
          </strong>
          <span>
            Step {globalIndex + 1} of {globalCount}
          </span>
        </div>
        <div
          className="tour-transport__progress"
          role="progressbar"
          aria-valuemin={1}
          aria-valuemax={globalCount}
          aria-valuenow={globalIndex + 1}
        >
          <span style={{ width: `${((globalIndex + 1) / globalCount) * 100}%` }} />
        </div>
        <div className="tour-transport__actions">
          <button
            type="button"
            onClick={tour.back}
            aria-label="Re-read the previous step"
            disabled={globalIndex === 0}
          >
            <ChevronLeft size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={paused ? tour.resume : tour.pause}
            aria-label={paused ? 'Resume tour' : 'Pause tour'}
            disabled={finished}
          >
            {paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}
          </button>
          <button
            type="button"
            onClick={tour.next}
            aria-label="Skip to the next step"
            disabled={finished}
          >
            <ChevronRight size={15} aria-hidden="true" />
          </button>
          <button type="button" onClick={tour.exit} aria-label="Exit tour">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  )
}
