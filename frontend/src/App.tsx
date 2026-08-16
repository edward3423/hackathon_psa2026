import { useEffect, useMemo, useRef, useState } from 'react'

import type {
  AgentName,
  RunCreated,
  ScenarioControls,
  ScenarioState,
  TraceEvent,
} from './api/types'

const agents: AgentName[] = [
  'Coordinator Agent',
  'Impact Agent',
  'Yard Agent',
  'Recovery Agent',
  'Execution Agent',
]

const objectives: Record<AgentName, string> = {
  'Coordinator Agent': 'Interpret the alert and coordinate recovery.',
  'Impact Agent': 'Assess connections and cargo urgency.',
  'Yard Agent': 'Forecast yard and reefer capacity.',
  'Recovery Agent': 'Build and validate three recovery plans.',
  'Execution Agent': 'Prepare mocked actions after approval.',
}

function formatTimestamp(timestamp: string): string {
  return new Intl.DateTimeFormat('en-SG', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }).format(new Date(timestamp))
}

function App() {
  const [scenario, setScenario] = useState<ScenarioState | null>(null)
  const [controls, setControls] = useState<ScenarioControls>({
    delay_hours: 18,
    priority_emphasis: 'BALANCED',
    alternative_sailing_failure: true,
  })
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [run, setRun] = useState<RunCreated | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    fetch('/api/scenario')
      .then(async (response) => {
        if (!response.ok) throw new Error('Scenario could not be loaded.')
        return (await response.json()) as ScenarioState
      })
      .then((data) => {
        setScenario(data)
        setControls(data.controls)
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : 'Scenario could not be loaded.')
      })

    return () => sourceRef.current?.close()
  }, [])

  const latestByAgent = useMemo(() => {
    const latest = new Map<AgentName, TraceEvent>()
    events.forEach((event) => {
      if (event.agent) latest.set(event.agent, event)
    })
    return latest
  }, [events])

  const startRun = async () => {
    sourceRef.current?.close()
    setEvents([])
    setError(null)
    setStreaming(true)

    try {
      const response = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(controls),
      })
      if (!response.ok) throw new Error('The demonstration run could not start.')

      const created = (await response.json()) as RunCreated
      setRun(created)
      const source = new EventSource(created.events_url)
      sourceRef.current = source

      source.addEventListener('trace', (message) => {
        const event = JSON.parse((message as MessageEvent<string>).data) as TraceEvent
        setEvents((current) => [...current, event])
      })
      source.addEventListener('stream_end', () => {
        source.close()
        setStreaming(false)
      })
      source.onerror = () => {
        source.close()
        setStreaming(false)
        setError('The agent event stream was interrupted.')
      }
    } catch (cause: unknown) {
      setStreaming(false)
      setError(cause instanceof Error ? cause.message : 'The run could not start.')
    }
  }

  const reset = async () => {
    sourceRef.current?.close()
    await fetch('/api/reset', { method: 'POST' })
    setEvents([])
    setRun(null)
    setStreaming(false)
    setError(null)
    if (scenario) setControls(scenario.controls)
  }

  if (!scenario) {
    return <main className="loading">{error ?? 'Loading synthetic scenario...'}</main>
  }

  const stage = events.at(-1)?.stage ?? run?.stage ?? 'READY'

  return (
    <main className="app-shell">
      <header className="masthead">
        <div>
          <p className="product-label">PSA CODE SPRINT 2.0</p>
          <h1>CASCADE</h1>
          <p className="subtitle">Disruption recovery control room</p>
        </div>
        <div className="run-state" aria-live="polite">
          <span>WORKFLOW STAGE</span>
          <strong>{stage.replaceAll('_', ' ')}</strong>
          <small>{run ? run.mode.replaceAll('_', ' ') : 'LOCAL FIXTURE'}</small>
        </div>
      </header>

      <section className="alert-panel" aria-labelledby="alert-title">
        <div className="alert-marker" aria-hidden="true">!</div>
        <div className="alert-copy">
          <p className="section-label">ACTIVE DISRUPTION</p>
          <h2 id="alert-title">{scenario.alert.vessel_name}</h2>
          <p>{scenario.description}</p>
        </div>
        <dl className="alert-metrics">
          <div><dt>DELAY</dt><dd>{controls.delay_hours}h</dd></div>
          <div><dt>PORT CALL</dt><dd>{scenario.alert.port_call}</dd></div>
          <div><dt>HORIZON</dt><dd>{scenario.planning_horizon_hours}h</dd></div>
        </dl>
      </section>

      <section className="control-strip" aria-label="Scenario controls">
        <label>
          Delay
          <input
            aria-label="Delay hours"
            type="range"
            min="6"
            max="24"
            value={controls.delay_hours}
            disabled={streaming}
            onChange={(event) => setControls({ ...controls, delay_hours: Number(event.target.value) })}
          />
          <output>{controls.delay_hours} hours</output>
        </label>
        <label>
          Priority
          <select
            value={controls.priority_emphasis}
            disabled={streaming}
            onChange={(event) => setControls({
              ...controls,
              priority_emphasis: event.target.value as ScenarioControls['priority_emphasis'],
            })}
          >
            <option value="BALANCED">Balanced</option>
            <option value="CARGO_PROTECTION">Cargo protection</option>
            <option value="CONGESTION_REDUCTION">Congestion reduction</option>
          </select>
        </label>
        <label className="failure-toggle">
          <input
            type="checkbox"
            checked={controls.alternative_sailing_failure}
            disabled={streaming}
            onChange={(event) => setControls({
              ...controls,
              alternative_sailing_failure: event.target.checked,
            })}
          />
          Simulate sailing lookup timeout
        </label>
        <button className="primary-action" type="button" onClick={startRun} disabled={streaming}>
          {streaming ? 'Agents working...' : 'Start analysis'}
        </button>
        <button className="secondary-action" type="button" onClick={reset}>Reset</button>
      </section>

      {error && <p className="error-banner" role="alert">{error}</p>}

      <section className="workspace">
        <aside className="objective-panel">
          <p className="section-label">OPERATIONAL OBJECTIVE</p>
          <h2>Protect flow under pressure</h2>
          <p>{scenario.objective}</p>
          <div className="scope-note">
            <strong>SYNTHETIC DEMONSTRATION</strong>
            <span>{scenario.synthetic_notice}</span>
          </div>
        </aside>

        <section className="activity-panel" aria-labelledby="activity-title">
          <div className="panel-heading">
            <div>
              <p className="section-label">LIVE ORCHESTRATION</p>
              <h2 id="activity-title">Agent activity</h2>
            </div>
            <span className={streaming ? 'live-indicator active' : 'live-indicator'}>
              {streaming ? 'STREAMING' : 'IDLE'}
            </span>
          </div>

          <div className="agent-grid">
            {agents.map((agent) => {
              const latest = latestByAgent.get(agent)
              const isRunning = streaming && latest?.sequence === events.at(-1)?.sequence
              const status = latest ? (isRunning ? 'RUNNING' : 'COMPLETE') : 'WAITING'
              return (
                <article className={`agent-card ${status.toLowerCase()}`} key={agent}>
                  <header>
                    <div className="agent-index">{String(agents.indexOf(agent) + 1).padStart(2, '0')}</div>
                    <div><h3>{agent}</h3><p>{objectives[agent]}</p></div>
                    <span className="agent-status">{status}</span>
                  </header>
                  <div className="agent-detail">
                    <span>{latest?.tool ?? 'No tool call yet'}</span>
                    <strong>{latest?.confidence ?? 'NOT ASSESSED'}</strong>
                  </div>
                  <p className="agent-result">
                    {latest?.result ?? latest?.decision_summary ?? 'Waiting for coordinator handoff.'}
                  </p>
                  {latest && (
                    <footer>
                      <span>{latest.elapsed_ms ?? 0} ms</span>
                      <span>{latest.next_handoff ? `Next: ${latest.next_handoff}` : 'Final handoff'}</span>
                    </footer>
                  )}
                </article>
              )
            })}
          </div>
        </section>
      </section>

      <section className="trace-panel" aria-labelledby="trace-title">
        <div className="panel-heading">
          <div><p className="section-label">EXECUTION TRACE</p><h2 id="trace-title">Decision record</h2></div>
          <span>{events.length} events</span>
        </div>
        {events.length === 0 ? (
          <p className="empty-trace">Start analysis to stream agent decisions and tool results.</p>
        ) : (
          <ol className="trace-list">
            {events.map((event) => (
              <li key={event.event_id}>
                <time>{formatTimestamp(event.timestamp)} UTC</time>
                <strong>{event.agent ?? 'System'}</strong>
                <span>{event.kind.replaceAll('_', ' ')}</span>
                <p>{event.result ?? event.decision_summary}</p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  )
}

export default App

