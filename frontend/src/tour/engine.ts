import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { anchorPresent, findAnchor } from './anchors'
import { TOUR_CHAPTERS } from './script'
import type { TourPosition, TourStatus, TourStep } from './types'

/**
 * The tour state machine.
 *
 * It observes the running product rather than reaching into it: steps find their
 * element by `data-tour`, advance on DOM conditions, and act by calling `.click()`
 * on the real control. `App` holds every piece of state in `useState` with no
 * context, so a tour that drove state directly would have to be threaded through
 * twenty components and could drift away from what a user clicking those same
 * buttons would actually get.
 */

/** How long the cursor takes to reach a control. Matches the CSS transition. */
const CURSOR_FLY_MS = 450
/** The press-and-release beat, so a viewer sees the click land. */
const CURSOR_PRESS_MS = 200
/** Two frames of grace after a scroll, so the spotlight lands on a settled rect. */
const SETTLE_MS = 120
const DEFAULT_TIMEOUT_MS = 30_000

const ABORTED = Symbol('tour-aborted')

export interface TourFlags {
  autostart: boolean
  /** Multiplies every dwell. `?tour=fast` makes a full play about 30 seconds. */
  dwellScale: number
}

export function readTourFlags(search: string): TourFlags {
  const value = new URLSearchParams(search).get('tour') ?? ''
  const modes = value.split(',').map((mode) => mode.trim())
  return {
    autostart: modes.includes('auto'),
    dwellScale: modes.includes('fast') ? 0.05 : 1,
  }
}

export interface TourController {
  status: TourStatus
  position: TourPosition | null
  /** The spotlit rect, tracked every frame. Null for a centred card. */
  rect: DOMRect | null
  cursor: { x: number; y: number } | null
  pressing: boolean
  /** Set when a step's condition never came true, naming the step. */
  stall: string | null
  available: boolean
  start: () => void
  exit: () => void
  pause: () => void
  resume: () => void
  next: () => void
  back: () => void
}

type FlatStep = TourPosition

function flatten(): FlatStep[] {
  const flat: FlatStep[] = []
  const globalCount = TOUR_CHAPTERS.reduce((total, chapter) => total + chapter.steps.length, 0)
  TOUR_CHAPTERS.forEach((chapter, chapterIndex) => {
    chapter.steps.forEach((step, stepIndex) => {
      flat.push({
        chapter,
        step,
        chapterIndex,
        stepIndex,
        globalIndex: flat.length,
        globalCount,
      })
    })
  })
  return flat
}

/**
 * One animation-frame pump, shared by every wait in the runner.
 *
 * `onFrame` receives elapsed milliseconds and returns true when the wait is over.
 * Time does not accumulate while paused, so pausing mid-dwell freezes the step
 * rather than skipping it, and aborting rejects at the next frame.
 */
function pump(
  signal: AbortSignal,
  isPaused: () => boolean,
  onFrame: (deltaMs: number) => boolean,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(ABORTED)
      return
    }
    let handle = 0
    let last = performance.now()
    const stop = () => {
      cancelAnimationFrame(handle)
      reject(ABORTED)
    }
    signal.addEventListener('abort', stop, { once: true })
    const frame = (now: number) => {
      const delta = now - last
      last = now
      if (!isPaused() && onFrame(delta)) {
        signal.removeEventListener('abort', stop)
        resolve()
        return
      }
      handle = requestAnimationFrame(frame)
    }
    handle = requestAnimationFrame(frame)
  })
}

function sleep(ms: number, signal: AbortSignal, isPaused: () => boolean): Promise<void> {
  let elapsed = 0
  return pump(signal, isPaused, (delta) => {
    elapsed += delta
    return elapsed >= ms
  })
}

/** Resolves true when the predicate holds, false once the timeout is spent. */
async function waitFor(
  predicate: () => boolean,
  timeoutMs: number,
  signal: AbortSignal,
  isPaused: () => boolean,
): Promise<boolean> {
  if (predicate()) return true
  let elapsed = 0
  let satisfied = false
  await pump(signal, isPaused, (delta) => {
    elapsed += delta
    satisfied = predicate()
    return satisfied || elapsed >= timeoutMs
  })
  return satisfied
}

function centreOf(element: HTMLElement): { x: number; y: number } {
  const rect = element.getBoundingClientRect()
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

function scrollIntoView(element: HTMLElement): void {
  // A panel taller than the viewport cannot be centred without pushing its own
  // heading off the top, and the heading is usually the thing the step names -
  // "EXECUTION RECEIPTS (MOCKED)" is the whole point of that step. Align those
  // to the top instead. The masthead scrolls away on desktop, so nothing covers
  // the heading once it lands there.
  const tall = element.getBoundingClientRect().height > window.innerHeight * 0.85
  element.scrollIntoView({
    block: tall ? 'start' : 'center',
    inline: 'nearest',
    behavior: 'smooth',
  })
}

export interface UseTourOptions {
  /** The tour drives real runs, so it needs the backend. */
  enabled: boolean
  search?: string
}

export function useTour({ enabled, search }: UseTourOptions): TourController {
  const steps = useMemo(flatten, [])
  const [flags] = useState(() => readTourFlags(search ?? window.location.search))

  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState<TourStatus>('IDLE')
  const [index, setIndex] = useState(0)
  const [token, setToken] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)
  const [pressing, setPressing] = useState(false)
  const [stall, setStall] = useState<string | null>(null)

  const pausedRef = useRef(false)
  /** Set when stepping back: the step narrates again but never re-clicks. */
  const narrateOnlyRef = useRef(false)
  const autostartedRef = useRef(false)

  const position = running ? (steps[index] ?? null) : null

  const advance = useCallback(
    (delta: number, narrateOnly: boolean) => {
      narrateOnlyRef.current = narrateOnly
      pausedRef.current = false
      setStall(null)
      setIndex((current) => {
        const next = current + delta
        if (next < 0) return 0
        if (next >= steps.length) return steps.length - 1
        return next
      })
      setToken((current) => current + 1)
      setStatus('PLAYING')
    },
    [steps.length],
  )

  const start = useCallback(() => {
    if (!enabled) {
      // Status alone, deliberately: the overlay keys the blocked card off it,
      // and setting `running` here would start the step runner, whose first
      // act is to set the status back to PLAYING over an empty tour.
      setStatus('BLOCKED')
      return
    }
    // Return to the Command Center, which is where the script opens. Clearing a
    // previous run is the `controls` step's job, because Reset only exists once
    // this navigation has rendered.
    findAnchor('nav-overview')?.click()
    narrateOnlyRef.current = false
    pausedRef.current = false
    setStall(null)
    setIndex(0)
    setToken((current) => current + 1)
    setCursor(null)
    setRect(null)
    setStatus('PLAYING')
    setRunning(true)
  }, [enabled])

  const exit = useCallback(() => {
    pausedRef.current = false
    setRunning(false)
    setStatus('IDLE')
    setRect(null)
    setCursor(null)
    setStall(null)
  }, [])

  const pause = useCallback(() => {
    pausedRef.current = true
    setStatus((current) => (current === 'PLAYING' ? 'PAUSED' : current))
  }, [])

  const resume = useCallback(() => {
    pausedRef.current = false
    setStatus((current) => (current === 'PAUSED' || current === 'STALLED' ? 'PLAYING' : current))
  }, [])

  const next = useCallback(() => advance(1, false), [advance])
  const back = useCallback(() => advance(-1, true), [advance])

  // The runner. One pass per step; re-entered when the index or token changes.
  // `status` is deliberately not a dependency, so pausing freezes the current
  // step instead of restarting it.
  useEffect(() => {
    if (!running) return
    const current = steps[index]
    if (!current) return

    const controller = new AbortController()
    const { signal } = controller
    const isPaused = () => pausedRef.current
    const narrateOnly = narrateOnlyRef.current
    narrateOnlyRef.current = false

    const run = async () => {
      const step = current.step
      if (!pausedRef.current) setStatus('PLAYING')

      if (step.click && !narrateOnly) {
        const target = findAnchor(step.click)
        if (target) {
          scrollIntoView(target)
          await sleep(SETTLE_MS, signal, isPaused)
          setCursor(centreOf(target))
          await sleep(CURSOR_FLY_MS, signal, isPaused)
          setPressing(true)
          await sleep(CURSOR_PRESS_MS, signal, isPaused)
          // The real control, clicked the way a user would. Everything above
          // this line is presentation; this line is the actual interaction.
          findAnchor(step.click)?.click()
          setPressing(false)
          // The puck has done its job. Leaving it up would park a cursor on top
          // of the bubble this step is about to show.
          setCursor(null)
        }
      }

      if (step.until) {
        const satisfied = await waitFor(
          step.until,
          step.timeoutMs ?? DEFAULT_TIMEOUT_MS,
          signal,
          isPaused,
        )
        if (!satisfied) {
          setStall(`"${step.title}" is still waiting for the app to catch up.`)
          setStatus('STALLED')
          pausedRef.current = true
        }
      }

      if (step.anchor) {
        // Wait for the element rather than accepting whatever is on screen this
        // frame. Pages are lazy chunks, so the step after a navigation can be
        // reached while the target page is still a Suspense fallback, and
        // without this the bubble would flash as an unanchored centred card.
        const anchor = step.anchor
        const arrived = await waitFor(
          () => anchorPresent(anchor),
          step.timeoutMs ?? DEFAULT_TIMEOUT_MS,
          signal,
          isPaused,
        )
        if (!arrived) {
          setStall(`"${step.title}" cannot find what it is pointing at.`)
          setStatus('STALLED')
          pausedRef.current = true
        }
        const element = findAnchor(anchor)
        if (element) {
          scrollIntoView(element)
          await sleep(SETTLE_MS, signal, isPaused)
        }
      }

      await sleep(step.dwellMs * flags.dwellScale, signal, isPaused)

      if (current.globalIndex >= steps.length - 1) {
        setStatus('FINISHED')
        return
      }
      setIndex(current.globalIndex + 1)
      setToken((value) => value + 1)
    }

    run().catch((cause: unknown) => {
      if (cause !== ABORTED) throw cause
    })

    return () => {
      controller.abort()
      setPressing(false)
    }
  }, [running, index, token, steps, flags.dwellScale])

  // Track the spotlit rect every frame, so it follows the arm cards appearing,
  // the approval bar reflowing the page, and any smooth scroll still in flight.
  useEffect(() => {
    if (!running) return
    const anchor = steps[index]?.step.anchor
    if (!anchor) {
      setRect(null)
      return
    }
    let handle = 0
    const track = () => {
      const element = findAnchor(anchor)
      setRect(element ? element.getBoundingClientRect() : null)
      handle = requestAnimationFrame(track)
    }
    handle = requestAnimationFrame(track)
    return () => cancelAnimationFrame(handle)
  }, [running, index, steps])

  useEffect(() => {
    if (!flags.autostart || autostartedRef.current || !enabled) return
    autostartedRef.current = true
    start()
  }, [flags.autostart, enabled, start])

  // The blocked card is a dialog rather than a tour, so Escape dismisses it and
  // the step controls have nothing to act on.
  useEffect(() => {
    if (status !== 'BLOCKED') return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') exit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [status, exit])

  useEffect(() => {
    if (!running) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') exit()
      else if (event.key === 'ArrowRight') next()
      else if (event.key === 'ArrowLeft') back()
      else if (event.code === 'Space') {
        event.preventDefault()
        if (pausedRef.current) resume()
        else pause()
      } else return
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [running, exit, next, back, pause, resume])

  return {
    status,
    position,
    rect,
    cursor,
    pressing,
    stall,
    available: enabled,
    start,
    exit,
    pause,
    resume,
    next,
    back,
  }
}

export function tourStepCount(): number {
  return TOUR_CHAPTERS.reduce((total, chapter) => total + chapter.steps.length, 0)
}

export function tourBudgetMs(): number {
  return TOUR_CHAPTERS.reduce(
    (total, chapter) =>
      total + chapter.steps.reduce((sum: number, step: TourStep) => sum + step.dwellMs, 0),
    0,
  )
}
