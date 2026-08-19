import { describe, expect, it } from 'vitest'

import { TOUR_ANCHORS } from './anchors'
import { tourBudgetMs, tourStepCount } from './engine'
import { TOUR_CHAPTERS } from './script'

const steps = TOUR_CHAPTERS.flatMap((chapter) => chapter.steps)

describe('tour script', () => {
  it('names only anchors that exist', () => {
    const known = new Set(Object.keys(TOUR_ANCHORS))
    for (const step of steps) {
      if (step.anchor) expect(known, `${step.id} anchor`).toContain(step.anchor)
      if (step.click) expect(known, `${step.id} click`).toContain(step.click)
    }
  })

  it('gives every step a unique id', () => {
    const ids = steps.map((step) => step.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(tourStepCount()).toBe(ids.length)
  })

  it('gives every chapter a title and at least one step', () => {
    for (const chapter of TOUR_CHAPTERS) {
      expect(chapter.title.length).toBeGreaterThan(0)
      expect(chapter.steps.length).toBeGreaterThan(0)
    }
  })

  it('runs about five minutes of reading time', () => {
    const budget = tourBudgetMs()
    expect(budget).toBeGreaterThanOrEqual(280_000)
    expect(budget).toBeLessThanOrEqual(320_000)
  })

  // A click changes the app, so the step that fires it has to wait for the
  // result. Without a condition the next bubble would narrate a screen that has
  // not arrived yet, which is exactly the desynchronisation the engine avoids.
  it('waits on a condition after every click that changes the page', () => {
    for (const step of steps) {
      if (!step.click) continue
      expect(step.until, `${step.id} clicks without waiting`).toBeTypeOf('function')
    }
  })

  it('writes a title and a body for every step', () => {
    for (const step of steps) {
      expect(step.title.length, step.id).toBeGreaterThan(0)
      expect(step.body.length, step.id).toBeGreaterThan(40)
      expect(step.dwellMs, step.id).toBeGreaterThan(0)
    }
  })

  it('anchors every step that is not a centred card', () => {
    for (const step of steps) {
      if (step.placement === 'center') continue
      expect(step.anchor, `${step.id} has nothing to point at`).toBeTruthy()
    }
  })
})
