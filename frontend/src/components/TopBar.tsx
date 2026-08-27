import { History, Menu, Wifi, WifiOff } from 'lucide-react'

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
  /**
   * Everything except the brand describes one single-vessel run: the vessel
   * under disruption, the stage it has reached and the controls that drive it.
   * Act 2 replays a fleet across five months and has none of those, so it asks
   * for the brand alone rather than being given an idle stage rail and a vessel
   * it is not about.
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
  setupOpen?: boolean
  onStartTour?: () => void
  onToggleSetup?: () => void
  onStart?: () => void
  onStartReplay?: () => void
  onReset?: () => void
  onOpenNavigation: () => void
  onStageSelect?: (stage: WorkflowStage) => void
}

/*
 * One row, and only what a viewer cannot work out from the page below it: which
 * vessel is late, by how much, where the workflow has got to, and the controls
 * that move it. The five-cell status grid, the objective sentence, the labelled
 * seven-stage rail and two demo disclaimers that used to live here said the same
 * things the Command Center says, and cost 290px of a 900px screen before any
 * content began. Run identity moved into the setup panel, the objective and the
 * labelled rail onto the dashboard, the disclaimer into the app footer.
 */
export function TopBar({
  scenario,
  run,
  stage,
  delayHours,
  streaming,
  offline,
  transportState,
  showRunContext = true,
  subtitle,
  tourEnabled = true,
  setupOpen = false,
  onStartTour,
  onToggleSetup,
  onStart,
  onStartReplay,
  onReset,
  onOpenNavigation,
  onStageSelect,
}: TopBarProps) {
  const stageIndex = STAGES.indexOf(stage)
  const connectionLabel = offline
    ? 'Offline demo'
    : transportState === 'CONNECTING'
      ? 'Event stream connecting'
      : transportState === 'CONNECTED'
        ? 'Event stream connected'
        : transportState === 'RECONNECTING'
          ? 'Event stream reconnecting'
          : transportState === 'DISCONNECTED'
            ? 'Event stream disconnected'
            : transportState === 'ENDED'
              ? 'Event stream complete'
              : 'Event stream ready'

  return (
    <header className="top-bar">
      <div className="masthead" data-tour="masthead">
        <button
          className="mobile-nav-trigger"
          type="button"
          aria-label="Open navigation"
          onClick={onOpenNavigation}
        >
          <Menu size={18} aria-hidden="true" />
        </button>

        <h1>CASCADE</h1>

        {run?.mode === 'DEMO_REPLAY' && (
          <span className="replay-badge" role="status">
            <History size={13} aria-hidden="true" />
            DEMO REPLAY
          </span>
        )}

        {showRunContext ? (
          <p className="situation" data-tour="disruption-strip">
            <span className="alert-vessel">{scenario.alert.vessel_name}</span>
            <span className="situation__figure">
              <span>Delay</span>
              <span>{delayHours} h</span>
            </span>
            <span className="situation__figure">
              <span>Revised ETA</span>
              <span>{formatDateTime(scenario.alert.revised_eta)}</span>
            </span>
          </p>
        ) : (
          <p className="situation situation--plain">{subtitle ?? scenario.name}</p>
        )}

        {showRunContext && (
          <>
            {/*
              Seven dots and the name of the one the run is on. The old rail
              spelled all seven labels across the full window width, directly
              above the dashboard rail that spells the same seven in plainer
              words. This is the glance; that one is the detail.
            */}
            <ol className="stage-track" aria-label="Workflow stages" data-tour="stage-track">
              {STAGES.map((stageName, index) => (
                <li key={stageName}>
                  <button
                    type="button"
                    className={
                      stage === 'FAILED'
                        ? 'stage-dot failed'
                        : index < stageIndex
                          ? 'stage-dot done'
                          : index === stageIndex
                            ? 'stage-dot current'
                            : 'stage-dot'
                    }
                    aria-label={spaced(stageName)}
                    aria-current={index === stageIndex ? 'step' : undefined}
                    title={spaced(stageName)}
                    onClick={() => onStageSelect?.(stageName)}
                  />
                </li>
              ))}
            </ol>

            <p className="run-state" aria-live="polite" data-tour="run-state">
              <strong>{spaced(stage)}</strong>
            </p>
          </>
        )}

        <div className="masthead__actions">
          {showRunContext && (
            <span
              className="stream-state"
              role="img"
              title={connectionLabel}
              aria-label={connectionLabel}
            >
              {offline ? (
                <WifiOff size={14} aria-hidden="true" />
              ) : (
                <Wifi size={14} aria-hidden="true" />
              )}
            </span>
          )}

          {onStartTour && (
            <button
              type="button"
              className={`ghost-action${tourEnabled ? '' : ' is-unavailable'}`}
              data-tour="tour-launch"
              /* The visible word is inside the accessible name, so the label
                 still matches what a viewer would say out loud. */
              aria-label="Start tour"
              onClick={onStartTour}
              title={
                tourEnabled
                  ? 'Play the five-minute guided walkthrough'
                  : 'The guided tour needs the backend'
              }
            >
              Tour
            </button>
          )}

          {showRunContext && (
            <>
              <button
                type="button"
                className="ghost-action"
                aria-expanded={setupOpen}
                aria-controls="scenario-setup"
                onClick={onToggleSetup}
                title="Scenario controls and run identity"
              >
                Setup
              </button>
              <button
                type="button"
                className="ghost-action"
                data-tour="control-reset"
                onClick={onReset}
              >
                Reset
              </button>
              <button
                type="button"
                className="ghost-action"
                aria-label="Start demo replay"
                title="Start demo replay"
                disabled={streaming}
                onClick={onStartReplay}
              >
                Replay
              </button>
              <button
                type="button"
                className="primary-action"
                data-tour="control-start"
                disabled={streaming}
                onClick={onStart}
              >
                {streaming ? 'Working...' : 'Start run'}
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
