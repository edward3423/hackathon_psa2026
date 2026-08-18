import { useEffect, useMemo, useRef, useState } from 'react'
import { Factory, Filter, Package, Ship, Snowflake, X } from 'lucide-react'

import type { CargoType, ConnectionAnalysis, ConnectionStatus } from '../api/types'
import { MOCK_CONNECTION_ANALYSIS } from '../data/demo'
import { formatDateTime } from '../lib/format'

type Connection = ConnectionAnalysis['connections'][number]
type StatusFilter = 'ALL' | ConnectionStatus
type PriorityFilter = 'ALL' | '1' | '2' | '3'

const CARGO_DETAILS: Record<
  CargoType,
  { label: string; shortLabel: string; priority: 1 | 2 | 3; Icon: typeof Snowflake }
> = {
  PHARMA_REEFER: {
    label: 'Refrigerated medicine',
    shortLabel: 'Medicine reefer',
    priority: 1,
    Icon: Snowflake,
  },
  TIME_CRITICAL_MANUFACTURING: {
    label: 'Time-critical manufacturing cargo',
    shortLabel: 'Manufacturing',
    priority: 2,
    Icon: Factory,
  },
  GENERAL_DRY: {
    label: 'Standard dry cargo',
    shortLabel: 'Standard dry',
    priority: 3,
    Icon: Package,
  },
}

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  SAFE: 'SAFE',
  AT_RISK: 'AT RISK',
  MISSED: 'EXPECTED MISS',
  RESOLVED: 'RESOLVED',
}

const DESTINATION_BY_VESSEL: Record<string, string> = {
  'MV MERIDIAN WAVE': 'Busan',
  'MV PACIFIC LINK': 'Port Klang',
  'MV PACIFIC HARRIER': 'Manila',
  'MV CORAL EMPRESS': 'Colombo',
  'MV CORAL GATE': 'Jakarta',
  'MV MERIDIAN': 'Busan',
}

interface ConnectionView extends Connection {
  destination: string
  requiredTransferHours: number
  availableTransferHours: number
}

export interface ConnectionsPageProps {
  analysis?: ConnectionAnalysis | null
  inboundVessel?: string
  offline?: boolean
}

function requiredTransferHours(cargoType: CargoType): number {
  if (cargoType === 'PHARMA_REEFER') return 3.5
  if (cargoType === 'TIME_CRITICAL_MANUFACTURING') return 4
  return 3
}

function destinationFor(vessel: string): string {
  return DESTINATION_BY_VESSEL[vessel] ?? 'Regional hub'
}

function formatHours(value: number): string {
  const sign = value < 0 ? '-' : ''
  const absolute = Math.abs(value)
  const hours = Math.floor(absolute)
  const minutes = Math.round((absolute - hours) * 60)
  return `${sign}${hours}h ${String(minutes).padStart(2, '0')}m`
}

function recommendedAction(connection: ConnectionView): string {
  if (connection.status === 'RESOLVED') return 'Validate updated transfer order'
  if (connection.status === 'SAFE') return 'Monitor connection'
  if (connection.status === 'MISSED') {
    return connection.cargo_type === 'PHARMA_REEFER'
      ? 'Protect power and rebook earliest sailing'
      : 'Rebook next available sailing'
  }
  if (connection.cargo_type === 'PHARMA_REEFER') return 'Rush through priority transfer lane'
  if (connection.cargo_type === 'TIME_CRITICAL_MANUFACTURING') return 'Expedite discharge and transfer'
  return 'Hold transfer slot and monitor cutoff'
}

function classificationReason(connection: ConnectionView): string {
  const margin = formatHours(connection.margin_hours)
  if (connection.status === 'MISSED') {
    return `The predicted ready time is ${formatHours(Math.abs(connection.margin_hours))} after the connection cutoff. The current schedule therefore produces an expected miss.`
  }
  if (connection.status === 'AT_RISK') {
    return `The container has ${margin} of margin after required handling. CASCADE classifies margins from zero through four hours as at risk.`
  }
  if (connection.status === 'SAFE') {
    return `The container has ${margin} of margin after required handling. CASCADE classifies margins above four hours as safe.`
  }
  return 'A recovery action has restored the connection. The revised transfer order still requires operator validation.'
}

function cargoIcon(cargoType: CargoType) {
  const Icon = CARGO_DETAILS[cargoType].Icon
  return <Icon aria-hidden="true" size={15} strokeWidth={1.8} />
}

export function ConnectionsPage({
  analysis,
  inboundVessel = 'MV ATLAS STAR',
  offline = false,
}: ConnectionsPageProps) {
  const source = analysis ?? (offline ? MOCK_CONNECTION_ANALYSIS : null)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('ALL')
  const [destinationFilter, setDestinationFilter] = useState('ALL')
  const [vesselFilter, setVesselFilter] = useState('ALL')
  const [selected, setSelected] = useState<ConnectionView | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const returnFocusRef = useRef<HTMLButtonElement | null>(null)

  const rows = useMemo<ConnectionView[]>(
    () =>
      (source?.connections ?? []).map((connection) => {
        const required = requiredTransferHours(connection.cargo_type)
        return {
          ...connection,
          destination: destinationFor(connection.onward_vessel),
          requiredTransferHours: required,
          availableTransferHours: connection.margin_hours + required,
        }
      }),
    [source],
  )

  const destinations = useMemo(
    () => [...new Set(rows.map((row) => row.destination))].sort(),
    [rows],
  )
  const vessels = useMemo(
    () => [...new Set(rows.map((row) => row.onward_vessel))].sort(),
    [rows],
  )
  const filteredRows = useMemo(
    () =>
      rows.filter((row) => {
        const priority = String(CARGO_DETAILS[row.cargo_type].priority)
        return (
          (statusFilter === 'ALL' || row.status === statusFilter) &&
          (priorityFilter === 'ALL' || priority === priorityFilter) &&
          (destinationFilter === 'ALL' || row.destination === destinationFilter) &&
          (vesselFilter === 'ALL' || row.onward_vessel === vesselFilter)
        )
      }),
    [destinationFilter, priorityFilter, rows, statusFilter, vesselFilter],
  )

  const closeDrawer = () => {
    setSelected(null)
    window.requestAnimationFrame(() => returnFocusRef.current?.focus())
  }

  useEffect(() => {
    if (!selected) return undefined
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selected])

  return (
    <section className="connections-page" aria-labelledby="connections-page-title">
      <header className="connections-page__header">
        <div>
          <h2 id="connections-page-title">Threatened transshipment connections</h2>
          <p className="connections-page__summary">
            A transshipment container arrives on one ship and leaves on another. When the first
            ship is late, the container can miss the second ship.
          </p>
        </div>
        <div className="connections-page__source" role="status">
          <Ship aria-hidden="true" size={17} />
          <span>
            {analysis != null
              ? 'LIVE RUN ANALYSIS'
              : offline
                ? 'OFFLINE DEMO DATA'
                : 'AWAITING RUN ANALYSIS'}
          </span>
        </div>
      </header>

      <div className="connections-page__cargo-key" aria-label="Cargo priority order">
        {(Object.entries(CARGO_DETAILS) as [CargoType, (typeof CARGO_DETAILS)[CargoType]][]).map(
          ([cargoType, detail]) => (
            <div className="cargo-key-item" key={cargoType}>
              <detail.Icon aria-hidden="true" size={17} />
              <span>
                <strong>Priority {detail.priority}</strong>
                {detail.label}
              </span>
            </div>
          ),
        )}
      </div>

      <form className="connections-filters" aria-label="Connection filters" onSubmit={(event) => event.preventDefault()}>
        <div className="connections-filters__title">
          <Filter aria-hidden="true" size={16} />
          <span>Filter connections</span>
        </div>
        <label>
          Risk status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
            <option value="ALL">All statuses</option>
            <option value="SAFE">Safe</option>
            <option value="AT_RISK">At risk</option>
            <option value="MISSED">Expected miss</option>
            <option value="RESOLVED">Resolved</option>
          </select>
        </label>
        <label>
          Cargo priority
          <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value as PriorityFilter)}>
            <option value="ALL">All priorities</option>
            <option value="1">Priority 1</option>
            <option value="2">Priority 2</option>
            <option value="3">Priority 3</option>
          </select>
        </label>
        <label>
          Destination
          <select value={destinationFilter} onChange={(event) => setDestinationFilter(event.target.value)}>
            <option value="ALL">All destinations</option>
            {destinations.map((destination) => (
              <option key={destination} value={destination}>{destination}</option>
            ))}
          </select>
        </label>
        <label>
          Connecting vessel
          <select value={vesselFilter} onChange={(event) => setVesselFilter(event.target.value)}>
            <option value="ALL">All vessels</option>
            {vessels.map((vessel) => (
              <option key={vessel} value={vessel}>{vessel}</option>
            ))}
          </select>
        </label>
      </form>

      <p className="connections-page__result-count" aria-live="polite">
        Showing {filteredRows.length} of {rows.length} containers
      </p>

      <div className="connections-table-region" role="region" aria-label="Threatened connection table" tabIndex={0}>
        <table className="connections-table">
          <thead>
            <tr>
              <th scope="col">Container ID</th>
              <th scope="col">Cargo</th>
              <th scope="col">Priority</th>
              <th scope="col">Incoming vessel</th>
              <th scope="col">Connecting vessel</th>
              <th scope="col">Destination</th>
              <th scope="col">Connection departure</th>
              <th scope="col">Available transfer time</th>
              <th scope="col">Required transfer time</th>
              <th scope="col">Risk status</th>
              <th scope="col">Recommended action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const cargo = CARGO_DETAILS[row.cargo_type]
              return (
                <tr
                  className="connections-table__row"
                  key={row.container_id}
                  onClick={() => setSelected(row)}
                >
                  <th scope="row">
                    <button
                      className="connections-table__container-button"
                      type="button"
                      ref={(node) => {
                        if (selected?.container_id === row.container_id) returnFocusRef.current = node
                      }}
                      aria-label={`Inspect ${row.container_id}`}
                      onClick={(event) => {
                        event.stopPropagation()
                        returnFocusRef.current = event.currentTarget
                        setSelected(row)
                      }}
                    >
                      {row.container_id}
                    </button>
                  </th>
                  <td>
                    <span className="connections-table__cargo">
                      {cargoIcon(row.cargo_type)}
                      {cargo.shortLabel}
                    </span>
                  </td>
                  <td>Priority {cargo.priority}</td>
                  <td>{inboundVessel}</td>
                  <td>{row.onward_vessel}</td>
                  <td>{row.destination}</td>
                  <td>{formatDateTime(row.connection_cutoff)}</td>
                  <td>{formatHours(row.availableTransferHours)}</td>
                  <td>{formatHours(row.requiredTransferHours)}</td>
                  <td>
                    <span className={`connection-status connection-status--${row.status.toLowerCase().replace('_', '-')}`}>
                      {STATUS_LABEL[row.status]}
                    </span>
                  </td>
                  <td>{recommendedAction(row)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filteredRows.length === 0 && (
          <p className="connections-table__empty">
            {source === null
              ? 'Awaiting connection analysis. Start a run to classify threatened containers.'
              : rows.length === 0
                ? 'Analysis completed with no connection records.'
                : 'No containers match the selected filters.'}
          </p>
        )}
      </div>

      {selected && (
        <div className="connection-drawer-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) closeDrawer()
        }}>
          <aside
            className="connection-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="connection-drawer-title"
          >
            <header className="connection-drawer__header">
              <div>
                <h2 id="connection-drawer-title">{selected.container_id}</h2>
              </div>
              <button
                ref={closeButtonRef}
                className="connection-drawer__close"
                type="button"
                aria-label="Close connection details"
                onClick={closeDrawer}
              >
                <X aria-hidden="true" size={19} />
              </button>
            </header>

            <div className="connection-drawer__status-line">
              <span className={`connection-status connection-status--${selected.status.toLowerCase().replace('_', '-')}`}>
                {STATUS_LABEL[selected.status]}
              </span>
              <span>Priority {CARGO_DETAILS[selected.cargo_type].priority}</span>
            </div>

            <dl className="connection-drawer__facts">
              <div><dt>Cargo</dt><dd>{CARGO_DETAILS[selected.cargo_type].label}</dd></div>
              <div><dt>Connecting vessel</dt><dd>{selected.onward_vessel}</dd></div>
              <div><dt>Destination</dt><dd>{selected.destination}</dd></div>
              <div><dt>Predicted ready time</dt><dd>{formatDateTime(selected.ready_time)}</dd></div>
              <div><dt>Connection cutoff</dt><dd>{formatDateTime(selected.connection_cutoff)}</dd></div>
              <div><dt>Transfer margin</dt><dd>{formatHours(selected.margin_hours)}</dd></div>
            </dl>

            <section className="connection-drawer__reasoning" aria-labelledby="classification-reason-title">
              <h3 id="classification-reason-title">Why CASCADE assigned this status</h3>
              <p>{classificationReason(selected)}</p>
              <p>{selected.priority_reason}</p>
            </section>

            <section className="connection-drawer__action" aria-labelledby="recommended-action-title">
              <h3 id="recommended-action-title">Recommended action</h3>
              <p>{recommendedAction(selected)}</p>
              <p>Recommendation only. A human operator must approve any simulated recovery plan.</p>
            </section>
          </aside>
        </div>
      )}
    </section>
  )
}
