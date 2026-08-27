import { Fragment, useMemo } from 'react'
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
import {
  axisProps,
  CHART_ACCENT,
  CHART_INK,
  CHART_INK_SOFT,
  gridProps,
  legendLabel,
  legendStyle,
  tooltipStyle,
} from '../lib/chartTheme'

/**
 * Act 2. Three arms replay April-August 2024 from a blind arrival feed: the
 * reconstructed recorded outcome, a reactive baseline, and CASCADE. Every
 * number here comes from the backend's single calculation path; this component
 * formats and never derives a headline figure of its own.
 */

/*
 * Four arms on one monochrome chart, so identity is the dash pattern, not the
 * hue. The accent is spent on the one arm the page is arguing about; the other
 * three are ink at three dash lengths, and the swatch beside each tile draws the
 * same pattern so the legend and the tiles agree.
 */
const ARM_STYLE: Record<
  FleetArm,
  { label: string; colour: string; width: number; dash?: string }
> = {
  HISTORICAL: {
    label: 'Recorded 2024 (reconstructed)',
    colour: CHART_INK_SOFT,
    width: 2,
    dash: '2 3',
  },
  REACTIVE_BASELINE: {
    label: 'Reactive baseline',
    colour: CHART_INK_SOFT,
    width: 2,
    dash: '7 4',
  },
  CASCADE_AGENTIC: { label: 'CASCADE agentic', colour: CHART_ACCENT, width: 2.5 },
  CASCADE_NO_EXTRA_CAPACITY: {
    label: 'CASCADE without extra berths',
    colour: CHART_INK,
    width: 2,
    dash: '10 3 2 3',
  },
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

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

function signed(value: number, unit: string): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)} ${unit}`
}

/**
 * An arm that never crossed the two-day threshold has nothing to recover from,
 * and saying "not reached" about it would read as a failure rather than as the
 * best possible outcome.
 */
function recoveryLabel(metrics: ArmResult['metrics']): string {
  if (metrics.days_above_two_day_wait === 0) return 'never above 2 d'
  return metrics.recovery_date ? shortDate(metrics.recovery_date) : 'not reached'
}

type DecisionEvent = BenchmarkStream['decisions'][number]

interface DecisionRun {
  key: string
  type: string
  /** The latest rationale in the run; the only one for a run of one. */
  message: string
  accepted: boolean
  rejectionReason: string | null
  firstDate: string
  lastDate: string
  count: number
}

/**
 * What a decision *is*, ignoring the reading that prompted it. Two HOLDs are
 * the same decision even though their rationales quote a different rolling
 * wait, and it is the sameness of the decision that makes a row redundant.
 */
function decisionIdentity(decision: NonNullable<DecisionEvent['decision']>): string {
  const it = decision.decision
  return [
    it.type,
    it.tranche_id ?? '',
    it.discipline ?? '',
    it.enabled ?? '',
    it.surge_level ?? '',
    decision.accepted,
    decision.rejection_reason ?? '',
  ].join('|')
}

/**
 * Consecutive identical decisions become one row.
 *
 * The controller reviews policy every epoch across five months, and on most of
 * them the honest answer is HOLD. Drawn one per line that is twenty-odd
 * indistinguishable rows burying the two decisions that actually changed how
 * the port ran, which inverts what the panel is for. Collapsing a run keeps
 * every epoch accounted for - the count and the span say how many and when -
 * while letting a real decision stand out by being the only thing near it.
 *
 * Only consecutive runs collapse, so the sequence stays in order and a repeat
 * after a change is never folded into the run before it.
 */
function collapseDecisions(events: DecisionEvent[]): DecisionRun[] {
  const runs: DecisionRun[] = []
  let previousIdentity: string | null = null
  for (const event of events) {
    const decision = event.decision
    if (!decision) continue
    const identity = decisionIdentity(decision)
    const previous = runs[runs.length - 1]
    if (previous && identity === previousIdentity) {
      previous.lastDate = decision.date
      previous.message = event.message
      previous.count += 1
      continue
    }
    previousIdentity = identity
    runs.push({
      key: event.event_id,
      type: decision.decision.type,
      message: event.message,
      accepted: decision.accepted,
      rejectionReason: decision.rejection_reason ?? null,
      firstDate: decision.date,
      lastDate: decision.date,
      count: 1,
    })
  }
  return runs
}

function ArmTiles({ arm }: { arm: ArmResult }) {
  const style = ARM_STYLE[arm.arm]
  return (
    <article className="benchmark-arm-card" data-arm={arm.arm}>
      <header>
        <span className="benchmark-arm-swatch" aria-hidden>
          <svg width="22" height="10" viewBox="0 0 22 10">
            <line
              x1="0"
              y1="5"
              x2="22"
              y2="5"
              stroke={style.colour}
              strokeWidth={style.width}
              strokeDasharray={style.dash}
            />
          </svg>
        </span>
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
          <dd>{recoveryLabel(arm.metrics)}</dd>
          <span>{plural(arm.metrics.days_above_two_day_wait, 'day')} above 2 d</span>
        </div>
        <div>
          <dt>Mean wait</dt>
          <dd>{days(arm.metrics.mean_wait_days)}</dd>
          {/* The reconstruction is a wait curve and nothing else. Its port-stay
              fields arrive as zero because the backend refuses to invent them,
              so they are reported as absent rather than drawn as 0.0. */}
          <span>
            {arm.is_simulation
              ? `port stay ${arm.metrics.mean_port_stay_hours.toFixed(1)} h`
              : 'port stay not reconstructed'}
          </span>
        </div>
        <div>
          <dt>Port-stay inflation</dt>
          <dd>
            {arm.is_simulation
              ? `${arm.metrics.port_stay_inflation_pct.toFixed(1)}%`
              : 'not reconstructed'}
          </dd>
          <span>
            {arm.is_simulation
              ? 'vs its own 2023 baseline'
              : 'no port-stay series exists for this curve'}
          </span>
        </div>
      </dl>
      {arm.caveat && <p className="benchmark-caveat">{arm.caveat}</p>}
    </article>
  )
}

function AnchorTable({ anchors }: { anchors: AnchorComparison[] }) {
  if (anchors.length === 0) return null
  return (
    <section
      className="benchmark-anchors"
      aria-labelledby="benchmark-anchors-title"
      data-tour="benchmark-anchors"
    >
      <header className="panel-heading">
        <div>
          <h3 id="benchmark-anchors-title">Simulated against recorded anchors</h3>
          <p className="panel-description">
            Published 2024 figures on the left; what the blind simulation produced on the right.
            These rows are context, not a score. The model is not expected to reproduce the
            recorded crisis, so each row states which way it should miss and why - including the
            row that lands inside tolerance for the wrong reason.
          </p>
        </div>
      </header>
      <table className="benchmark-table">
        <thead>
          <tr>
            <th scope="col">Anchor</th>
            <th scope="col">Recorded</th>
            <th scope="col">Simulated</th>
            <th scope="col">Gap</th>
          </tr>
        </thead>
        <tbody>
          {anchors.map((anchor) => (
            <Fragment key={anchor.anchor_key}>
              <tr className="benchmark-anchor-row">
                <th scope="row">{anchor.label}</th>
                <td>
                  {anchor.recorded_value} {anchor.unit}
                  <span className="benchmark-cell-note">{anchor.recorded_provenance}</span>
                </td>
                <td>
                  {anchor.simulated_value.toFixed(2)} {anchor.unit}
                </td>
                <td>
                  {signed(anchor.simulated_value - anchor.recorded_value, anchor.unit)}
                  <span className="benchmark-cell-note">
                    {anchor.within_tolerance ? 'inside' : 'outside'} +/- {anchor.tolerance}{' '}
                    {anchor.unit}
                  </span>
                </td>
              </tr>
              <tr className="benchmark-anchor-reading">
                <td colSpan={4}>{anchor.interpretation}</td>
              </tr>
            </Fragment>
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
    <div
      className={`benchmark-audit ${pass ? 'is-pass' : 'is-fail'}`}
      role="status"
      data-tour="benchmark-audit"
    >
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
  const decisionRuns = useMemo(() => collapseDecisions(decisions), [decisions])
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
          data-tour="benchmark-run"
          onClick={() => void start()}
          disabled={running}
        >
          <Play aria-hidden="true" size={15} />
          {running ? 'Running' : 'Run benchmark'}
        </button>
      </header>

      {result && (
        <div className="benchmark-result-summary" aria-label="Benchmark result summary">
          <AuditBadge result={result} />
          {headline && (
            <p className="benchmark-headline" data-tour="benchmark-headline">
              CASCADE cut the peak wait by{' '}
              <strong>{headline.peak_wait_reduction_pct.toFixed(1)}%</strong> against the reactive
              baseline ({signed(headline.peak_wait_delta_days, 'd')} peak,{' '}
              {headline.recovery_days_saved == null
                ? 'no recovery comparison'
                : `${headline.recovery_days_saved.toFixed(0)} days earlier recovery`}
              ). This is one pinned run; the robustness claim is the sweep win-rate.
            </p>
          )}
        </div>
      )}

      {result?.notice && (
        <aside className="benchmark-scope-notice" aria-labelledby="benchmark-scope-title">
          <h3 id="benchmark-scope-title">What this benchmark claims</h3>
          <p>
            A controlled comparison of three policies using the same blind arrival stream. It is
            not a reproduction of historical port operations or a prediction about individual
            vessels.
          </p>
          <details>
            <summary>Methodology and limitations</summary>
            <p>{result.notice}</p>
          </details>
        </aside>
      )}
      {playbackNotice && (
        <p className={`benchmark-notice ${offline ? 'is-offline' : ''}`}>{playbackNotice}</p>
      )}
      {error && <p className="benchmark-error">{error}</p>}

      <figure className="benchmark-chart" data-tour="benchmark-chart">
        <figcaption>
          Three-day rolling mean wait from arrival to berth, in days. Recorded peak and the
          two-day recovery target are drawn for reference.
        </figcaption>
        {/* Before a run there is no series, and an empty 320px plot frame reads as
            a chart that failed rather than one nobody has asked for yet. The
            figure itself stays mounted, because the guided tour anchors it. */}
        {rows.length === 0 ? (
          <p className="benchmark-chart__empty">
            Run the benchmark to replay 153 days of arrivals through the three arms.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid {...gridProps} vertical={false} />
              <XAxis dataKey="date" {...axisProps} tickFormatter={shortDate} minTickGap={36} />
              <YAxis
                {...axisProps}
                width={44}
                domain={[0, 8]}
                tickFormatter={(value: number) => `${value}d`}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelFormatter={(value) => (typeof value === 'string' ? shortDate(value) : value)}
                formatter={(value) => (typeof value === 'number' ? `${value.toFixed(2)} d` : '-')}
              />
              <Legend wrapperStyle={legendStyle} formatter={legendLabel} />
              <ReferenceLine
                y={RECORDED_PEAK_DAYS}
                stroke={CHART_INK}
                strokeWidth={2}
                label={{
                  value: 'recorded peak, late May',
                  fill: CHART_INK,
                  fontSize: 12,
                  position: 'insideTopLeft',
                  dy: -2,
                }}
              />
              <ReferenceLine
                y={RECOVERY_TARGET_DAYS}
                stroke={CHART_INK_SOFT}
                strokeDasharray="6 4"
                label={{
                  value: 'recovery target',
                  fill: CHART_INK_SOFT,
                  fontSize: 12,
                  position: 'insideBottomRight',
                }}
              />
              {decisionDates.map((date) => (
                /* Annotations, not the series: a dozen accent verticals competed
                   with the one accent line they annotate. */
                <ReferenceLine
                  key={date}
                  x={date}
                  stroke={CHART_INK_SOFT}
                  strokeDasharray="2 4"
                  strokeOpacity={0.55}
                />
              ))}
              {drawnArms.map((arm) => (
                <Line
                  key={arm}
                  type="monotone"
                  dataKey={arm}
                  name={ARM_STYLE[arm].label}
                  stroke={ARM_STYLE[arm].colour}
                  strokeWidth={ARM_STYLE[arm].width}
                  strokeDasharray={ARM_STYLE[arm].dash}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
              </LineChart>
          </ResponsiveContainer>
        )}
      </figure>

      {result && (
        <>
          <div className="benchmark-arm-grid" data-tour="benchmark-arms">
            {result.arms.map((arm) => (
              <ArmTiles arm={arm} key={arm.arm} />
            ))}
          </div>
          <AnchorTable anchors={result.anchor_comparisons} />
        </>
      )}

      {decisions.length > 0 && (
        <section
          className="benchmark-decisions"
          aria-labelledby="benchmark-decisions-title"
          data-tour="benchmark-decisions"
        >
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
            {decisionRuns.map((run) => (
              <li key={run.key} data-accepted={run.accepted ? 'yes' : 'no'}>
                <span className="benchmark-decision-date">
                  {run.count === 1
                    ? shortDate(run.firstDate)
                    : `${shortDate(run.firstDate)} - ${shortDate(run.lastDate)}`}
                </span>
                <div>
                  <strong>{run.type}</strong>
                  {run.count > 1 && (
                    <span className="benchmark-decision-repeat">{plural(run.count, 'epoch')}</span>
                  )}
                  {/* The rationale of a repeated decision is a status readout
                      that moves a little each week without the decision
                      changing, so a collapsed run shows the last one as a
                      sample rather than implying it stood for all of them. */}
                  <p>
                    {run.count === 1
                      ? run.message
                      : `No change at any of these reviews. Latest reading: ${run.message}`}
                  </p>
                  {run.rejectionReason && (
                    <p className="benchmark-decision-rejected">Rejected: {run.rejectionReason}</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="benchmark-provenance-footer" data-tour="benchmark-footer">
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
