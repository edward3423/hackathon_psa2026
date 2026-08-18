import type { RunMode, ScenarioControls } from '../api/types'
import type { ScenarioPreset } from '../data/demo'

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
  scenarioPresets: ScenarioPreset[]
  selectedScenarioId: string
  onScenarioSelect: (scenarioId: string) => void
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
  scenarioPresets,
  selectedScenarioId,
  onScenarioSelect,
}: ControlsBarProps) {
  return (
    <section className="control-strip" aria-label="Scenario controls">
      <label className="scenario-select">
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
          <option value="LIVE_STUB">Scripted Demo</option>
          <option value="LIVE_CLAUDE">Claude</option>
          <option value="LIVE_GEMINI">Gemini</option>
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
