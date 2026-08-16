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
            <p className="section-label">YARD FORECAST</p>
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
    <section className="yard-panel" aria-labelledby="yard-title">
      <div className="panel-heading">
        <div>
          <p className="section-label">YARD FORECAST (SYNTHETIC)</p>
          <h2 id="yard-title">72-hour block occupancy</h2>
        </div>
        <span className="yard-legend-note">
          Baseline vs {selectedPlan ? titleCase(selectedPlan) : 'selected plan'} - containers per
          block, hours from alert (UTC)
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
                  <CartesianGrid stroke="#16242e" strokeDasharray="2 4" />
                  <XAxis
                    dataKey="hour"
                    stroke="#82939d"
                    fontSize={11}
                    tickFormatter={(value: number) => `${value}h`}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    stroke="#82939d"
                    fontSize={11}
                    width={44}
                    domain={[0, Math.ceil(block.container_capacity * 1.1)]}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#0e1b24',
                      border: '1px solid #20313b',
                      color: '#d9e5eb',
                      fontSize: 12,
                    }}
                    labelFormatter={(value) => `Hour ${value}`}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#82939d' }} />
                  <ReferenceLine
                    y={congestion}
                    stroke="#f1a33c"
                    strokeDasharray="5 3"
                    label={{
                      value: '85% congested',
                      fill: '#f1a33c',
                      fontSize: 10,
                      position: 'insideBottomLeft',
                    }}
                  />
                  <ReferenceLine
                    y={block.container_capacity}
                    stroke="#e35d5d"
                    strokeDasharray="5 3"
                    label={{
                      value: '100% capacity',
                      fill: '#e35d5d',
                      fontSize: 10,
                      position: 'insideTopLeft',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="baseline"
                    name="Baseline"
                    stroke="#82939d"
                    strokeWidth={1.6}
                    dot={false}
                    isAnimationActive={false}
                  />
                  {plannedBlock && (
                    <Line
                      type="monotone"
                      dataKey="planned"
                      name={selectedPlan ? titleCase(selectedPlan) : 'Planned'}
                      stroke="#4fc3d7"
                      strokeWidth={1.8}
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
