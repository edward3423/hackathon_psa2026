import { AlertTriangle, Snowflake, Warehouse } from 'lucide-react'

import type { PlanArchetype, YardForecast } from '../api/types'
import { formatDateTime, titleCase } from '../lib/format'
import { YardForecastPanel } from './YardForecastPanel'

type YardBlock = YardForecast['blocks'][number]
type OccupancyPoint = YardBlock['series'][number]
type ReeferShortage = YardForecast['reefer_shortages'][number]

export interface YardOperationsPageProps {
  baseline: YardForecast | null
  planned: YardForecast | null
  selectedPlan: PlanArchetype | null
  cursorHour: number
  mode: 'yard' | 'reefers'
}

interface LoadedForecastProps {
  baseline: YardForecast
  planned: YardForecast | null
  selectedPlan: PlanArchetype | null
  cursorHour: number
}

function forecastStart(forecast: YardForecast): number | null {
  const timestamps = forecast.blocks
    .flatMap((block) => block.series)
    .map((point) => Date.parse(point.time))
    .filter(Number.isFinite)

  return timestamps.length > 0 ? Math.min(...timestamps) : null
}

function pointAtHour(
  block: YardBlock,
  startTimestamp: number | null,
  cursorHour: number,
): OccupancyPoint | null {
  if (startTimestamp === null || block.series.length === 0) return null

  return block.series.reduce<OccupancyPoint | null>((nearest, point) => {
    if (!nearest) return point
    const pointHour = (Date.parse(point.time) - startTimestamp) / 3_600_000
    const nearestHour = (Date.parse(nearest.time) - startTimestamp) / 3_600_000
    return Math.abs(pointHour - cursorHour) < Math.abs(nearestHour - cursorHour) ? point : nearest
  }, null)
}

function occupancyStatus(point: OccupancyPoint | null, capacity: number): string {
  if (!point) return 'Not reported'
  if (point.full || point.occupancy >= capacity) return 'At capacity'
  if (point.congested || point.occupancy / capacity >= 0.85) return 'Congested'
  return 'Within capacity'
}

function shortageSize(shortage: ReeferShortage): number {
  return Math.max(0, shortage.required_plugs - shortage.available_plugs)
}

function mostSevereShortage(shortages: ReeferShortage[]): ReeferShortage | null {
  return shortages.reduce<ReeferShortage | null>((mostSevere, shortage) => {
    if (!mostSevere || shortageSize(shortage) > shortageSize(mostSevere)) return shortage
    return mostSevere
  }, null)
}

function relativeHour(timestamp: string, startTimestamp: number | null): string {
  if (startTimestamp === null) return 'Time unavailable'
  const parsed = Date.parse(timestamp)
  if (!Number.isFinite(parsed)) return 'Time unavailable'
  return `H+${Math.max(0, Math.round((parsed - startTimestamp) / 3_600_000))}`
}

function YardCapacityView({
  baseline,
  planned,
  selectedPlan,
  cursorHour,
}: LoadedForecastProps) {
  if (baseline.blocks.length === 0) {
    return <p className="operations-empty-state">No yard blocks were returned for this run.</p>
  }

  const baselineStart = forecastStart(baseline)
  const plannedStart = planned ? forecastStart(planned) : null
  const plannedBlocks = new Map(planned?.blocks.map((block) => [block.block_id, block]) ?? [])

  return (
    <>
      <p className="yard-cursor-context">
        Showing the forecast sample nearest H+{cursorHour}. Capacity status comes from the returned
        occupancy records.
      </p>

      <div
        className="operations-table-region"
        role="region"
        aria-label="Yard block capacity forecast"
        tabIndex={0}
      >
        <table className="operations-data-table yard-capacity-table">
          <caption>Block capacity and peak occupancy</caption>
          <thead>
            <tr>
              <th scope="col">Block</th>
              <th scope="col">Container capacity</th>
              <th scope="col">Occupancy at H+{cursorHour}</th>
              <th scope="col">Current status</th>
              <th scope="col">Baseline peak</th>
              <th scope="col">Baseline peak time</th>
              <th scope="col">
                {selectedPlan ? `${titleCase(selectedPlan)} peak` : 'Selected plan peak'}
              </th>
            </tr>
          </thead>
          <tbody>
            {baseline.blocks.map((block) => {
              const currentPoint = pointAtHour(block, baselineStart, cursorHour)
              const plannedBlock = plannedBlocks.get(block.block_id)
              const plannedPoint = plannedBlock
                ? pointAtHour(plannedBlock, plannedStart, cursorHour)
                : null
              const status = occupancyStatus(currentPoint, block.container_capacity)

              return (
                <tr key={block.block_id}>
                  <th scope="row">{block.block_id}</th>
                  <td>{block.container_capacity.toLocaleString()}</td>
                  <td>
                    {currentPoint ? currentPoint.occupancy.toLocaleString() : 'Not reported'}
                  </td>
                  <td data-status={status.toLowerCase().replaceAll(' ', '-')}>{status}</td>
                  <td>{block.peak_occupancy.toLocaleString()}</td>
                  <td>{formatDateTime(block.peak_time)}</td>
                  <td>
                    {plannedBlock
                      ? `${plannedBlock.peak_occupancy.toLocaleString()} peak, ${
                          plannedPoint?.occupancy.toLocaleString() ?? 'no sample'
                        } at H+${cursorHour}`
                      : 'Not calculated'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <YardForecastPanel baseline={baseline} planned={planned} selectedPlan={selectedPlan} />
    </>
  )
}

function ReeferCapacityView({
  baseline,
  planned,
  selectedPlan,
  cursorHour,
}: LoadedForecastProps) {
  const startTimestamp = forecastStart(baseline)
  const blockIds = [
    ...new Set([
      ...baseline.reefer_shortages.map((shortage) => shortage.block_id),
      ...(planned?.reefer_shortages.map((shortage) => shortage.block_id) ?? []),
    ]),
  ].sort()

  if (blockIds.length === 0) {
    return (
      <div className="operations-empty-state" role="status">
        <Snowflake aria-hidden="true" size={20} />
        <p>No reefer plug shortages were reported in the available forecast.</p>
        <small>Selected horizon: H+{cursorHour}.</small>
      </div>
    )
  }

  return (
    <>
      <p className="yard-cursor-context">
        Shortage timing is measured from the start of the 72-hour forecast. The table uses the most
        severe backend shortage record returned for each block.
      </p>
      <div
        className="operations-table-region"
        role="region"
        aria-label="Reefer plug shortage comparison"
        tabIndex={0}
      >
        <table className="operations-data-table reefer-capacity-table">
          <caption>Current shortage and selected-plan mitigation</caption>
          <thead>
            <tr>
              <th scope="col">Block</th>
              <th scope="col">Current shortage starts</th>
              <th scope="col">Plugs needed</th>
              <th scope="col">Plugs available</th>
              <th scope="col">Current shortfall</th>
              <th scope="col">
                {selectedPlan ? `${titleCase(selectedPlan)} result` : 'Selected plan result'}
              </th>
            </tr>
          </thead>
          <tbody>
            {blockIds.map((blockId) => {
              const baselineShortage = mostSevereShortage(
                baseline.reefer_shortages.filter((shortage) => shortage.block_id === blockId),
              )
              const plannedShortage = mostSevereShortage(
                planned?.reefer_shortages.filter((shortage) => shortage.block_id === blockId) ?? [],
              )

              let plannedResult = 'Not calculated'
              if (planned) {
                plannedResult = plannedShortage
                  ? `${shortageSize(plannedShortage)} plugs short from ${relativeHour(
                      plannedShortage.start_time,
                      startTimestamp,
                    )}`
                  : 'No shortage reported'
              }

              return (
                <tr key={blockId}>
                  <th scope="row">{blockId}</th>
                  <td>
                    {baselineShortage
                      ? `${formatDateTime(baselineShortage.start_time)} (${relativeHour(
                          baselineShortage.start_time,
                          startTimestamp,
                        )})`
                      : 'None reported'}
                  </td>
                  <td>{baselineShortage?.required_plugs.toLocaleString() ?? 'Not reported'}</td>
                  <td>{baselineShortage?.available_plugs.toLocaleString() ?? 'Not reported'}</td>
                  <td>
                    {baselineShortage
                      ? `${shortageSize(baselineShortage).toLocaleString()} plugs`
                      : 'None reported'}
                  </td>
                  <td>{plannedResult}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

export function YardOperationsPage(props: YardOperationsPageProps) {
  const { baseline, mode } = props
  const yardMode = mode === 'yard'

  return (
    <section className={`yard-operations-page yard-operations-page--${mode}`}>
      <header className="page-section-header">
        <div>
          <h2>{yardMode ? 'Yard capacity' : 'Reefer plug capacity'}</h2>
          <p>
            {yardMode
              ? 'The yard is the terminal storage area where containers wait between vessel moves.'
              : 'A reefer is a refrigerated container. It needs an electrical plug to keep its cargo cold.'}
          </p>
        </div>
        {yardMode ? (
          <Warehouse aria-hidden="true" size={22} />
        ) : (
          <Snowflake aria-hidden="true" size={22} />
        )}
      </header>

      {!baseline ? (
        <div className="operations-empty-state" role="status">
          <AlertTriangle aria-hidden="true" size={20} />
          <p>
            {yardMode
              ? 'Yard capacity becomes available after the forecast engine completes.'
              : 'Reefer plug capacity becomes available after the forecast engine completes.'}
          </p>
        </div>
      ) : yardMode ? (
        <YardCapacityView
          baseline={baseline}
          planned={props.planned}
          selectedPlan={props.selectedPlan}
          cursorHour={props.cursorHour}
        />
      ) : (
        <ReeferCapacityView
          baseline={baseline}
          planned={props.planned}
          selectedPlan={props.selectedPlan}
          cursorHour={props.cursorHour}
        />
      )}
    </section>
  )
}
