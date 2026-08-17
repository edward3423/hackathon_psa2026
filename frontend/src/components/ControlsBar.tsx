import type { RunMode, ScenarioControls } from '../api/types'

export type BrainMode = Extract<RunMode, 'LIVE_STUB' | 'LIVE_CLAUDE' | 'LIVE_GEMINI'>

interface ControlsBarProps {
  controls: ScenarioControls
  brainMode: BrainMode
  disabled: boolean
  onChange: (controls: ScenarioControls) => void
  onBrainModeChange: (mode: BrainMode) => void
  onStart: () => void
  onStartReplay: () => void
  onReset: () => void
}

export function ControlsBar({
  controls,
  brainMode,
  disabled,
  onChange,
  onBrainModeChange,
  onStart,
  onStartReplay,
  onReset,
}: ControlsBarProps) {
  return (
    <section className="control-strip" aria-label="Scenario controls">
      <label>
        Delay
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
      </label>

      <label>
        Priority emphasis
        <select
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

      <label>
        Agent brain
        <select
          aria-label="Agent brain"
          value={brainMode}
          disabled={disabled}
          onChange={(event) => onBrainModeChange(event.target.value as BrainMode)}
        >
          <option value="LIVE_STUB">Scripted (offline)</option>
          <option value="LIVE_CLAUDE">Live Claude (local CLI)</option>
          <option value="LIVE_GEMINI">Live Gemini (API key)</option>
        </select>
      </label>

      <label className="failure-toggle">
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

      <button className="primary-action" type="button" onClick={onStart} disabled={disabled}>
        {disabled ? 'Agents working...' : 'Start run'}
      </button>
      <button
        className="secondary-action"
        type="button"
        onClick={onStartReplay}
        disabled={disabled}
      >
        Start demo replay
      </button>
      <button className="secondary-action" type="button" onClick={onReset}>
        Reset
      </button>
    </section>
  )
}
