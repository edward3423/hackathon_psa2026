import { useState } from 'react'
import {
  ArrowDown,
  Bot,
  CheckCircle2,
  Cpu,
  Database,
  HardDrive,
  LockKeyhole,
  Monitor,
  Radio,
  Server,
  Workflow,
  XCircle,
} from 'lucide-react'

export type SystemAgentMode = 'SCRIPTED' | 'GEMINI' | 'CLAUDE'

interface SystemStatusPageProps {
  backendConnected?: boolean
  sseConnected?: boolean
  agentMode?: SystemAgentMode
  onAgentModeChange?: (mode: SystemAgentMode) => void
}

const MODES: Array<{ value: SystemAgentMode; label: string; detail: string }> = [
  { value: 'SCRIPTED', label: 'Scripted', detail: 'Deterministic demonstration workflow' },
  { value: 'GEMINI', label: 'Gemini', detail: 'Live model path when configured' },
  { value: 'CLAUDE', label: 'Claude', detail: 'Local command-line model path' },
]

const ARCHITECTURE = [
  { label: 'React Dashboard', icon: Monitor },
  { label: 'FastAPI Backend', icon: Server },
  { label: 'Agent Workflow', icon: Workflow },
  { label: 'Deterministic Calculation Engine', icon: Cpu },
  { label: 'Human Approval', icon: LockKeyhole },
  { label: 'Mock Execution', icon: CheckCircle2 },
]

export function SystemStatusPage({
  backendConnected = true,
  sseConnected = true,
  agentMode,
  onAgentModeChange,
}: SystemStatusPageProps) {
  const [localMode, setLocalMode] = useState<SystemAgentMode>('SCRIPTED')
  const activeMode = agentMode ?? localMode

  const selectMode = (mode: SystemAgentMode) => {
    if (agentMode === undefined) setLocalMode(mode)
    onAgentModeChange?.(mode)
  }

  const statuses = [
    { label: 'Frontend', value: 'ONLINE', healthy: true, icon: Monitor },
    {
      label: 'FastAPI Backend',
      value: backendConnected ? 'CONNECTED' : 'DISCONNECTED',
      healthy: backendConnected,
      icon: Server,
    },
    {
      label: 'SSE Stream',
      value: sseConnected ? 'CONNECTED' : 'DISCONNECTED',
      healthy: sseConnected,
      icon: Radio,
    },
    { label: 'Agent Mode', value: activeMode, healthy: true, icon: Bot },
    { label: 'Calculation Engine', value: 'READY', healthy: true, icon: Cpu },
    { label: 'Data Source', value: 'SYNTHETIC JSON FIXTURES', healthy: true, icon: HardDrive },
    { label: 'Database', value: 'NONE - IN MEMORY', healthy: true, icon: Database },
    { label: 'External Port Systems', value: 'NOT CONNECTED', healthy: false, icon: XCircle },
  ]

  return (
    <section className="system-status-page" aria-labelledby="system-status-title">
      <header className="page-section-header">
        <div>
          <h2 id="system-status-title">Demonstration environment</h2>
        </div>
        <span className="demo-environment-badge">DEMO ENVIRONMENT</span>
      </header>

      <div className="system-status-grid">
        <section className="system-health-panel" aria-labelledby="health-title" data-tour="system-health">
          <header className="panel-heading">
            <div>
              <h3 id="health-title">Component health</h3>
            </div>
          </header>
          <dl className="status-row-list">
            {statuses.map(({ label, value, healthy, icon: Icon }) => (
              <div className="status-row" key={label}>
                <dt>
                  <Icon aria-hidden="true" size={17} />
                  {label}
                </dt>
                <dd className={healthy ? 'status-healthy' : 'status-isolated'}>{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="agent-mode-panel" aria-labelledby="agent-mode-title" data-tour="system-mode">
          <header className="panel-heading">
            <div>
              <h3 id="agent-mode-title">Agent mode</h3>
            </div>
          </header>
          <p className="panel-description">
            Select the provider used when the next run starts. Availability is still enforced by
            the backend.
          </p>
          <div className="agent-mode-options" role="radiogroup" aria-label="Agent mode">
            {MODES.map((mode) => (
              <button
                type="button"
                role="radio"
                aria-checked={activeMode === mode.value}
                className={activeMode === mode.value ? 'is-selected' : ''}
                key={mode.value}
                onClick={() => selectMode(mode.value)}
              >
                <strong>{mode.label}</strong>
                <span>{mode.detail}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      <section className="architecture-panel" aria-labelledby="architecture-title">
        <header className="panel-heading">
          <div>
            <h3 id="architecture-title">From alert to mock execution</h3>
          </div>
        </header>

        <ol className="architecture-flow">
          {ARCHITECTURE.map(({ label, icon: Icon }, index) => (
            <li key={label}>
              <div className="architecture-node">
                <Icon aria-hidden="true" size={20} />
                <span>{label}</span>
              </div>
              {index < ARCHITECTURE.length - 1 && (
                <ArrowDown className="architecture-arrow" aria-hidden="true" size={18} />
              )}
            </li>
          ))}
        </ol>

        <div className="architecture-support-grid">
          <div>
            <strong>SSE event stream</strong>
            <span>Named trace events and reconnect support</span>
          </div>
          <div>
            <strong>Model adapters</strong>
            <span>Gemini, local Claude, and offline scripted modes</span>
          </div>
          <div>
            <strong>Synthetic fixtures</strong>
            <span>Versioned JSON scenarios and recorded replay events</span>
          </div>
          <div>
            <strong>Run storage</strong>
            <span>Temporary in-memory state for this demonstration</span>
          </div>
        </div>
      </section>

      <aside
        className="system-boundaries"
        aria-label="Demonstration system boundaries"
        data-tour="system-boundaries"
      >
        <strong>Operational boundaries</strong>
        <ul>
          <li>No production database</li>
          <li>No real terminal systems connected</li>
          <li>No real actions executed</li>
        </ul>
      </aside>
    </section>
  )
}
