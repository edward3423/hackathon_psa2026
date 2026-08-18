import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BenchmarkPage } from './BenchmarkPage'
import { MOCK_BENCHMARK_RESULT, OFFLINE_BENCHMARK_NOTICE } from '../data/demo'
import { useBenchmark } from '../hooks/useBenchmark'

/**
 * Act 2 driven by the committed offline mock. The backend is unreachable, so
 * `useBenchmark` falls back to MOCK_BENCHMARK_RESULT and the page has to stay
 * honest about it: the recorded arm is a reconstruction rather than a record,
 * the anchor rows are context rather than a score, and every one of those
 * statements has to reach the screen rather than sit in the payload.
 */

function BenchmarkHarness() {
  return <BenchmarkPage benchmark={useBenchmark()} />
}

/**
 * Run the benchmark offline and drain the playback timers, so the assertions
 * below see the completed result. Fake timers make Testing Library's `waitFor`
 * deadlock, so this resolves everything up front and the tests stay synchronous.
 */
async function playOfflineBenchmark() {
  render(<BenchmarkHarness />)
  fireEvent.click(screen.getByRole('button', { name: 'Run benchmark' }))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(OFFLINE_PLAYBACK_MS)
  })
}

/** 12 ms per day for the longest arm, plus slack. */
const OFFLINE_PLAYBACK_MS =
  Math.max(...MOCK_BENCHMARK_RESULT.arms.map((arm) => arm.daily.length)) * 12 + 100

/** Scoped to the tile grid: the legend repeats every arm label. */
function armCard(label: string): HTMLElement {
  const grid = document.querySelector('.benchmark-arm-grid') as HTMLElement
  return within(grid).getByText(label).closest('.benchmark-arm-card') as HTMLElement
}

const HISTORICAL = MOCK_BENCHMARK_RESULT.arms.find((arm) => arm.arm === 'HISTORICAL')!
const CASCADE = MOCK_BENCHMARK_RESULT.arms.find((arm) => arm.arm === 'CASCADE_AGENTIC')!

describe('Crisis Benchmark page', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // A network-level failure (TypeError) is what triggers the offline path.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('draws one line per arm, each named in the legend', async () => {
    await playOfflineBenchmark()

    const chart = document.querySelector('.benchmark-chart')!
    expect(chart.querySelectorAll('.recharts-line')).toHaveLength(MOCK_BENCHMARK_RESULT.arms.length)

    const legend = chart.querySelector('.recharts-legend-wrapper')!
    for (const arm of MOCK_BENCHMARK_RESULT.arms) {
      expect(legend).toHaveTextContent(arm.label)
    }
  })

  it('labels the recorded arm as a reconstruction wherever it is drawn', async () => {
    await playOfflineBenchmark()

    const card = armCard(HISTORICAL.label)
    expect(card).toHaveTextContent('RECONSTRUCTED')
    expect(card).toHaveTextContent(HISTORICAL.caveat!)

    // A viewer reading only the chart must not mistake the grey line for a
    // per-vessel record, so the legend name carries the caveat too.
    expect(HISTORICAL.label).toMatch(/reconstructed/i)
    expect(document.querySelector('.recharts-legend-wrapper')).toHaveTextContent(HISTORICAL.label)

    // Every other arm is marked as simulated, never as recorded.
    for (const arm of MOCK_BENCHMARK_RESULT.arms.filter((candidate) => candidate.is_simulation)) {
      expect(armCard(arm.label)).toHaveTextContent('SIMULATED')
    }

    expect(screen.getByText(/labelled RECONSTRUCTED wherever it is drawn/)).toBeVisible()

    // The reconstruction is a wait curve and nothing more. Its port-stay
    // fields arrive as zero, and a tile reading "0.0%" would be a fabricated
    // measurement rather than a missing one.
    expect(HISTORICAL.metrics.port_stay_inflation_pct).toBe(0)
    expect(card).toHaveTextContent('not reconstructed')
    expect(card).toHaveTextContent('port stay not reconstructed')
    expect(card).not.toHaveTextContent('0.0%')
    expect(card).not.toHaveTextContent('port stay 0.0 h')
  })

  it('shows the blind audit as PASS with no violations', async () => {
    await playOfflineBenchmark()

    const badge = screen.getByRole('status')
    expect(badge).toHaveTextContent('BLIND AUDIT PASS')
    expect(badge).toHaveTextContent('0 violations')
    expect(badge).toHaveTextContent('max lookahead 0 s')
    expect(badge).toHaveClass('is-pass')
  })

  it('populates the KPI tiles from the result metrics', async () => {
    await playOfflineBenchmark()

    const card = armCard(CASCADE.label)
    const metrics = CASCADE.metrics
    expect(card).toHaveTextContent(`${metrics.peak_wait_days.toFixed(2)} d`)
    expect(card).toHaveTextContent(`${metrics.mean_wait_days.toFixed(2)} d`)
    expect(card).toHaveTextContent(`${metrics.days_above_two_day_wait} days above 2 d`)
    expect(card).toHaveTextContent(`port stay ${metrics.mean_port_stay_hours.toFixed(1)} h`)
    expect(card).toHaveTextContent(`${metrics.port_stay_inflation_pct.toFixed(1)}%`)

    // No tile is left as a placeholder, and none renders a broken number.
    const cards = document.querySelectorAll('.benchmark-arm-card')
    expect(cards).toHaveLength(MOCK_BENCHMARK_RESULT.arms.length)
    for (const each of cards) {
      expect(each).not.toHaveTextContent('NaN')
      expect(each).not.toHaveTextContent('undefined')
      expect(each.querySelectorAll('.benchmark-kpis dd')).toHaveLength(4)
    }
  })

  it('renders the benchmark notice to the user, not only in the payload', async () => {
    await playOfflineBenchmark()

    const notice = screen.getByText(MOCK_BENCHMARK_RESULT.notice)
    expect(notice).toBeVisible()
    expect(notice.closest('.benchmark-scope-notice')).not.toBeNull()

    // It is the claim statement, so it must say what is not being claimed.
    expect(notice).toHaveTextContent(/not a reproduction of history/i)
    expect(notice).toHaveTextContent(/does not reproduce the recorded 2024 congestion/i)

    // The offline playback notice is a separate statement and stays separate:
    // one says how the curves were obtained, the other what they mean.
    const offline = screen.getByText(OFFLINE_BENCHMARK_NOTICE)
    expect(offline).toBeVisible()
    expect(offline).toHaveClass('is-offline')
    expect(offline).not.toBe(notice)
  })

  it('gives every anchor row its interpretation and never grades it', async () => {
    await playOfflineBenchmark()

    const anchors = MOCK_BENCHMARK_RESULT.anchor_comparisons
    expect(anchors.length).toBeGreaterThan(0)

    const table = document.querySelector('.benchmark-table')!
    for (const anchor of anchors) {
      expect(anchor.interpretation).not.toBe('')
      expect(screen.getByText(anchor.interpretation)).toBeVisible()
    }

    // `within_tolerance` is context, not a score, so no row is ticked or
    // coloured as a pass.
    expect(table.querySelectorAll('.status-healthy')).toHaveLength(0)
    expect(table.querySelectorAll('.status-isolated')).toHaveLength(0)
    expect(table).not.toHaveTextContent('YES')
    expect(screen.getByRole('columnheader', { name: 'Gap' })).toBeInTheDocument()
    expect(
      screen.queryByRole('columnheader', { name: /within tolerance/i }),
    ).not.toBeInTheDocument()

    // The row that lands inside tolerance for the wrong reason says so.
    const coincidence = anchors.find((anchor) => anchor.anchor_key === 'recovered_wait_days')!
    expect(coincidence.within_tolerance).toBe(true)
    expect(coincidence.interpretation).toMatch(/coincidence, not agreement/i)
    const row = screen.getByText(coincidence.interpretation).closest('tr')!
    expect(row.previousElementSibling).toHaveTextContent('inside +/- 1')
  })

  it('states the headline gain as one pinned run rather than a general claim', async () => {
    await playOfflineBenchmark()

    const comparison = MOCK_BENCHMARK_RESULT.comparisons[0]
    const headline = document.querySelector('.benchmark-headline')!
    expect(headline).toHaveTextContent(`${comparison.peak_wait_reduction_pct.toFixed(1)}%`)
    expect(headline).toHaveTextContent('This is one pinned run')
  })
})
