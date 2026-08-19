import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { readTourFlags, tourStepCount, useTour } from './engine'

afterEach(cleanup)

describe('readTourFlags', () => {
  it('reads the recording modes, together or apart', () => {
    expect(readTourFlags('')).toEqual({ autostart: false, dwellScale: 1 })
    expect(readTourFlags('?tour=auto')).toEqual({ autostart: true, dwellScale: 1 })
    expect(readTourFlags('?tour=fast')).toEqual({ autostart: false, dwellScale: 0.05 })
    expect(readTourFlags('?tour=auto,fast')).toEqual({ autostart: true, dwellScale: 0.05 })
  })
})

describe('useTour', () => {
  it('blocks instead of playing a hollow tour when the backend is missing', () => {
    const { result } = renderHook(() => useTour({ enabled: false, search: '' }))

    expect(result.current.available).toBe(false)
    act(() => result.current.start())

    // Blocked has to survive the effects that run after start(): the step
    // runner's first act is to set PLAYING, so anything that wakes it here
    // would replace the explanation with an empty tour.
    expect(result.current.status).toBe('BLOCKED')
    expect(result.current.position).toBeNull()

    act(() => result.current.exit())
    expect(result.current.status).toBe('IDLE')
  })

  it('ignores the autostart flag while blocked', () => {
    const { result } = renderHook(() => useTour({ enabled: false, search: '?tour=auto' }))
    expect(result.current.status).toBe('IDLE')
  })

  it('opens on the first step of the script', () => {
    const { result } = renderHook(() => useTour({ enabled: true, search: '' }))
    act(() => result.current.start())

    expect(result.current.status).toBe('PLAYING')
    expect(result.current.position?.globalIndex).toBe(0)
    expect(result.current.position?.globalCount).toBe(tourStepCount())
  })
})
