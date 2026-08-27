import type { RunCreated, RunMode, ScenarioControls } from '../api/types'
import type { ScenarioPreset } from '../data/demo'
import { formatDateTime, spaced } from '../lib/format'

export type BrainMode = Extract<RunMode, 'LIVE_STUB' | 'LIVE_CLAUDE' | 'LIVE_GEMINI'>

interface ControlsBarProps {
  controls: ScenarioControls
  brainMode: BrainMode
  disabled: boolean
  run: RunCreated | null
  portTime: string
  onChange: (controls: ScenarioControls) => void
  onBrainModeChange: (mode: BrainMode) => void
  scenarioPresets: ScenarioPreset[]
  selectedScenarioId: string
  onScenarioSelect: (scenarioId: string) => void
}

/*
 * Everything you set before a run, and nothing you read during one. The strip
 * used to be a nowrap flex row of five inputs plus three buttons: at 1440px the
 * Start button sat off the right edge of the window, so the app's primary action
 * was invisible on the most common laptop screen. The buttons now live in the
 * masthead, and what is left is a wrapping grid that cannot overflow.
 *
 * The panel is open while the run is READY and folds itself away once events
 * start arriving, because a delay slider is not something you reach for while
 * five agents are working.
 */
export function ControlsBar({
  controls,
  brainMode,
  disabled,
  run,
  portTime,
  onChange,
  onBrainModeChange,
  scenarioPresets,
  selectedScenarioId,
  onScenarioSelect,
}: ControlsBarProps) {
  return (
    <section
      className="control-strip"
      id="scenario-setup"
      aria-label="Scenario controls"
      data-tour="controls-bar"
    >
      <label className="control-field">
        Scenario
        <select
          aria-label="Scenario"
          value={selectedScenarioId}
          disabled={disabled}
          onChange={(event) => onScenarioSelect(event.target.value)}
        >
          {scenarioPresets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.title}
            </option>
          ))}
        </select>
      </label>

      <label className="control-field control-field--range">
        Delay
        <span>
          <input
            aria-label="Delay hours"
            type="range"
            min="6"
            max="24"
            step="1"
            value={controls.delay_hours}
            disabled={disabled}
            onChange={(event) => onChange({ ...controls, delay_hours: Number(event.target.value) })}
          />
          <output>{controls.delay_hours} hours</output>
        </span>
      </label>

      <label className="control-field">
        Priority
        <select
          aria-label="Priority emphasis"
          value={controls.priority_emphasis}
          disabled={disabled}
          onChange={(event) =>
            onChange({
              ...controls,
              priority_emphasis: event.target.value as ScenarioControls['priority_emphasis'],
            })
          }
        >
          <option value="BALANCED">Balanced</option>
          <option value="CARGO_PROTECTION">Cargo protection</option>
          <option value="CONGESTION_REDUCTION">Congestion reduction</option>
        </select>
      </label>

      <label className="control-field">
        Agent brain
        <select
          aria-label="Agent brain"
          value={brainMode}
          disabled={disabled}
          onChange={(event) => onBrainModeChange(event.target.value as BrainMode)}
        >
          <option value="LIVE_STUB">Scripted demo</option>
          <option value="LIVE_CLAUDE">Claude</option>
          <option value="LIVE_GEMINI">Gemini</option>
        </select>
      </label>

      <label className="control-field control-field--toggle">
        <input
          type="checkbox"
          checked={controls.alternative_sailing_failure}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...controls, alternative_sailing_failure: event.target.checked })
          }
        />
        Simulate sailing lookup timeout
      </label>

      {/* The run's identity, which used to occupy five permanent cells in the
          masthead. It is worth reading once per run, not once per glance. */}
      <dl className="control-identity">
        <div>
          <dt>Run</dt>
          <dd className="run-id">{run?.run_id ?? 'NOT STARTED'}</dd>
        </div>
        <div>
          <dt>Mode</dt>
          <dd>
            {run?.mode === 'DEMO_REPLAY'
              ? 'Recorded replay'
              : run
                ? spaced(run.mode).replace('LIVE ', '')
                : 'Scripted simulation'}
          </dd>
        </div>
        <div>
          <dt>Port time</dt>
          <dd>{formatDateTime(portTime)}</dd>
        </div>
      </dl>
    </section>
  )
}
