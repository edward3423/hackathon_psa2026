import { useMemo } from 'react'
import { Play, ShieldCheck, ShieldAlert } from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { AnchorComparison, ArmResult, BenchmarkResult, FleetArm } from '../api/types'
import type { ArmSeries, BenchmarkStream } from '../hooks/useBenchmark'

/**
 * Act 2. Three arms replay April-August 2024 from a blind arrival feed: the
 * reconstructed recorded outcome, a reactive baseline, and CASCADE. Every
 * number here comes from the backend's single calculation path; this component
 * formats and never derives a headline figure of its own.
 */

const ARM_STYLE: Record<FleetArm, { label: string; colour: string; width: number }> = {
  HISTORICAL: { label: 'Recorded 2024 (reconstructed)', colour: '#8292a1', width: 1.6 },
  REACTIVE_BASELINE: { label: 'Reactive baseline', colour: '#c59a52', width: 1.6 },
  CASCADE_AGENTIC: { label: 'CASCADE agentic', colour: '#4ea3a8', width: 2 },
  CASCADE_NO_EXTRA_CAPACITY: { label: 'CASCADE without extra berths', colour: '#7f8fb0', width: 1.6 },
}

const RECORDED_PEAK_DAYS = 7
const RECOVERY_TARGET_DAYS = 2

interface ChartRow {
  date: string
  [arm: string]: string | number
}

function toChartRows(series: ArmSeries): ChartRow[] {
  const byDate = new Map<string, ChartRow>()
  for (const [arm, points] of Object.entries(series)) {
    for (const point of points) {
      const row = byDate.get(point.date) ?? { date: point.date }
      row[arm] = point.rollingWaitDays
      byDate.set(point.date, row)
    }
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
}

function shortDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
}

function days(value: number | null | undefined): string {
  return value === null || value === undefined ? 'not reached' : `${value.toFixed(2)} d`
}

function signed(value: number, unit: string): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)} ${unit}`
}

function ArmTiles({ arm }: { arm: ArmResult }) {
  const style = ARM_STYLE[arm.arm]
  return (
    <article className="benchmark-arm-card" data-arm={arm.arm}>
      <header>
        <span className="benchmark-arm-swatch" style={{ background: style.colour }} aria-hidden />
        <h3>{arm.label || style.label}</h3>
        <span className={`benchmark-provenance benchmark-provenance--${arm.provenance.toLowerCase()}`}>
          {arm.provenance}
        </span>
      </header>
      <dl className="benchmark-kpis">
        <div>
          <dt>Peak wait</dt>
          <dd>{days(arm.metrics.peak_wait_days)}</dd>
          <span>{shortDate(arm.metrics.peak_wait_date)}</span>
        </div>
        <div>
          <dt>Recovered to 2 d</dt>
          <dd>{arm.metrics.recovery_date ? shortDate(arm.metrics.recovery_date) : 'not reached'}</dd>
          <span>{arm.metrics.days_above_two_day_wait} days above 2 d</span>
        </div>
        <div>
          <dt>Mean wait</dt>
          <dd>{days(arm.metrics.mean_wait_days)}</dd>
          <span>port stay {arm.metrics.mean_port_stay_hours.toFixed(1)} h</span>
        </div>
        <div>
          <dt>Port-stay inflation</dt>
          <dd>{arm.metrics.port_stay_inflation_pct.toFixed(1)}%</dd>
          <span>vs its own 2023 baseline</span>
        </div>
      </dl>
      {arm.caveat && <p className="benchmark-caveat">{arm.caveat}</p>}
    </article>
  )
}

function AnchorTable({ anchors }: { anchors: AnchorComparison[] }) {
  if (anchors.length === 0) return null
  return (
    <section className="benchmark-anchors" aria-labelledby="benchmark-anchors-title">
      <header className="panel-heading">
        <div>
          <h3 id="benchmark-anchors-title">Simulated against recorded anchors</h3>
          <p className="panel-description">
            Published 2024 figures on the left; what the blind simulation produced on the right. A
            miss is shown as a miss.
          </p>
        </div>
      </header>
      <table className="benchmark-table">
        <thead>
          <tr>
            <th scope="col">Anchor</th>
            <th scope="col">Recorded</th>
            <th scope="col">Simulated</th>
            <th scope="col">Within tolerance</th>
          </tr>
        </thead>
        <tbody>
          {anchors.map((anchor) => (
            <tr key={anchor.anchor_key}>
              <th scope="row">{anchor.label}</th>
              <td>
                {anchor.recorded_value} {anchor.unit}
                <span className="benchmark-cell-note">{anchor.recorded_provenance}</span>
              </td>
              <td>
                {anchor.simulated_value.toFixed(2)} {anchor.unit}
              </td>
              <td className={anchor.within_tolerance ? 'status-healthy' : 'status-isolated'}>
                {anchor.within_tolerance ? 'YES' : `NO (+/- ${anchor.tolerance})`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function AuditBadge({ result }: { result: BenchmarkResult }) {
  const audited = result.arms.filter((arm) => arm.blind_audit)
  if (audited.length === 0) return null
  const reads = audited.reduce((total, arm) => total + (arm.blind_audit?.total_reads ?? 0), 0)
  const violations = audited.reduce((total, arm) => total + (arm.blind_audit?.violations ?? 0), 0)
  const lookahead = Math.max(...audited.map((arm) => arm.blind_audit?.max_lookahead_seconds ?? 0))
  const pass = violations === 0
  const Icon = pass ? ShieldCheck : ShieldAlert
  return (
    <div className={`benchmark-audit ${pass ? 'is-pass' : 'is-fail'}`} role="status">
      <Icon aria-hidden="true" size={18} />
      <strong>BLIND AUDIT {pass ? 'PASS' : 'FAIL'}</strong>
      <span>
        {reads} feed reads, max lookahead {lookahead.toFixed(0)} s, {violations} violations. The
        simulated arms could not read a day they had not yet entered.
      </span>
    </div>
  )
}

export interface BenchmarkPageProps {
  benchmark: BenchmarkStream
}

export function BenchmarkPage({ benchmark }: BenchmarkPageProps) {
  const { arms, series, decisions, result, playbackNotice, error, offline, running, start } =
    benchmark

  const rows = useMemo(() => toChartRows(series), [series])
  const drawnArms = arms.length > 0 ? arms : (result?.arms.map((arm) => arm.arm) ?? [])
  const decisionDates = useMemo(
    () => [...new Set(decisions.map((event) => event.decision?.date).filter(Boolean))] as string[],
    [decisions],
  )
  const headline = result?.comparisons.find(
    (comparison) =>
      comparison.arm === 'CASCADE_AGENTIC' && comparison.versus === 'REACTIVE_BASELINE',
  )

  return (
    <section className="benchmark-page" aria-labelledby="benchmark-title">
      <header className="page-section-header">
        <div>
          <h2 id="benchmark-title">Red Sea 2024 blind replay benchmark</h2>
          <p>
            The real Singapore arrival stream for 1 April to 31 August 2024, revealed one operating
            day at a time. Parameters were fitted on 2023 only; no arm can see the crisis coming.
          </p>
        </div>
        <button
          type="button"
          className="benchmark-run-button"
          onClick={() => void start()}
          disabled={running}
        >
          <Play aria-hidden="true" size={15} />
          {running ? 'Running' : 'Run benchmark'}
        </button>
      </header>

      {playbackNotice && (
        <p className={`benchmark-notice ${offline ? 'is-offline' : ''}`}>{playbackNotice}</p>
      )}
      {error && <p className="benchmark-error">{error}</p>}

      <figure className="benchmark-chart">
        <figcaption>
          Three-day rolling mean wait from arrival to berth, in days. Recorded peak and the
          two-day recovery target are drawn for reference.
        </figcaption>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#263746" strokeDasharray="2 4" />
            <XAxis
              dataKey="date"
              stroke="#8292a1"
              fontSize={11}
              tickFormatter={shortDate}
              minTickGap={36}
            />
            <YAxis
              stroke="#8292a1"
              fontSize={11}
              width={44}
              domain={[0, 8]}
              tickFormatter={(value: number) => `${value}d`}
            />
            <Tooltip
              contentStyle={{
                background: '#111b24',
                border: '1px solid #354655',
                color: '#e5edf3',
                fontSize: 12,
              }}
              labelFormatter={(value) => (typeof value === 'string' ? shortDate(value) : value)}
              formatter={(value) => (typeof value === 'number' ? `${value.toFixed(2)} d` : '-')}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: '#a9b7c3' }} />
            <ReferenceLine
              y={RECORDED_PEAK_DAYS}
              stroke="#c86d68"
              strokeDasharray="5 3"
              label={{
                value: 'recorded peak, late May',
                fill: '#c86d68',
                fontSize: 10,
                position: 'insideTopLeft',
                dy: -2,
              }}
            />
            <ReferenceLine
              y={RECOVERY_TARGET_DAYS}
              stroke="#c59a52"
              strokeDasharray="5 3"
              label={{
                value: 'recovery target',
                fill: '#c59a52',
                fontSize: 10,
                position: 'insideBottomRight',
              }}
            />
            {decisionDates.map((date) => (
              <ReferenceLine key={date} x={date} stroke="#4ea3a8" strokeOpacity={0.35} />
            ))}
            {drawnArms.map((arm) => (
              <Line
                key={arm}
                type="monotone"
                dataKey={arm}
                name={ARM_STYLE[arm].label}
                stroke={ARM_STYLE[arm].colour}
                strokeWidth={ARM_STYLE[arm].width}
                strokeDasharray={arm === 'HISTORICAL' ? '4 3' : undefined}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </figure>

      {headline && (
        <p className="benchmark-headline">
          CASCADE cut the peak wait by{' '}
          <strong>{headline.peak_wait_reduction_pct.toFixed(1)}%</strong> against the reactive
          baseline ({signed(headline.peak_wait_delta_days, 'd')} peak,{' '}
          {headline.recovery_days_saved == null
            ? 'no recovery comparison'
            : `${headline.recovery_days_saved.toFixed(0)} days earlier recovery`}
          ). This is one pinned run; the robustness claim is the sweep win-rate.
        </p>
      )}

      {result && (
        <>
          <div className="benchmark-arm-grid">
            {result.arms.map((arm) => (
              <ArmTiles arm={arm} key={arm.arm} />
            ))}
          </div>
          <AuditBadge result={result} />
          <AnchorTable anchors={result.anchor_comparisons} />
        </>
      )}

      {decisions.length > 0 && (
        <section className="benchmark-decisions" aria-labelledby="benchmark-decisions-title">
          <header className="panel-heading">
            <div>
              <h3 id="benchmark-decisions-title">Decisions CASCADE took, and when</h3>
              <p className="panel-description">
                Each was checked against bounds, lead times, and cooldowns before it could take
                effect. Rejected decisions are recorded, never quietly coerced.
              </p>
            </div>
          </header>
          <ol className="benchmark-decision-list">
            {decisions.map((event) => (
              <li key={event.event_id} data-accepted={event.decision?.accepted ? 'yes' : 'no'}>
                <span className="benchmark-decision-date">
                  {event.decision ? shortDate(event.decision.date) : ''}
                </span>
                <div>
                  <strong>{event.decision?.decision.type}</strong>
                  <p>{event.message}</p>
                  {event.decision?.rejection_reason && (
                    <p className="benchmark-decision-rejected">
                      Rejected: {event.decision.rejection_reason}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="benchmark-provenance-footer">
        <p>
          Arrival stream: IMF PortWatch daily port calls (portwatch.imf.org, IMF and University of
          Oxford), committed as a fixed snapshot. Vessel-level call sizes are synthesised from the
          2023 calibration window only.
        </p>
        <p>
          The recorded 2024 curve is a reconstruction anchored to published figures, not a
          per-vessel record; it is labelled RECONSTRUCTED wherever it is drawn. The simulated arms
          share one engine and one parameter set, so only their policies differ.
        </p>
        {result && (
          <p>
            Calibration {result.calibration_window.start} to {result.calibration_window.end}; blind
            window {result.blind_window.start} to {result.blind_window.end}; completed in{' '}
            {result.runtime_ms} ms.
          </p>
        )}
      </footer>
    </section>
  )
}
