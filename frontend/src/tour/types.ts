import type { TourAnchor } from './anchors'

export type TourPlacement = 'auto' | 'top' | 'bottom' | 'left' | 'right' | 'center'

export type TourStatus = 'IDLE' | 'PLAYING' | 'PAUSED' | 'STALLED' | 'BLOCKED' | 'FINISHED'

export interface TourStep {
  /** Stable id, unique across the whole script. Used as the React key. */
  id: string
  /**
   * The element to spotlight. Omitted for a centred card that belongs to no
   * particular control - the opening and closing beats.
   */
  anchor?: TourAnchor
  /** Bubble heading. Names what is on screen. */
  title: string
  /** Bubble body. Says why it matters; never a paraphrase of visible copy. */
  body: string
  placement?: TourPlacement
  /**
   * Clicked before the bubble appears. The cursor flies here and ripples first,
   * but the click itself is a real `.click()` on the real control, so the tour
   * cannot drift away from what a user pressing that button would get.
   */
  click?: TourAnchor
  /**
   * The step waits here until this holds. Advancing on a condition rather than a
   * timer means a slow backend delays the tour instead of desynchronising it.
   */
  until?: () => boolean
  /** How long the bubble stays up once `until` holds. The reading budget. */
  dwellMs: number
  /** How long to wait for `until` before declaring the step stalled. */
  timeoutMs?: number
}

export interface TourChapter {
  id: string
  title: string
  steps: TourStep[]
}

/** A step plus where it sits in the flattened script, for the transport bar. */
export interface TourPosition {
  chapter: TourChapter
  step: TourStep
  chapterIndex: number
  stepIndex: number
  /** 0-based index across every step in every chapter. */
  globalIndex: number
  globalCount: number
}
