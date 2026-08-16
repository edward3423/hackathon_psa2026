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
}

export function TopBar({ scenario, run, stage, delayHours }: TopBarProps) {
  const stageIndex = STAGES.indexOf(stage)

  return (
    <header className="top-bar">
      <div className="masthead-row">
        <div className="brand">
          <p className="product-label">PSA CODE SPRINT 2.0</p>
          <h1>CASCADE</h1>
          <p className="subtitle">Disruption recovery control room</p>
        </div>

        <div className="alert-summary" role="status">
          <span className="alert-tag">ACTIVE DISRUPTION</span>
          <strong className="alert-vessel">{scenario.alert.vessel_name}</strong>
          <dl className="alert-figures">
            <div>
              <dt>DELAY</dt>
              <dd>{delayHours} h</dd>
            </div>
            <div>
              <dt>REVISED ETA</dt>
              <dd>{formatDateTime(scenario.alert.revised_eta)}</dd>
            </div>
            <div>
              <dt>PORT CALL</dt>
              <dd>{scenario.alert.port_call}</dd>
            </div>
          </dl>
        </div>

        <div className="run-state" aria-live="polite">
          <span>WORKFLOW STAGE</span>
          <strong>{spaced(stage)}</strong>
          {run?.mode === 'DEMO_REPLAY' ? (
            <span className="replay-badge">DEMO REPLAY</span>
          ) : (
            <small>{run ? spaced(run.mode) : 'NO RUN'}</small>
          )}
        </div>
      </div>

      <p className="objective-line">
        <span className="objective-label">OBJECTIVE</span>
        {scenario.objective}
      </p>

      <ol className="stage-track" aria-label="Workflow stages">
        {STAGES.map((s, index) => (
          <li
            key={s}
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
          >
            {spaced(s)}
          </li>
        ))}
      </ol>

      <p className="synthetic-notice">SYNTHETIC DATA: {scenario.synthetic_notice}</p>
    </header>
  )
}
