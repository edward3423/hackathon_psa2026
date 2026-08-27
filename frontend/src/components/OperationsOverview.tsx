import { useEffect, useMemo, useRef, useState } from 'react'
import { Anchor, Boxes, Factory, Ship, Snowflake, Warehouse, X, Zap } from 'lucide-react'

import type {
  ConnectionAnalysis,
  ScenarioControls,
  ScenarioState,
  WorkflowStage,
  YardForecast,
} from '../api/types'
import type { PortVessel, ScenarioPreset } from '../data/demo'
import { PORT_VESSELS } from '../data/demo'
import { scenarioPreview } from '../data/scenarioPreview.generated'
import { yardPeakPercent } from '../lib/derive'
import { formatDateTime } from '../lib/format'

interface WorkflowStep {
  id: string
  label: string
  stage: WorkflowStage
  rank: number
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { id: 'alert', label: 'Alert', stage: 'READY', rank: 0 },
  { id: 'impact', label: 'Impact', stage: 'ASSESSING', rank: 1 },
  { id: 'yard-forecast', label: 'Yard forecast', stage: 'ASSESSING', rank: 1 },
  { id: 'agent-analysis', label: 'Agent analysis', stage: 'DISPUTE', rank: 2 },
  { id: 'recovery-planning', label: 'Planning', stage: 'PLANNING', rank: 3 },
  { id: 'human-approval', label: 'Approval', stage: 'AWAITING_APPROVAL', rank: 4 },
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

export interface OperationsOverviewProps {
  scenario: ScenarioState
  preset: ScenarioPreset
  /** The live control state, which the delay slider can move before a run starts. */
  controls: ScenarioControls
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

/*
 * Five numbers, one rail, one picture, one ranking. The page used to carry a
 * seven-metric strip, a second card restating the delay and both ETAs, a
 * seven-step rail duplicating the masthead's, the schematic, the ranking with a
 * paragraph under every row, and a closing disclaimer - with the delay stated
 * four times and the workflow stage five times across the screen.
 */
export function OperationsOverview({
  scenario,
  preset,
  controls,
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

  const selectedVessel = PORT_VESSELS.find((vessel) => vessel.id === selectedVesselId) ?? null
  const currentRank = STAGE_RANK[stage]

  // Before a run there is no analysis, so the panel shows what the engine will
  // produce for the current controls. Preview and result are the same numbers
  // from the same computation, so starting the run no longer changes them.
  const preview = scenarioPreview(controls.delay_hours, controls.priority_emphasis)
  const affectedContainers = analysis
    ? analysis.groups.reduce((total, group) => total + group.container_count, 0)
    : preview.affected
  const atRiskContainers = analysis?.at_risk_count ?? preview.atRisk
  const expectedMisses = analysis?.missed_count ?? preview.missed

  const cargoBreakdown = useMemo(() => {
    const counts = analysis
      ? analysis.groups.reduce<Record<string, number>>((totals, group) => {
          totals[group.cargo_type] = (totals[group.cargo_type] ?? 0) + group.container_count
          return totals
        }, {})
      : preview.cargo
    return [
      {
        priority: 1,
        label: 'Refrigerated medicine',
        count: counts.PHARMA_REEFER ?? 0,
        icon: Snowflake,
      },
      {
        priority: 2,
        label: 'Time-critical manufacturing',
        count: counts.TIME_CRITICAL_MANUFACTURING ?? 0,
        icon: Factory,
      },
      {
        priority: 3,
        label: 'Standard dry cargo',
        count: counts.GENERAL_DRY ?? 0,
        icon: Boxes,
      },
    ]
  }, [analysis, preview.cargo])

  const yardBlocks = useMemo(() => {
    if (!baselineYard) {
      return preview.blocks.map((block) => ({ id: block.id, occupancy: block.peak }))
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
  }, [baselineYard, cursorHour, preview.blocks])

  // The same helper the impact panel used, rather than a second copy of the
  // arithmetic: a zero-capacity block made the inline version return NaN.
  const yardPeak = baselineYard ? yardPeakPercent(baselineYard) : preview.yardPeak
  const reeferShortage = baselineYard?.reefer_shortages[0]
  const reeferDemand = reeferShortage?.required_plugs ?? preview.reeferDemand
  const reeferCapacity = reeferShortage?.available_plugs ?? preview.reeferCapacity

  /*
   * Five figures, all in ink. Four of the five used to be coloured, which turned
   * the row into a rainbow and cost the colours their meaning: at-risk and
   * missed are magnitudes, not states, and a big red number next to a big amber
   * one reads as decoration.
   *
   * Colour is kept for the two that cross a threshold the engine actually
   * enforces - 85 percent yard congestion and plug demand above physical plug
   * capacity - and it marks the label rather than the figure, so the row still
   * reads as one hierarchy.
   */
  const headline = [
    { label: 'Containers affected', value: affectedContainers.toLocaleString(), breach: '' },
    { label: 'Connections at risk', value: atRiskContainers.toLocaleString(), breach: '' },
    { label: 'Expected misses', value: expectedMisses.toLocaleString(), breach: '' },
    {
      label: 'Yard peak',
      value: `${yardPeak}%`,
      breach: yardPeak >= 100 ? 'critical' : yardPeak >= 85 ? 'warning' : '',
    },
    {
      label: 'Reefer plugs',
      value: `${reeferDemand} / ${reeferCapacity}`,
      breach: reeferDemand > reeferCapacity ? 'critical' : '',
    },
  ]

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

  const renderVessel = (vessel: PortVessel) => (
    <button
      key={vessel.id}
      type="button"
      className={`operations-overview__vessel operations-overview__vessel--${vessel.role.toLowerCase()} operations-overview__risk--${vessel.risk.toLowerCase()}`}
      onClick={(event) => selectVessel(vessel, event.currentTarget)}
      aria-pressed={selectedVesselId === vessel.id}
      aria-controls="overview-vessel-details"
    >
      <Ship size={16} aria-hidden="true" />
      <span className="operations-overview__vessel-text">
        <strong>{vessel.name}</strong>
        <span className="operations-overview__vessel-meta">
          <small>{vessel.berth}</small>
          <em>{vessel.risk}</em>
        </span>
      </span>
    </button>
  )

  const inboundVessels = PORT_VESSELS.filter((vessel) => vessel.role === 'INBOUND')
  const alongsideVessels = layers.connections
    ? PORT_VESSELS.filter((vessel) => vessel.role !== 'INBOUND')
    : []

  return (
    <div className="operations-overview">
      <section
        className="operations-overview__situation"
        aria-labelledby="situation-title"
        data-tour="situation-card"
      >
        <h2 id="situation-title">{preset.title}</h2>
        <p className="operations-overview__lede">{preset.summary}</p>
        <p className="operations-overview__arrival">
          <span>Arrival</span>
          <time>{formatDateTime(scenario.alert.original_eta)}</time>
          <span className="visually-hidden">to</span>
          <span aria-hidden="true">-&gt;</span>
          <time>{revisedEta(scenario.alert.original_eta, preset.delayHours)}</time>
        </p>
        <p className="operations-overview__objective">{scenario.objective}</p>

        <dl className="operations-overview__metrics">
          {headline.map((metric) => (
            <div
              key={metric.label}
              className={
                metric.breach
                  ? `operations-overview__metric operations-overview__metric--${metric.breach}`
                  : 'operations-overview__metric'
              }
            >
              <dd>{metric.value}</dd>
              <dt>
                {metric.label}
                {metric.breach && (
                  <span className="operations-overview__metric-breach">
                    {metric.breach === 'critical' ? 'over capacity' : 'over threshold'}
                  </span>
                )}
              </dt>
            </div>
          ))}
        </dl>
      </section>

      <section
        className="operations-overview__workflow"
        aria-labelledby="workflow-title"
        data-tour="workflow-rail"
      >
        <h2 id="workflow-title" className="visually-hidden">
          Disruption response
        </h2>
        <ol className="operations-overview__workflow-list">
          {WORKFLOW_STEPS.map((step) => {
            const current = stage !== 'FAILED' && step.stage === stage
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
                  aria-label={`${step.label}, ${complete ? 'completed' : current ? 'current' : 'upcoming'}. Open its detail.`}
                >
                  <span className="operations-overview__workflow-marker" aria-hidden="true" />
                  <span>{step.label}</span>
                </button>
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
            <h2 id="port-title">Port and yard</h2>
            <div className="operations-overview__map-controls">
              <span className="operations-overview__map-note">H+{cursorHour}</span>
              <div
                className="operations-overview__layers"
                role="group"
                aria-label="Schematic layers"
              >
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

          {/* Three zones in one grid, seaward to inland: the approach channel,
              the berth line, the yard. Vessels used to be absolutely positioned
              on hardcoded percentages, which put the outbound calls on top of
              the yard blocks at every viewport width. Columns cannot overlap,
              so the collision is now impossible rather than merely tuned away. */}
          <div className="operations-overview__port-canvas">
            <div className="operations-overview__seaward">
              <div className="operations-overview__channel">
                <span className="operations-overview__zone-label">Approach channel</span>
                <div className="operations-overview__vessel-stack">
                  {inboundVessels.map(renderVessel)}
                </div>
              </div>
              <div className="operations-overview__quayside">
                <span className="operations-overview__zone-label">Alongside Terminal 1</span>
                <div className="operations-overview__vessel-stack">
                  {alongsideVessels.map(renderVessel)}
                </div>
              </div>
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
              <Anchor size={15} aria-hidden="true" />
              <span>Terminal 1 berth line</span>
            </button>

            <div className="operations-overview__terminal">
              <span className="operations-overview__zone-label">Terminal yard</span>
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
                      <Warehouse size={14} aria-hidden="true" />
                      <strong>{block.id}</strong>
                      <span>{block.occupancy}%</span>
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
                      <Zap size={14} aria-hidden="true" />
                      <strong>Reefers</strong>
                      <span>{reeferDemand} plugs</span>
                    </button>
                  )}
                </div>
              )}
            </div>
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
            <h2 id="cargo-title">Protection order</h2>
            <span>{affectedContainers.toLocaleString()} affected</span>
          </div>
          <ol className="operations-overview__cargo-list">
            {cargoBreakdown.map((cargo) => {
              const Icon = cargo.icon
              return (
                <li
                  key={cargo.priority}
                  className={`operations-overview__cargo-priority-${cargo.priority}`}
                >
                  <Icon size={15} aria-hidden="true" />
                  <span className="operations-overview__cargo-copy">
                    <strong>{cargo.label}</strong>
                    <small>Priority {cargo.priority}</small>
                  </span>
                  <span className="operations-overview__cargo-count">
                    {cargo.count.toLocaleString()}
                  </span>
                  <progress
                    max={affectedContainers || 1}
                    value={cargo.count}
                    aria-label={`${cargo.label}: ${cargo.count} of ${affectedContainers} affected containers`}
                  />
                </li>
              )
            })}
          </ol>
          <p className="operations-overview__cargo-note">
            Refrigerated medicine drives the recovery decision: it needs an electrical plug for
            every hour it waits in the yard.
          </p>
        </section>
      </div>

      {selectedVessel && (
        <aside
          className="operations-overview__vessel-drawer"
          id="overview-vessel-details"
          aria-labelledby="overview-vessel-title"
        >
          <div className="operations-overview__vessel-drawer-header">
            <h2 id="overview-vessel-title">{selectedVessel.name}</h2>
            <button
              ref={closeButtonRef}
              type="button"
              className="operations-overview__vessel-drawer-close"
              onClick={closeVesselDetails}
              aria-label="Close vessel details"
            >
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <div
            className={`operations-overview__vessel-risk operations-overview__risk--${selectedVessel.risk.toLowerCase()}`}
          >
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
              <dd>{formatDateTime(selectedVessel.eta)}</dd>
            </div>
            <div>
              <dt>Departure</dt>
              <dd>{formatDateTime(selectedVessel.departure)}</dd>
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
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <div className="operations-overview__infrastructure-detail">
            <strong>{selectedInfrastructure.status}</strong>
            <p>{selectedInfrastructure.detail}</p>
          </div>
        </aside>
      )}
    </div>
  )
}
