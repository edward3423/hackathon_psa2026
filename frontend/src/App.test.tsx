import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const scenario = {
  name: 'MV ATLAS STAR 18-hour delay',
  description: 'A synthetic delay threatens onward connections.',
  alert: {
    vessel_name: 'MV ATLAS STAR',
    port_call: 'SGSIN-PSA-2042',
    original_eta: '2026-09-14T06:00:00Z',
    revised_eta: '2026-09-15T00:00:00Z',
    event_time: '2026-09-13T18:00:00Z',
    synthetic: true,
    delay_hours: 18,
  },
  objective: 'Protect critical cargo and reduce missed connections.',
  planning_horizon_hours: 72,
  controls: {
    delay_hours: 18,
    priority_emphasis: 'BALANCED',
    alternative_sailing_failure: true,
  },
  synthetic_notice: 'All values are synthetic.',
}

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners = new Map<string, (event: MessageEvent<string>) => void>()
  onerror: (() => void) | null = null

  constructor(public url: string) {
    FakeEventSource.instances.push(this)
  }

  addEventListener(name: string, listener: EventListenerOrEventListenerObject) {
    this.listeners.set(name, listener as (event: MessageEvent<string>) => void)
  }

  close() {}
}

describe('CASCADE foundation dashboard', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => scenario,
    }))
  })

  afterEach(() => vi.unstubAllGlobals())

  it('renders the golden alert and all five agents', async () => {
    render(<App />)

    expect(await screen.findByText('MV ATLAS STAR')).toBeInTheDocument()
    expect(screen.getByText('Coordinator Agent')).toBeInTheDocument()
    expect(screen.getByText('Impact Agent')).toBeInTheDocument()
    expect(screen.getByText('Yard Agent')).toBeInTheDocument()
    expect(screen.getByText('Recovery Agent')).toBeInTheDocument()
    expect(screen.getByText('Execution Agent')).toBeInTheDocument()
  })

  it('starts a run and opens the returned event stream', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => scenario } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run_id: 'run-1',
          mode: 'LIVE_STUB',
          stage: 'READY',
          events_url: '/api/runs/run-1/events',
        }),
      } as Response)

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start analysis' }))

    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))
    expect(FakeEventSource.instances[0].url).toBe('/api/runs/run-1/events')
  })
})

