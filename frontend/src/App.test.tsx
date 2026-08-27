import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import type { RunMode, WorkflowState } from './api/types'
import {
  analysis,
  baselineYard,
  dispute,
  planComparison,
  resetSequence,
  runCreated,
  scenario,
  traceEvent,
  workflowState,
} from './test/fixtures'

type Listener = (event: MessageEvent<string>) => void

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners = new Map<string, Set<Listener>>()
  onerror: (() => void) | null = null

  constructor(public url: string) {
    FakeEventSource.instances.push(this)
  }

  addEventListener(name: string, listener: EventListenerOrEventListenerObject) {
    const set = this.listeners.get(name) ?? new Set<Listener>()
    set.add(listener as Listener)
    this.listeners.set(name, set)
  }

  emit(name: string, data?: unknown) {
    for (const listener of this.listeners.get(name) ?? []) {
      listener({ data: JSON.stringify(data) } as MessageEvent<string>)
    }
  }

  close() {}
}

interface RecordedCall {
  url: string
  method: string
  body?: unknown
}

let runMode: RunMode
let currentState: WorkflowState
let calls: RecordedCall[]

function jsonResponse(payload: unknown): Response {
  return { ok: true, status: 200, json: async () => payload } as Response
}

function installFetch() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const path = url.split('?')[0]
      const method = init?.method ?? 'GET'
      calls.push({
        url,
        method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      })
      if (path.endsWith('/api/scenario')) return jsonResponse(scenario)
      if (path.endsWith('/api/runs') && method === 'POST') {
        const mode = url.includes('mode=DEMO_REPLAY') ? 'DEMO_REPLAY' : runMode
        return jsonResponse(runCreated(mode))
      }
      // Both endpoints return the whole updated WorkflowState, and the app
      // stores what they return. Answering them with {} made every field the
      // app reads afterwards silently undefined.
      if (path.endsWith('/api/runs/run-1/dispute-resolution')) return jsonResponse(currentState)
      if (path.endsWith('/api/runs/run-1/approval')) return jsonResponse(currentState)
      if (path.endsWith('/api/runs/run-1')) return jsonResponse(currentState)
      if (path.endsWith('/api/reset')) return jsonResponse(scenario)
      throw new Error(`Unexpected request: ${method} ${url}`)
    }),
  )
}

async function startRun() {
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: 'Start run' }))
  await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))
  return FakeEventSource.instances[0]
}

describe('CASCADE dashboard', () => {
  beforeEach(() => {
    resetSequence()
    FakeEventSource.instances = []
    runMode = 'LIVE_STUB'
    currentState = workflowState()
    calls = []
    vi.stubGlobal('EventSource', FakeEventSource)
    installFetch()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders the alert summary and objective from the scenario', async () => {
    render(<App />)

    expect((await screen.findAllByText('MV ATLAS STAR')).length).toBeGreaterThan(0)
    expect(screen.getByText('18 h')).toBeInTheDocument()
    expect(screen.getByText('Revised ETA')).toBeInTheDocument()
    expect(screen.getByText(scenario.objective)).toBeInTheDocument()
    expect(screen.getByText(`Synthetic data: ${scenario.synthetic_notice}`)).toBeInTheDocument()
  })

  it('exposes every workspace through an accessible collapsible sidebar', async () => {
    render(<App />)

    const navigation = await screen.findByRole('navigation', { name: 'CASCADE sections' })
    const labels = [
      'Command Center',
      'Connections',
      'Yard',
      'Reefers',
      'Agents',
      'Recovery',
      'Execution',
      'Replay',
      'System',
    ]

    for (const label of labels) {
      expect(within(navigation).getByRole('button', { name: label })).toBeInTheDocument()
    }

    expect(within(navigation).getByRole('button', { name: 'Command Center' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    fireEvent.click(within(navigation).getByRole('button', { name: 'Connections' }))
    expect(
      await screen.findByRole('heading', { name: 'Threatened transshipment connections' }),
    ).toBeInTheDocument()
    expect(within(navigation).getByRole('button', { name: 'Connections' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation sidebar' }))
    expect(screen.getByRole('button', { name: 'Expand navigation sidebar' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
    for (const label of labels) {
      expect(within(navigation).getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('shows graph totals equal to the analysis group sums', async () => {
    const source = await startRun()
    currentState = workflowState({
      stage: 'COMPLETE',
      results: { connection_analysis: analysis },
    })
    act(() => source.emit('trace', traceEvent({ kind: 'RUN_COMPLETED', stage: 'COMPLETE' })))

    const navigation = screen.getByRole('navigation', { name: 'CASCADE sections' })
    fireEvent.click(within(navigation).getByRole('button', { name: 'Connections' }))
    await screen.findByRole('heading', { name: 'Threatened transshipment connections' })

    const sum = (status: string) =>
      analysis.groups
        .filter((group) => group.status === status)
        .reduce((total, group) => total + group.container_count, 0)

    await waitFor(() => {
      expect(screen.getByTestId('total-safe')).toHaveTextContent(String(sum('SAFE')))
    })
    expect(screen.getByTestId('total-at-risk')).toHaveTextContent(String(sum('AT_RISK')))
    expect(screen.getByTestId('total-missed')).toHaveTextContent(String(sum('MISSED')))
    expect(screen.getByTestId('total-resolved')).toHaveTextContent(String(sum('RESOLVED')))
  })

  it('opens the dispute overlay on DISPUTE_OPENED, posts the resolution, and closes', async () => {
    const source = await startRun()
    currentState = workflowState({ stage: 'DISPUTE', active_dispute: dispute })
    act(() =>
      source.emit(
        'trace',
        traceEvent({ kind: 'DISPUTE_OPENED', stage: 'DISPUTE', confidence: 'LOW' }),
      ),
    )

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(dispute.question)).toBeInTheDocument()
    expect(screen.getByText(dispute.positions[0].evidence[0])).toBeInTheDocument()
    expect(screen.getByText(dispute.positions[1].evidence[0])).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Respect physical reefer plug capacity' }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: dispute.positions[1].position }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm constraint' }))

    await waitFor(() => {
      const post = calls.find((call) => call.url.endsWith('/dispute-resolution'))
      expect(post?.body).toEqual({
        dispute_id: 'disp-1',
        confirmed_constraint: dispute.positions[1].position,
      })
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('keeps Reset working while the dispute overlay is open', async () => {
    const source = await startRun()
    currentState = workflowState({ stage: 'DISPUTE', active_dispute: dispute })
    act(() =>
      source.emit(
        'trace',
        traceEvent({ kind: 'DISPUTE_OPENED', stage: 'DISPUTE', confidence: 'LOW' }),
      ),
    )
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    // The paused dispute must not strand the presenter: the top-bar Reset
    // stays clickable and clears the run, dispute overlay included.
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))

    await waitFor(() => {
      const reset = calls.find(
        (call) => call.url.endsWith('/api/reset') && call.method === 'POST',
      )
      expect(reset).toBeDefined()
    })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('hides the approval bar until AWAITING_APPROVAL and posts the decision', async () => {
    const source = await startRun()
    act(() => source.emit('trace', traceEvent({ kind: 'AGENT_STARTED', stage: 'ASSESSING' })))

    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Human approval' })).not.toBeInTheDocument()

    currentState = workflowState({
      stage: 'AWAITING_APPROVAL',
      results: { plan_comparison: planComparison },
    })
    act(() =>
      source.emit(
        'trace',
        traceEvent({ kind: 'APPROVAL_REQUIRED', stage: 'AWAITING_APPROVAL' }),
      ),
    )

    const approve = await screen.findByRole('button', { name: 'Approve' })
    await waitFor(() => expect(approve).toBeEnabled())
    expect(screen.getByRole('region', { name: 'Human approval' })).toHaveTextContent(
      'Optimized Hybrid',
    )
    fireEvent.click(approve)

    const confirmation = await screen.findByRole('dialog', {
      name: 'Confirm simulated execution',
    })
    expect(confirmation).toHaveTextContent('Optimized Hybrid')
    expect(confirmation).toHaveTextContent('Simulation only')
    expect(calls.some((call) => call.url.endsWith('/approval'))).toBe(false)

    fireEvent.click(within(confirmation).getByRole('button', { name: 'Cancel' }))
    await waitFor(() =>
      expect(
        screen.queryByRole('dialog', { name: 'Confirm simulated execution' }),
      ).not.toBeInTheDocument(),
    )
    expect(calls.some((call) => call.url.endsWith('/approval'))).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))
    const reconfirmation = await screen.findByRole('dialog', {
      name: 'Confirm simulated execution',
    })
    fireEvent.click(
      within(reconfirmation).getByRole('button', { name: 'Confirm simulated execution' }),
    )

    await waitFor(() => {
      const post = calls.find((call) => call.url.endsWith('/approval'))
      expect(post?.body).toEqual({ plan_archetype: 'OPTIMIZED_HYBRID', decision: 'APPROVED' })
    })
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument(),
    )
  })

  it('renders mocked receipts after dispatch events', async () => {
    const source = await startRun()
    expect(screen.queryByText('EXECUTION RECEIPTS (MOCKED)')).not.toBeInTheDocument()

    currentState = workflowState({
      stage: 'EXECUTING',
      results: {
        connection_analysis: analysis,
        baseline_yard: baselineYard,
        receipts: [
          {
            action_id: 'act-1',
            status: 'ACCEPTED',
            receipt_ref: 'WO-2042-001',
            detail: 'Terminal work order accepted by mocked TOS.',
          },
          {
            action_id: 'act-2',
            status: 'REJECTED',
            receipt_ref: null,
            detail: 'Carrier notice rejected by validator.',
          },
        ],
      },
    })
    act(() =>
      source.emit('trace', traceEvent({ kind: 'ACTION_DISPATCHED', stage: 'EXECUTING' })),
    )

    const navigation = screen.getByRole('navigation', { name: 'CASCADE sections' })
    fireEvent.click(within(navigation).getByRole('button', { name: 'Execution' }))

    expect(await screen.findByText('EXECUTION RECEIPTS (MOCKED)')).toBeInTheDocument()
    expect(screen.getByText('WO-2042-001')).toBeInTheDocument()
    expect(screen.getByText('ACCEPTED')).toBeInTheDocument()
    expect(screen.getByText('REJECTED')).toBeInTheDocument()
  })

  it('shows a persistent DEMO REPLAY label when a replay run starts', async () => {
    render(<App />)
    // The replay trigger lives inside the backtick debug panel now, so the
    // test walks the same two clicks a presenter would.
    fireEvent.click(await screen.findByRole('button', { name: 'Debug' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Start demo replay' }))
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))

    await waitFor(() => {
      expect(document.querySelector('.top-bar .replay-badge')).toHaveTextContent('DEMO REPLAY')
    })
    const post = calls.find((call) => call.url.includes('/api/runs?'))
    expect(post?.url).toContain('mode=DEMO_REPLAY')
  })
})
