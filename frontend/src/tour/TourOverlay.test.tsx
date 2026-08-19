import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TourOverlay } from './TourOverlay'
import type { TourController } from './engine'
import type { TourChapter, TourStatus } from './types'

const chapter: TourChapter = {
  id: 'chapter',
  title: 'Command Center',
  steps: [
    {
      id: 'schematic',
      anchor: 'port-schematic',
      title: 'The port, not a dashboard',
      body: 'Berths, the approach channel, yard blocks and reefer racks.',
      dwellMs: 9000,
    },
  ],
}

function controller(overrides: Partial<TourController> = {}): TourController {
  return {
    status: 'PLAYING',
    position: {
      chapter,
      step: chapter.steps[0],
      chapterIndex: 1,
      stepIndex: 0,
      globalIndex: 7,
      globalCount: 43,
    },
    rect: new DOMRect(120, 200, 400, 260),
    cursor: null,
    pressing: false,
    stall: null,
    available: true,
    start: vi.fn(),
    exit: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    next: vi.fn(),
    back: vi.fn(),
    ...overrides,
  }
}

afterEach(cleanup)

describe('TourOverlay', () => {
  it('renders nothing while the tour is idle', () => {
    const { container } = render(<TourOverlay tour={controller({ status: 'IDLE' })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the step and where it sits in the script', () => {
    render(<TourOverlay tour={controller()} />)
    expect(screen.getByRole('heading', { name: 'The port, not a dashboard' })).toBeVisible()
    expect(screen.getByText(/approach channel/)).toBeVisible()
    expect(screen.getByText('Step 8 of 43')).toBeVisible()
    expect(screen.getByText('2. Command Center')).toBeVisible()
  })

  it('puts the spotlight on the anchor rect', () => {
    const { container } = render(<TourOverlay tour={controller()} />)
    const spotlight = container.querySelector<HTMLElement>('.tour-spotlight')
    expect(spotlight).not.toBeNull()
    // Six pixels of breathing room on each side, so a focus ring is not clipped.
    expect(spotlight?.style.left).toBe('114px')
    expect(spotlight?.style.top).toBe('194px')
    expect(spotlight?.style.width).toBe('412px')
    expect(spotlight?.style.height).toBe('272px')
  })

  it('dims the whole page for a step with no anchor', () => {
    const base = controller()
    const { container } = render(
      <TourOverlay
        tour={{
          ...base,
          rect: null,
          position: { ...base.position!, step: { ...chapter.steps[0], placement: 'center' } },
        }}
      />,
    )
    expect(container.querySelector('.tour-scrim')).not.toBeNull()
    expect(container.querySelector('.tour-spotlight')).toBeNull()
    expect(container.querySelector('.tour-bubble--center')).not.toBeNull()
  })

  it('drives the transport controls', () => {
    const tour = controller()
    render(<TourOverlay tour={tour} />)

    fireEvent.click(screen.getByRole('button', { name: 'Skip to the next step' }))
    fireEvent.click(screen.getByRole('button', { name: 'Re-read the previous step' }))
    fireEvent.click(screen.getByRole('button', { name: 'Pause tour' }))
    fireEvent.click(screen.getByRole('button', { name: 'Exit tour' }))

    expect(tour.next).toHaveBeenCalledOnce()
    expect(tour.back).toHaveBeenCalledOnce()
    expect(tour.pause).toHaveBeenCalledOnce()
    expect(tour.exit).toHaveBeenCalledOnce()
  })

  it('disables previous on the first step', () => {
    const base = controller()
    render(
      <TourOverlay
        tour={{
          ...base,
          position: { ...base.position!, globalIndex: 0 },
        }}
      />,
    )

    expect(screen.getByRole('button', { name: 'Re-read the previous step' })).toBeDisabled()
  })

  it('offers resume once paused, and reports a stall', () => {
    const tour = controller({
      status: 'STALLED' as TourStatus,
      stall: '"Start the run" is still waiting for the app to catch up.',
    })
    render(<TourOverlay tour={tour} />)

    expect(screen.getByText(/still waiting for the app/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Resume tour' }))
    expect(tour.resume).toHaveBeenCalledOnce()
  })

  it('moves the transport out of the way and keeps the bubble clear of it', () => {
    // A panel taller than the viewport: the controls cannot stay at the bottom
    // without covering it, and the bubble cannot sit where they land.
    const { container } = render(
      <TourOverlay tour={controller({ rect: new DOMRect(260, 40, 1200, window.innerHeight) })} />,
    )

    expect(container.querySelector('.tour-transport')?.className).toContain('is-top')
    const bubble = container.querySelector<HTMLElement>('.tour-bubble')
    expect(Number.parseInt(bubble?.style.top ?? '0', 10)).toBeGreaterThanOrEqual(120)
  })

  it('explains itself instead of failing when the backend is down', () => {
    render(<TourOverlay tour={controller({ status: 'BLOCKED', available: false })} />)
    expect(screen.getByRole('heading', { name: 'The tour needs the backend' })).toBeVisible()
    expect(screen.getByText(/port 8620/)).toBeVisible()
  })
})
