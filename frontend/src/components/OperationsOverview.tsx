import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Anchor,
  ArrowRight,
  Boxes,
  Factory,
  Ship,
  Snowflake,
  Warehouse,
  X,
  Zap,
} from 'lucide-react'

import type {
  ConnectionAnalysis,
  ScenarioState,
  WorkflowStage,
  YardForecast,
} from '../api/types'
import type { PortVessel, ScenarioPreset } from '../data/demo'
import { PORT_VESSELS } from '../data/demo'
import { formatDateTime, spaced } from '../lib/format'

interface WorkflowStep {
  id: string
  label: string
  stage: WorkflowStage
  rank: number
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { id: 'alert', label: 'Alert', stage: 'READY', rank: 0 },
  { id: 'impact', label: 'Impact', stage: 'ASSESSING', rank: 1 },
  { id: 'yard-forecast', label: 'Yard Forecast', stage: 'ASSESSING', rank: 1 },
  { id: 'agent-analysis', label: 'Agent Analysis', stage: 'DISPUTE', rank: 2 },
  { id: 'recovery-planning', label: 'Recovery Planning', stage: 'PLANNING', rank: 3 },
  { id: 'human-approval', label: 'Human Approval', stage: 'AWAITING_APPROVAL', rank: 4 },
  { id: 'execution', label: 'Execution', stage: 'EXECUTING', rank: 5 },
]

const STAGE_RANK: Record<WorkflowStage, number> = {
  READY: 0,
  ASSESSING: 1,
  DISPUTE: 2,
  PLANNING: 3,
  AWAITING_APPROVAL: 4,
  EXECUTING: 5,
  COMPLETE: 6,
  FAILED: -1,
}

const REEFER_PLUG_CAPACITY = 450

export interface OperationsOverviewProps {
  scenario: ScenarioState
  preset: ScenarioPreset
  stage: WorkflowStage
  analysis?: ConnectionAnalysis | null
  baselineYard?: YardForecast | null
  cursorHour?: number
  onStageSelect?: (stage: WorkflowStage) => void
  onVesselSelect?: (vessel: PortVessel | null) => void
}

interface InfrastructureSelection {
  kind: 'Berth' | 'Yard block' | 'Reefer rack'
  title: string
  status: string
  detail: string
}

function revisedEta(originalEta: string, delayHours: number): string {
  const timestamp = new Date(originalEta).getTime()
  if (!Number.isFinite(timestamp)) return formatDateTime(originalEta)
  return formatDateTime(new Date(timestamp + delayHours * 3_600_000).toISOString())
}

function riskStatus(vessel: PortVessel): string {
  if (vessel.role === 'INBOUND') return 'Delayed arrival'
  if (vessel.risk === 'CRITICAL' || vessel.risk === 'HIGH') return 'Connection threatened'
  return 'Connection monitored'
}

export function OperationsOverview({
  scenario,
  preset,
  stage,
  analysis = null,
  baselineYard = null,
  cursorHour = 0,
  onStageSelect,
  onVesselSelect,
}: OperationsOverviewProps) {
  const [selectedVesselId, setSelectedVesselId] = useState<string | null>(null)
  const [selectedInfrastructure, setSelectedInfrastructure] =
    useState<InfrastructureSelection | null>(null)
  const [layers, setLayers] = useState({ connections: true, yard: true, reefers: true })
  const lastTriggerRef = useRef<HTMLButtonElement | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)

  const selectedVessel =
    PORT_VESSELS.find((vessel) => vessel.id === selectedVesselId) ?? null
  const inboundVessel = PORT_VESSELS.find((vessel) => vessel.role === 'INBOUND')
  const currentRank = STAGE_RANK[stage]
  const affectedContainers = analysis
    ? analysis.groups.reduce((total, group) => total + group.container_count, 0)
    : preset.affected
  const atRiskContainers = analysis?.at_risk_count ?? preset.atRisk
  const expectedMisses = analysis?.missed_count ?? preset.expectedMisses

  const cargoBreakdown = useMemo(() => {
    const priorityOne = Math.round(affectedContainers * 0.1)
    const priorityTwo = Math.round(affectedContainers * 0.15)
    return [
      {
        priority: 1,
        label: 'Refrigerated medicine',
        count: priorityOne,
        description: 'Highest priority. Electrical plug capacity is protected first.',
        icon: Snowflake,
      },
      {
        priority: 2,
        label: 'Time-critical manufacturing cargo',
        count: priorityTwo,
        description: 'Components needed to keep a production line moving.',
        icon: Factory,
      },
      {
        priority: 3,
        label: 'Standard dry cargo',
        count: affectedContainers - priorityOne - priorityTwo,
        description: 'Cargo that can usually tolerate a longer onward delay.',
        icon: Boxes,
      },
    ]
  }, [affectedContainers])

  const yardBlocks = useMemo(() => {
    if (!baselineYard) {
      return [
        { id: 'YB1', occupancy: Math.max(48, preset.yardPeak - 16) },
        { id: 'YB2', occupancy: Math.max(52, preset.yardPeak - 9) },
        { id: 'YB3', occupancy: preset.yardPeak },
        { id: 'YB4', occupancy: Math.max(45, preset.yardPeak - 21) },
      ]
    }

    return baselineYard.blocks.map((block) => {
      const start = Date.parse(block.series[0]?.time ?? '')
      const selectedPoint = [...block.series].sort((left, right) => {
        const leftHour = Number.isFinite(start) ? (Date.parse(left.time) - start) / 3_600_000 : 0
        const rightHour = Number.isFinite(start) ? (Date.parse(right.time) - start) / 3_600_000 : 0
        return Math.abs(leftHour - cursorHour) - Math.abs(rightHour - cursorHour)
      })[0]
      const occupancy = selectedPoint?.occupancy ?? 0
      return {
        id: block.block_id,
        occupancy: Math.round((occupancy / block.container_capacity) * 100),
      }
    })
  }, [baselineYard, cursorHour, preset.yardPeak])

  const yardPeak = baselineYard
    ? Math.round(
        Math.max(
          0,
          ...baselineYard.blocks.map(
            (block) => (block.peak_occupancy / block.container_capacity) * 100,
          ),
        ),
      )
    : preset.yardPeak
  const reeferShortage = baselineYard?.reefer_shortages[0]
  const reeferDemand = reeferShortage?.required_plugs ?? preset.reeferDemand
  const reeferCapacity = reeferShortage?.available_plugs ?? REEFER_PLUG_CAPACITY

  useEffect(() => {
    if (!selectedVessel) return

    closeButtonRef.current?.focus()
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setSelectedVesselId(null)
      onVesselSelect?.(null)
      lastTriggerRef.current?.focus()
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onVesselSelect, selectedVessel])

  const selectVessel = (vessel: PortVessel, trigger: HTMLButtonElement) => {
    lastTriggerRef.current = trigger
    setSelectedInfrastructure(null)
    setSelectedVesselId(vessel.id)
    onVesselSelect?.(vessel)
  }

  const closeVesselDetails = () => {
    setSelectedVesselId(null)
    onVesselSelect?.(null)
    lastTriggerRef.current?.focus()
  }

  const inspectInfrastructure = (selection: InfrastructureSelection) => {
    setSelectedVesselId(null)
    onVesselSelect?.(null)
    setSelectedInfrastructure(selection)
  }

  return (
    <div className="operations-overview">
      <section
        className="operations-overview__situation"
        aria-labelledby="situation-title"
        data-tour="situation-card"
      >
        <div className="operations-overview__section-heading">
          <div>
            <h2 id="situation-title">{preset.title}</h2>
            <p>{preset.summary}</p>
          </div>
          <div className="operations-overview__active-status" role="status">
            <AlertStatusIcon />
            <span>Disruption active</span>
          </div>
        </div>

        <dl className="operations-overview__metrics">
          <div className="operations-overview__metric operations-overview__metric--primary">
            <dt>Vessel delay</dt>
            <dd>+{preset.delayHours}h</dd>
            <span>{scenario.alert.vessel_name}</span>
          </div>
          <div className="operations-overview__metric">
            <dt>Containers affected</dt>
            <dd>{affectedContainers.toLocaleString()}</dd>
          </div>
          <div className="operations-overview__metric operations-overview__metric--warning">
            <dt>Connections at risk</dt>
            <dd>{atRiskContainers.toLocaleString()}</dd>
          </div>
          <div className="operations-overview__metric operations-overview__metric--critical">
            <dt>Expected misses</dt>
            <dd>{expectedMisses.toLocaleString()}</dd>
          </div>
          <div className="operations-overview__metric operations-overview__metric--warning">
            <dt>Yard peak occupancy</dt>
            <dd>{yardPeak}%</dd>
          </div>
          <div className="operations-overview__metric">
            <dt>Reefer plug demand</dt>
            <dd>
              {reeferDemand} / {reeferCapacity}
            </dd>
          </div>
          <div className="operations-overview__metric operations-overview__metric--stage">
            <dt>Current workflow stage</dt>
            <dd>{spaced(stage)}</dd>
          </div>
        </dl>
      </section>

      <section className="operations-overview__disruption" aria-labelledby="disruption-title">
        <div className="operations-overview__disruption-copy">
          <h2 id="disruption-title">
            Incoming vessel {scenario.alert.vessel_name} delayed
          </h2>
          <p>{scenario.description}</p>
        </div>
        <dl className="operations-overview__disruption-facts">
          <div>
            <dt>Original estimated arrival</dt>
            <dd>{formatDateTime(scenario.alert.original_eta)}</dd>
          </div>
          <div>
            <dt>Updated estimated arrival</dt>
            <dd>{revisedEta(scenario.alert.original_eta, preset.delayHours)}</dd>
          </div>
          <div>
            <dt>Delay</dt>
            <dd>+{preset.delayHours} hours</dd>
          </div>
          <div>
            <dt>Containers onboard</dt>
            <dd>{inboundVessel?.containers.toLocaleString() ?? '1,284'}</dd>
          </div>
          <div>
            <dt>Transshipment containers</dt>
            <dd>{affectedContainers.toLocaleString()}</dd>
          </div>
        </dl>
      </section>

      <section
        className="operations-overview__workflow"
        aria-labelledby="workflow-title"
        data-tour="workflow-rail"
      >
        <div className="operations-overview__section-heading">
          <div>
            <h2 id="workflow-title">Disruption response</h2>
          </div>
          <p>Select a stage to inspect its operational detail.</p>
        </div>
        <ol className="operations-overview__workflow-list">
          {WORKFLOW_STEPS.map((step, index) => {
            const current =
              stage !== 'FAILED' &&
              (step.stage === stage ||
                (stage === 'ASSESSING' && step.stage === 'ASSESSING'))
            const complete = stage === 'COMPLETE' || step.rank < currentRank

            return (
              <li
                key={step.id}
                className={`operations-overview__workflow-item${
                  complete ? ' operations-overview__workflow-item--complete' : ''
                }${current ? ' operations-overview__workflow-item--current' : ''}`}
              >
                <button
                  type="button"
                  className="operations-overview__workflow-button"
                  onClick={() => onStageSelect?.(step.stage)}
                  aria-current={current ? 'step' : undefined}
                  aria-label={`${step.label}, ${complete ? 'completed' : current ? 'current' : 'upcoming'}`}
                >
                  <span className="operations-overview__workflow-marker" aria-hidden="true" />
                  <span>{step.label}</span>
                </button>
                {index < WORKFLOW_STEPS.length - 1 && (
                  <ArrowRight
                    className="operations-overview__workflow-connector"
                    size={16}
                    aria-hidden="true"
                  />
                )}
              </li>
            )
          })}
        </ol>
      </section>

      <div className="operations-overview__lower-grid">
        <section
          className="operations-overview__port"
          aria-labelledby="port-title"
          data-tour="port-schematic"
        >
          <div className="operations-overview__section-heading">
            <div>
              <h2 id="port-title">Port and yard schematic</h2>
            </div>
            <div className="operations-overview__map-controls">
              <span className="operations-overview__map-note">Hour +{cursorHour}</span>
              <div className="operations-overview__layers" role="group" aria-label="Schematic layers">
                {(Object.keys(layers) as Array<keyof typeof layers>).map((layer) => (
                  <button
                    type="button"
                    key={layer}
                    aria-pressed={layers[layer]}
                    onClick={() =>
                      setLayers((current) => ({ ...current, [layer]: !current[layer] }))
                    }
                  >
                    {layer[0].toUpperCase() + layer.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="operations-overview__port-canvas">
            <div className="operations-overview__water" aria-hidden="true">
              <span>Approach channel</span>
            </div>
            <button
              type="button"
              className="operations-overview__berth"
              aria-label="Inspect Terminal 1 berth line"
              onClick={() =>
                inspectInfrastructure({
                  kind: 'Berth',
                  title: 'Terminal 1 berth line',
                  status: 'Three outbound calls monitored',
                  detail:
                    'The delayed inbound call changes crane sequencing and transfer windows along this berth line.',
                })
              }
            >
              <Anchor size={16} />
              <span>Terminal 1 berth line</span>
            </button>

            {PORT_VESSELS.filter(
              (vessel) => vessel.role === 'INBOUND' || layers.connections,
            ).map((vessel) => (
              <button
                key={vessel.id}
                type="button"
                className={`operations-overview__vessel operations-overview__vessel--${vessel.role.toLowerCase()} operations-overview__risk--${vessel.risk.toLowerCase()}`}
                style={{ left: `${vessel.x}%`, top: `${vessel.y}%` }}
                onClick={(event) => selectVessel(vessel, event.currentTarget)}
                aria-pressed={selectedVesselId === vessel.id}
                aria-controls="overview-vessel-details"
              >
                <Ship size={18} aria-hidden="true" />
                <span>
                  <strong>{vessel.name}</strong>
                  <small>{vessel.berth}</small>
                </span>
                <em>{vessel.risk}</em>
              </button>
            ))}

            {layers.yard && (
            <div className="operations-overview__yard-blocks" aria-label="Synthetic yard blocks">
              {yardBlocks.map((block) => (
                <button
                  type="button"
                  key={block.id}
                  className={`operations-overview__yard-block${
                    block.occupancy >= 100
                      ? ' operations-overview__yard-block--critical'
                      : block.occupancy >= 85
                        ? ' operations-overview__yard-block--warning'
                        : ''
                  }`}
                  onClick={() =>
                    inspectInfrastructure({
                      kind: 'Yard block',
                      title: `Block ${block.id}`,
                      status: `${block.occupancy}% occupied near H+${cursorHour}`,
                      detail:
                        block.occupancy >= 85
                          ? 'This block is above the congestion threshold and needs recovery-plan relief.'
                          : 'This block remains within the modeled operating threshold.',
                    })
                  }
                >
                  <Warehouse size={15} aria-hidden="true" />
                  <strong>{block.id}</strong>
                  <span>{block.occupancy}% forecast</span>
                </button>
              ))}
              {layers.reefers && (
              <button
                type="button"
                className="operations-overview__yard-block operations-overview__yard-block--reefer"
                onClick={() =>
                  inspectInfrastructure({
                    kind: 'Reefer rack',
                    title: 'Refrigerated container racks',
                    status: `${reeferDemand} of ${reeferCapacity} plugs forecast`,
                    detail:
                      reeferDemand > reeferCapacity
                        ? 'Forecast demand exceeds physical electrical plug capacity.'
                        : 'Forecast demand stays within reported electrical plug capacity.',
                  })
                }
              >
                <Zap size={15} aria-hidden="true" />
                <strong>Reefer racks</strong>
                <span>{reeferDemand} plugs forecast</span>
              </button>
              )}
            </div>
            )}
          </div>

          <div className="operations-overview__risk-legend" aria-label="Vessel risk legend">
            {(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const).map((risk) => (
              <span key={risk} className={`operations-overview__risk--${risk.toLowerCase()}`}>
                {risk}
              </span>
            ))}
          </div>
        </section>

        <section
          className="operations-overview__cargo"
          aria-labelledby="cargo-title"
          data-tour="cargo-order"
        >
          <div className="operations-overview__section-heading">
            <div>
              <h2 id="cargo-title">Protection order</h2>
            </div>
            <span>{affectedContainers.toLocaleString()} affected</span>
          </div>
          <p className="operations-overview__cargo-explanation">
            Priority determines which cargo CASCADE protects first when time or terminal capacity
            is limited.
          </p>
          <ol className="operations-overview__cargo-list">
            {cargoBreakdown.map((cargo) => {
              const Icon = cargo.icon
              return (
                <li key={cargo.priority} className={`operations-overview__cargo-priority-${cargo.priority}`}>
                  <div className="operations-overview__cargo-icon" aria-hidden="true">
                    <Icon size={18} />
                  </div>
                  <div className="operations-overview__cargo-copy">
                    <span>Priority {cargo.priority}</span>
                    <strong>{cargo.label}</strong>
                    <p>{cargo.description}</p>
                  </div>
                  <div className="operations-overview__cargo-count">
                    <strong>{cargo.count.toLocaleString()}</strong>
                    <span>containers</span>
                  </div>
                  <progress
                    max={affectedContainers || 1}
                    value={cargo.count}
                    aria-label={`${cargo.label}: ${cargo.count} of ${affectedContainers} affected containers`}
                  />
                </li>
              )
            })}
          </ol>
          <div className="operations-overview__cargo-decision-note">
            <Snowflake size={16} aria-hidden="true" />
            <p>
              Refrigerated medicine is driving the recovery decision because it needs electrical
              plugs while waiting in the yard.
            </p>
          </div>
        </section>
      </div>

      {selectedVessel && (
        <aside
          className="operations-overview__vessel-drawer"
          id="overview-vessel-details"
          aria-labelledby="overview-vessel-title"
        >
          <div className="operations-overview__vessel-drawer-header">
            <div>
              <h2 id="overview-vessel-title">{selectedVessel.name}</h2>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              className="operations-overview__vessel-drawer-close"
              onClick={closeVesselDetails}
              aria-label="Close vessel details"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
          <div className={`operations-overview__vessel-risk operations-overview__risk--${selectedVessel.risk.toLowerCase()}`}>
            <span>{selectedVessel.risk} RISK</span>
            <strong>{riskStatus(selectedVessel)}</strong>
          </div>
          <dl className="operations-overview__vessel-facts">
            <div>
              <dt>Vessel ID</dt>
              <dd>{selectedVessel.id}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>{selectedVessel.role}</dd>
            </div>
            <div>
              <dt>Estimated arrival</dt>
              <dd>{selectedVessel.eta}</dd>
            </div>
            <div>
              <dt>Departure</dt>
              <dd>{selectedVessel.departure}</dd>
            </div>
            <div>
              <dt>Berth</dt>
              <dd>{selectedVessel.berth}</dd>
            </div>
            <div>
              <dt>Containers</dt>
              <dd>{selectedVessel.containers.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Connections</dt>
              <dd>{selectedVessel.connections.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Delay status</dt>
              <dd>{riskStatus(selectedVessel)}</dd>
            </div>
            <div>
              <dt>Current risk</dt>
              <dd>{selectedVessel.risk}</dd>
            </div>
          </dl>
        </aside>
      )}

      {selectedInfrastructure && (
        <aside
          className="operations-overview__vessel-drawer"
          role="dialog"
          aria-modal="false"
          aria-labelledby="overview-infrastructure-title"
        >
          <div className="operations-overview__vessel-drawer-header">
            <div>
              <p className="drawer-context">{selectedInfrastructure.kind}</p>
              <h2 id="overview-infrastructure-title">{selectedInfrastructure.title}</h2>
            </div>
            <button
              type="button"
              className="operations-overview__vessel-drawer-close"
              onClick={() => setSelectedInfrastructure(null)}
              aria-label="Close infrastructure details"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
          <div className="operations-overview__infrastructure-detail">
            <strong>{selectedInfrastructure.status}</strong>
            <p>{selectedInfrastructure.detail}</p>
            <p>All capacity and timing values are synthetic or calculated for this demonstration.</p>
          </div>
        </aside>
      )}

      <p className="operations-overview__safety-note">
        CASCADE uses synthetic port data and mocked actions. It cannot affect real terminal
        operations.
      </p>
    </div>
  )
}

function AlertStatusIcon() {
  return <Anchor size={16} aria-hidden="true" />
}
