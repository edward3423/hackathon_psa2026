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

import type { PlanArchetype, YardForecast } from '../api/types'
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
import { titleCase } from '../lib/format'

interface YardForecastPanelProps {
  baseline: YardForecast | null
  planned: YardForecast | null
  selectedPlan: PlanArchetype | null
}

interface ChartPoint {
  hour: number
  baseline?: number
  planned?: number
}

function hoursSince(start: string, time: string): number {
  return Math.round((new Date(time).getTime() - new Date(start).getTime()) / 3_600_000)
}

export function YardForecastPanel({ baseline, planned, selectedPlan }: YardForecastPanelProps) {
  if (!baseline) {
    return (
      <section className="yard-panel" aria-labelledby="yard-title">
        <div className="panel-heading">
          <div>
            <h2 id="yard-title">72-hour block occupancy</h2>
          </div>
        </div>
        <p className="panel-placeholder">
          The baseline yard forecast appears when yard simulation completes.
        </p>
      </section>
    )
  }

  return (
    <section className="yard-panel" aria-labelledby="yard-title" data-tour="yard-forecast">
      <div className="panel-heading">
        <div>
          <h2 id="yard-title">72-hour block occupancy</h2>
        </div>
        <span className="yard-legend-note">
          Baseline vs {selectedPlan ? titleCase(selectedPlan) : 'selected plan'} - containers per
          block, hours from alert
        </span>
      </div>

      <div className="yard-grid">
        {baseline.blocks.map((block) => {
          const start = block.series[0]?.time
          const plannedBlock = planned?.blocks.find((b) => b.block_id === block.block_id)
          const points = new Map<number, ChartPoint>()
          for (const point of block.series) {
            const hour = start ? hoursSince(start, point.time) : 0
            points.set(hour, { hour, baseline: point.occupancy })
          }
          for (const point of plannedBlock?.series ?? []) {
            const hour = start ? hoursSince(start, point.time) : 0
            const existing = points.get(hour) ?? { hour }
            existing.planned = point.occupancy
            points.set(hour, existing)
          }
          const data = [...points.values()].sort((a, b) => a.hour - b.hour)
          const congestion = Math.round(block.container_capacity * 0.85)

          return (
            <figure className="yard-block" key={block.block_id}>
              <figcaption>
                Block {block.block_id} - capacity {block.container_capacity} containers
              </figcaption>
              <ResponsiveContainer width="100%" height={190}>
                <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
                  <CartesianGrid {...gridProps} vertical={false} />
                  <XAxis
                    dataKey="hour"
                    {...axisProps}
                    tickFormatter={(value: number) => `${value}h`}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    {...axisProps}
                    width={44}
                    domain={[0, Math.ceil(block.container_capacity * 1.1)]}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelFormatter={(value) => `Hour ${value}`} />
                  <Legend wrapperStyle={legendStyle} formatter={legendLabel} />
                  <ReferenceLine
                    y={congestion}
                    stroke={CHART_INK_SOFT}
                    strokeDasharray="6 4"
                    label={{
                      value: '85% congested',
                      fill: CHART_INK_SOFT,
                      fontSize: 12,
                      position: 'insideBottomRight',
                    }}
                  />
                  <ReferenceLine
                    y={block.container_capacity}
                    stroke={CHART_INK}
                    strokeWidth={2}
                    label={{
                      value: '100% capacity',
                      fill: CHART_INK,
                      fontSize: 12,
                      position: 'insideTopLeft',
                      dy: -2,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    name="Baseline"
                    stroke={CHART_INK_SOFT}
                    strokeWidth={2}
                    strokeDasharray="7 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                  {plannedBlock && (
                    <Line
                      type="monotone"
                      dataKey="planned"
                      name={selectedPlan ? titleCase(selectedPlan) : 'Planned'}
                      stroke={CHART_ACCENT}
                      strokeWidth={2.5}
                      dot={false}
                      isAnimationActive={false}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </figure>
          )
        })}
      </div>
    </section>
  )
}
