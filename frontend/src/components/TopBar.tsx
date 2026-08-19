import { Bot, Menu, PlayCircle, Radio, ShieldCheck, Wifi, WifiOff } from 'lucide-react'

import type { RunCreated, ScenarioState, WorkflowStage } from '../api/types'
import { formatDateTime, spaced } from '../lib/format'

const STAGES: WorkflowStage[] = [
  'READY',
  'ASSESSING',
  'DISPUTE',
  'PLANNING',
  'AWAITING_APPROVAL',
  'EXECUTING',
  'COMPLETE',
]

interface TopBarProps {
  scenario: ScenarioState
  run: RunCreated | null
  stage: WorkflowStage
  delayHours: number
  streaming: boolean
  offline: boolean
  transportState?:
    | 'READY'
    | 'CONNECTING'
    | 'CONNECTED'
    | 'RECONNECTING'
    | 'DISCONNECTED'
    | 'OFFLINE'
    | 'ENDED'
  eventCount: number
  /**
   * Everything below the masthead describes one single-vessel run: the vessel
   * under disruption, its objective, the workflow stage rail and the run's
   * transport state. Act 2 replays a fleet across five months and has none of
   * those, so it asks for the masthead alone rather than being given an idle
   * stage rail and a vessel it is not about.
   */
  showRunContext?: boolean
  /** What this page is, when it is not the single-vessel scenario. */
  subtitle?: string
  /**
   * The guided tour starts real runs, so it needs the backend. The control stays
   * clickable when it cannot run and explains why, which tells a first-time
   * viewer more than a dead button would.
   */
  tourEnabled?: boolean
  onStartTour?: () => void
  onOpenNavigation: () => void
  onStageSelect?: (stage: WorkflowStage) => void
}

export function TopBar({
  scenario,
  run,
  stage,
  delayHours,
  streaming,
  offline,
  transportState,
  eventCount,
  showRunContext = true,
  subtitle,
  tourEnabled = true,
  onStartTour,
  onOpenNavigation,
  onStageSelect,
}: TopBarProps) {
  const stageIndex = STAGES.indexOf(stage)
  const connectionLabel = offline
    ? 'Offline demo'
    : transportState === 'CONNECTING'
      ? 'SSE connecting'
      : transportState === 'CONNECTED'
        ? 'SSE connected'
        : transportState === 'RECONNECTING'
          ? 'SSE reconnecting'
          : transportState === 'DISCONNECTED'
            ? 'SSE disconnected'
            : transportState === 'ENDED'
              ? 'SSE complete'
              : 'SSE ready'
  const agentStatus =
    stage === 'DISPUTE' || stage === 'AWAITING_APPROVAL'
      ? 'Waiting for operator'
      : stage === 'COMPLETE'
        ? 'Run complete'
        : stage === 'FAILED'
          ? 'Attention required'
          : streaming
            ? 'Agents working'
            : 'Ready'

  return (
    <header className="top-bar">
      {run?.mode === 'DEMO_REPLAY' && (
        <div className="replay-banner" role="status">
          <span className="replay-badge">DEMO REPLAY</span>
          <span>Recorded synthetic run</span>
        </div>
      )}

      <div className="masthead-row" data-tour="masthead">
        <button
          className="mobile-nav-trigger"
          type="button"
          aria-label="Open navigation"
          onClick={onOpenNavigation}
        >
          <Menu size={19} aria-hidden="true" />
        </button>

        <div className="masthead-identity">
          <div className="page-identity">
            <h1>CASCADE</h1>
            <p className="scenario-readout">{subtitle ?? scenario.name}</p>
          </div>

          {onStartTour && (
            <button
              type="button"
              className={`tour-launch-button${tourEnabled ? '' : ' is-unavailable'}`}
              data-tour="tour-launch"
              onClick={onStartTour}
              title={
                tourEnabled
                  ? 'Play the five-minute guided walkthrough'
                  : 'The guided tour needs the backend'
              }
            >
              <PlayCircle size={16} aria-hidden="true" />
              Start tour
            </button>
          )}
        </div>

        {showRunContext && (
          <>
            <div className="top-status-grid" aria-label="System status summary">
              <div>
                <span>Simulated port time</span>
                <strong>{formatDateTime(scenario.alert.event_time)}</strong>
              </div>
              <div>
                <span>Run ID</span>
                <strong className="run-id">{run?.run_id ?? 'NOT STARTED'}</strong>
              </div>
              <div>
                <span>Agent mode</span>
                <strong>
                  {run?.mode === 'DEMO_REPLAY'
                    ? 'Recorded simulation'
                    : run
                      ? spaced(run.mode).replace('LIVE ', '')
                      : 'Scripted simulation'}
                </strong>
              </div>
              <div>
                <span>Agent status</span>
                <strong className="inline-status">
                  <Bot size={14} aria-hidden="true" />
                  {agentStatus}
                </strong>
              </div>
              <div>
                <span>Event stream</span>
                <strong className="inline-status">
                  {offline ? (
                    <WifiOff size={14} aria-hidden="true" />
                  ) : (
                    <Wifi size={14} aria-hidden="true" />
                  )}
                  {connectionLabel}
                </strong>
              </div>
            </div>

            <div className="run-state" aria-live="polite" data-tour="run-state">
              <span>Workflow</span>
              <strong>{spaced(stage)}</strong>
              <small>{eventCount} trace {eventCount === 1 ? 'record' : 'records'}</small>
            </div>
          </>
        )}
      </div>

      {showRunContext && (
        <>
          <div className="disruption-strip" role="status" data-tour="disruption-strip">
            <div className="disruption-primary">
              <Radio size={17} aria-hidden="true" />
              <span>Active disruption</span>
              <strong className="alert-vessel">{scenario.alert.vessel_name}</strong>
            </div>
            <dl className="alert-figures">
              <div>
                <dt>Delay</dt>
                <dd>{delayHours} h</dd>
              </div>
              <div>
                <dt>Revised ETA</dt>
                <dd>{formatDateTime(scenario.alert.revised_eta)}</dd>
              </div>
              <div>
                <dt>Port call</dt>
                <dd>{scenario.alert.port_call}</dd>
              </div>
            </dl>
            <div className="demo-assurance">
              <ShieldCheck size={16} aria-hidden="true" />
              <span>DEMO ENVIRONMENT</span>
            </div>
          </div>

          <p className="objective-line">
            <span>Objective</span>
            {scenario.objective}
          </p>

          <ol className="stage-track" aria-label="Workflow stages" data-tour="stage-track">
            {STAGES.map((stageName, index) => (
              <li key={stageName}>
                <button
                  type="button"
                  className={
                    stage === 'FAILED'
                      ? 'stage-step failed'
                      : index < stageIndex
                        ? 'stage-step done'
                        : index === stageIndex
                          ? 'stage-step current'
                          : 'stage-step'
                  }
                  aria-current={index === stageIndex ? 'step' : undefined}
                  onClick={() => onStageSelect?.(stageName)}
                >
                  <span className="stage-marker" aria-hidden="true" />
                  {spaced(stageName)}
                </button>
              </li>
            ))}
          </ol>

          {/* Act 1's notice, and true only of Act 1. The benchmark is driven by a
              recorded arrival stream, so it carries its own provenance footer
              rather than being described as synthetic here. */}
          <p className="synthetic-notice">Synthetic data: {scenario.synthetic_notice}</p>
        </>
      )}
    </header>
  )
}
