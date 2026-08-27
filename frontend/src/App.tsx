import { lazy, Suspense, useEffect, useMemo, useState } from 'react'

import { getScenario } from './api/client'
import type {
  ApprovalDecision,
  PlanArchetype,
  RunMode,
  ScenarioControls,
  ScenarioState,
  WorkflowStage,
} from './api/types'
import { AgentActivityPanel } from './components/AgentActivityPanel'
import { AgentTopology } from './components/AgentTopology'
import { ApprovalBar } from './components/ApprovalBar'
import type { BrainMode } from './components/ControlsBar'
import { ControlsBar } from './components/ControlsBar'
import { DisputeOverlay } from './components/DisputeOverlay'
import { MetricsPanel } from './components/MetricsPanel'
import { OperationsOverview } from './components/OperationsOverview'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { TraceDrawer } from './components/TraceDrawer'
import { FALLBACK_SCENARIO, SCENARIO_PRESETS, type PageId } from './data/demo'
import { useBenchmark } from './hooks/useBenchmark'
import { useRunStream } from './hooks/useRunStream'
import { useTour } from './tour/engine'
import { TourOverlay } from './tour/TourOverlay'

const BenchmarkPage = lazy(() =>
  import('./components/BenchmarkPage').then((module) => ({ default: module.BenchmarkPage })),
)
const CascadeGraph = lazy(() =>
  import('./components/CascadeGraph').then((module) => ({ default: module.CascadeGraph })),
)
const ConnectionsPage = lazy(() =>
  import('./components/ConnectionsPage').then((module) => ({ default: module.ConnectionsPage })),
)
const ExecutionPage = lazy(() =>
  import('./components/ExecutionPage').then((module) => ({ default: module.ExecutionPage })),
)
const OperationsTimeline = lazy(() =>
  import('./components/OperationsTimeline').then((module) => ({
    default: module.OperationsTimeline,
  })),
)
const RecoveryWorkspace = lazy(() =>
  import('./components/RecoveryWorkspace').then((module) => ({
    default: module.RecoveryWorkspace,
  })),
)
const ReplayPage = lazy(() =>
  import('./components/ReplayPage').then((module) => ({ default: module.ReplayPage })),
)
const SystemStatusPage = lazy(() =>
  import('./components/SystemStatusPage').then((module) => ({
    default: module.SystemStatusPage,
  })),
)
const YardOperationsPage = lazy(() =>
  import('./components/YardOperationsPage').then((module) => ({
    default: module.YardOperationsPage,
  })),
)
const YardForecastPanel = lazy(() =>
  import('./components/YardForecastPanel').then((module) => ({
    default: module.YardForecastPanel,
  })),
)

const SYSTEM_MODE_BY_BRAIN = {
  LIVE_STUB: 'SCRIPTED',
  LIVE_GEMINI: 'GEMINI',
  LIVE_CLAUDE: 'CLAUDE',
} as const

const BRAIN_MODE_BY_SYSTEM = {
  SCRIPTED: 'LIVE_STUB',
  GEMINI: 'LIVE_GEMINI',
  CLAUDE: 'LIVE_CLAUDE',
} as const

function pageForStage(stage: WorkflowStage): PageId {
  if (stage === 'DISPUTE') return 'agents'
  if (stage === 'PLANNING' || stage === 'AWAITING_APPROVAL') return 'recovery'
  if (stage === 'EXECUTING' || stage === 'COMPLETE') return 'execution'
  if (stage === 'FAILED') return 'system'
  return 'overview'
}

function App() {
  const [scenario, setScenario] = useState<ScenarioState | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
  const [backendConnected, setBackendConnected] = useState(true)
  const [controls, setControls] = useState<ScenarioControls>({
    delay_hours: 18,
    priority_emphasis: 'BALANCED',
    alternative_sailing_failure: true,
  })
  const [selectedPlan, setSelectedPlan] = useState<PlanArchetype | null>(null)
  const [resolvedDisputeIds, setResolvedDisputeIds] = useState<Set<string>>(new Set())
  const [dismissedDisputeEventIds, setDismissedDisputeEventIds] = useState<Set<string>>(
    new Set(),
  )
  const [approvalSubmitted, setApprovalSubmitted] = useState(false)
  const [brainMode, setBrainMode] = useState<BrainMode>('LIVE_STUB')
  const [selectedScenarioId, setSelectedScenarioId] = useState('severe-delay')
  const [activePage, setActivePage] = useState<PageId>('overview')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const [cursorHour, setCursorHour] = useState(0)
  /*
   * The scenario strip is demo rigging, not operator UI: presets, a delay
   * slider, the reasoning engine, and the run's identity. It sat above the
   * dashboard on every load and was most of what made the top of the screen
   * read as a developer console. It is now a debug panel - closed by default,
   * toggled with the backtick key or the Debug control in the masthead.
   */
  const [setupOpen, setSetupOpen] = useState(false)

  /*
   * Backtick toggles the debug panel. Ignored while a field has focus, so a
   * backtick typed into the operator note stays a backtick, and ignored with
   * modifiers so it cannot collide with a browser shortcut.
   */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== '`' || event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (target?.closest('input, select, textarea, [contenteditable="true"]')) return
      event.preventDefault()
      setSetupOpen((current) => !current)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const stream = useRunStream()
  // Act 2 keeps its own stream. The two never share state, so a benchmark
  // cannot disturb the golden run and vice versa.
  const benchmark = useBenchmark()
  const { events, workflow, run, stage, streaming, error, offline, transportState } = stream

  useEffect(() => {
    getScenario()
      .then((data) => {
        setScenario(data)
        setControls(data.controls)
        setBackendConnected(true)
      })
      .catch((cause: unknown) => {
        setScenarioError(
          cause instanceof Error ? cause.message : 'Scenario could not be loaded.',
        )
        setBackendConnected(false)
        setScenario(FALLBACK_SCENARIO)
        setControls(FALLBACK_SCENARIO.controls)
      })
  }, [])

  const displayScenario = workflow?.scenario ?? scenario
  const results = workflow?.results ?? null
  const comparison = results?.plan_comparison ?? null
  // The connection analysis and yard forecast the operational pages render are
  // the pre-recovery baseline, and the Recovery page reports what the approved
  // plan projects instead. Manual QA read the two as rival answers to the same
  // question, so the pages that show the baseline are given the approved plan
  // and made to say which is which.
  const approvedEvaluation = useMemo(() => {
    const archetype = results?.approved_plan
    if (!archetype || !comparison) return null
    return (
      comparison.evaluations.find((evaluation) => evaluation.plan.archetype === archetype) ?? null
    )
  }, [comparison, results?.approved_plan])
  const offlineActive = offline || !backendConnected

  // The guided tour drives real runs through the real controls, so every figure
  // it puts on screen is genuinely computed. That makes the backend a hard
  // requirement rather than a preference.
  const tour = useTour({ enabled: !offlineActive })

  const selectedPreset = useMemo(() => {
    const preset =
      SCENARIO_PRESETS.find((candidate) => candidate.id === selectedScenarioId) ??
      SCENARIO_PRESETS[0]
    return { ...preset, delayHours: controls.delay_hours }
  }, [controls.delay_hours, selectedScenarioId])

  useEffect(() => {
    if (!comparison || selectedPlan !== null) return
    const recommended = comparison.evaluations.find(
      (evaluation) => evaluation.plan.archetype === comparison.recommended,
    )
    const fallback = comparison.evaluations.find((evaluation) => evaluation.feasible)
    setSelectedPlan(recommended?.feasible ? recommended.plan.archetype : fallback?.plan.archetype ?? null)
  }, [comparison, selectedPlan])

  const disputeOpenEvent = useMemo(() => {
    const opened = [...events].reverse().find((event) => event.kind === 'DISPUTE_OPENED')
    if (!opened) return null
    const resolvedLater = events.some(
      (event) => event.kind === 'HUMAN_DECISION' && event.sequence > opened.sequence,
    )
    return resolvedLater ? null : opened
  }, [events])

  const activeDispute = useMemo(() => {
    const dispute = workflow?.active_dispute ?? null
    if (!dispute || dispute.resolved_by_human) return null
    if (resolvedDisputeIds.has(dispute.dispute_id)) return null
    return dispute
  }, [workflow, resolvedDisputeIds])

  const showDispute =
    activeDispute !== null ||
    (disputeOpenEvent !== null &&
      stage === 'DISPUTE' &&
      !dismissedDisputeEventIds.has(disputeOpenEvent.event_id))

  const resolveDispute = async (disputeId: string, confirmedConstraint: string) => {
    await stream.resolveDispute({
      dispute_id: disputeId,
      confirmed_constraint: confirmedConstraint,
    })
    setResolvedDisputeIds((current) => new Set(current).add(disputeId))
    if (disputeOpenEvent) {
      setDismissedDisputeEventIds((current) => new Set(current).add(disputeOpenEvent.event_id))
    }
  }

  const decideApproval = async (
    plan: PlanArchetype,
    decision: ApprovalDecision,
    note?: string,
  ) => {
    await stream.submitApproval({ plan_archetype: plan, decision, note })
    setApprovalSubmitted(true)
    if (decision === 'APPROVED') setActivePage('execution')
  }

  const startRun = (mode?: RunMode) => {
    setSetupOpen(false)
    setSelectedPlan(null)
    setResolvedDisputeIds(new Set())
    setDismissedDisputeEventIds(new Set())
    setApprovalSubmitted(false)
    setCursorHour(0)
    if (mode === 'DEMO_REPLAY') setActivePage('replay')
    void stream.start(controls, mode)
  }

  const resetRun = async () => {
    // Closed, not reopened: the panel is debug tooling now, and closing it on
    // reset also means the guided tour's click on the Debug control always
    // opens rather than sometimes toggling shut.
    setSetupOpen(false)
    setSelectedPlan(null)
    setResolvedDisputeIds(new Set())
    setDismissedDisputeEventIds(new Set())
    setApprovalSubmitted(false)
    setCursorHour(0)
    setActivePage('overview')
    await stream.reset()
    const fresh = await getScenario().catch(() => null)
    if (fresh) {
      setScenario(fresh)
      setControls(fresh.controls)
      setBackendConnected(true)
      setScenarioError(null)
    } else if (scenario) {
      setControls(scenario.controls)
      setBackendConnected(false)
    }
  }

  const startTour = async () => {
    if (!tour.available) {
      tour.start()
      return
    }
    // The opening card must describe the state behind it. Starting over a
    // completed run showed old IDs, completed agents, and COMPLETE while the
    // narration introduced a disruption that had supposedly just arrived.
    await resetRun()
    tour.start()
  }

  const selectScenario = (scenarioId: string) => {
    const preset = SCENARIO_PRESETS.find((candidate) => candidate.id === scenarioId)
    if (!preset) return
    setSelectedScenarioId(scenarioId)
    setControls({
      delay_hours: preset.delayHours,
      priority_emphasis: preset.priorityEmphasis,
      alternative_sailing_failure: preset.lookupFailure,
    })
  }

  if (!displayScenario) {
    return <main className="loading">Loading synthetic scenario...</main>
  }

  const showApproval = stage === 'AWAITING_APPROVAL' && !approvalSubmitted
  const receipts = results?.receipts ?? []
  const actions = results?.dispatched_actions ?? []

  const renderPage = () => {
    switch (activePage) {
      case 'connections':
        return (
          <div className="connections-workspace">
            <CascadeGraph
              inboundVessel={displayScenario.alert.vessel_name}
              delayHours={controls.delay_hours}
              analysis={results?.connection_analysis ?? null}
            />
            <ConnectionsPage
              analysis={results?.connection_analysis ?? null}
              approved={approvedEvaluation}
              inboundVessel={displayScenario.alert.vessel_name}
              offline={offlineActive}
            />
          </div>
        )
      case 'yard':
      case 'reefers':
        return (
          <YardOperationsPage
            baseline={results?.baseline_yard ?? null}
            planned={results?.planned_yard ?? null}
            selectedPlan={selectedPlan}
            cursorHour={cursorHour}
            mode={activePage === 'yard' ? 'yard' : 'reefers'}
          />
        )
      case 'agents':
        return (
          <div className="agent-workspace">
            <AgentTopology events={events} activities={workflow?.activities} />
            <AgentActivityPanel
              events={events}
              activities={workflow?.activities}
              streaming={streaming}
            />
            <TraceDrawer events={events} />
          </div>
        )
      case 'recovery':
        return (
          <div className="recovery-page-stack">
            <RecoveryWorkspace
              comparison={comparison}
              selectedPlan={selectedPlan}
              onSelectPlan={setSelectedPlan}
            />
            <YardForecastPanel
              baseline={results?.baseline_yard ?? null}
              planned={results?.planned_yard ?? null}
              selectedPlan={selectedPlan}
            />
          </div>
        )
      case 'execution':
        return <ExecutionPage actions={actions} receipts={receipts} />
      case 'replay':
        return (
          <ReplayPage
            initialCursor={0}
            events={events}
            live={streaming}
            scenarioTitle={selectedPreset.title}
            onCursorChange={(index) =>
              setCursorHour(events.length > 1 ? Math.round((index / (events.length - 1)) * 72) : 0)
            }
          />
        )
      case 'benchmark':
        return <BenchmarkPage benchmark={benchmark} />
      case 'system':
        return (
          <SystemStatusPage
            backendConnected={backendConnected}
            sseConnected={transportState === 'CONNECTED' || transportState === 'ENDED'}
            agentMode={SYSTEM_MODE_BY_BRAIN[brainMode]}
            onAgentModeChange={(mode) => setBrainMode(BRAIN_MODE_BY_SYSTEM[mode])}
          />
        )
      case 'overview':
      default:
        return (
          <div className="command-center-grid">
            <OperationsOverview
              scenario={displayScenario}
              preset={selectedPreset}
              controls={workflow?.scenario.controls ?? controls}
              stage={stage}
              analysis={results?.connection_analysis ?? null}
              baselineYard={results?.baseline_yard ?? null}
              cursorHour={cursorHour}
              onStageSelect={(selectedStage) => setActivePage(pageForStage(selectedStage))}
            />
            <aside className="command-center-rail" aria-label="Run context">
              <AgentActivityPanel
                events={events}
                activities={workflow?.activities}
                streaming={streaming}
              />
              <MetricsPanel
                analysis={results?.connection_analysis ?? null}
                baselineYard={results?.baseline_yard ?? null}
                sailings={results?.alternative_sailings ?? null}
              />
              <TraceDrawer events={events} />
            </aside>
          </div>
        )
    }
  }

  // Act 2 is a different demonstration, not a different view of the Act 1 run.
  // The vessel header, the scenario controls and the run scrubber all describe
  // one delayed ship, so none of them belong over a five-month fleet replay.
  const actTwo = activePage === 'benchmark'

  return (
    <div className={`app-shell${showApproval ? ' with-approval' : ''}`}>
      <Sidebar
        currentPage={activePage}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileNavigationOpen}
        replayActive={run?.mode === 'DEMO_REPLAY'}
        onNavigate={setActivePage}
        onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
        onCloseMobile={() => setMobileNavigationOpen(false)}
      />

      <div className="app-frame">
        <TopBar
          scenario={displayScenario}
          run={run}
          stage={stage}
          delayHours={controls.delay_hours}
          streaming={streaming}
          offline={offlineActive}
          transportState={transportState}
          showRunContext={!actTwo}
          subtitle={actTwo ? 'Red Sea 2024 blind replay benchmark' : undefined}
          tourEnabled={tour.available}
          setupOpen={setupOpen}
          onStartTour={() => void startTour()}
          onToggleSetup={() => setSetupOpen((current) => !current)}
          onStart={() => startRun(brainMode === 'LIVE_STUB' ? undefined : brainMode)}
          onStartReplay={() => startRun('DEMO_REPLAY')}
          onReset={() => void resetRun()}
          onOpenNavigation={() => setMobileNavigationOpen(true)}
          onStageSelect={(selectedStage) => setActivePage(pageForStage(selectedStage))}
        />

        {!actTwo && setupOpen && (
          <ControlsBar
            controls={controls}
            brainMode={brainMode}
            disabled={streaming}
            run={run}
            portTime={displayScenario.alert.event_time}
            onChange={setControls}
            onBrainModeChange={setBrainMode}
            scenarioPresets={SCENARIO_PRESETS}
            selectedScenarioId={selectedScenarioId}
            onScenarioSelect={selectScenario}
          />
        )}

        {scenarioError && (
          <p className="offline-banner" role="status">
            Backend unavailable. The clearly labeled offline demo is active. {scenarioError}
          </p>
        )}
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}

        <main className="app-content" id="main-content">
          <Suspense fallback={<p className="page-loading">Loading workspace...</p>}>
            {renderPage()}
          </Suspense>

          {/* Its own boundary. Sharing one with the page meant a lazily loaded
              scrubber held the whole workspace behind "Loading workspace...",
              including the Command Center, which loads nothing.

              The timeline scrubs the 72 hours of one Act 1 vessel run. The Act 2
              benchmark spans 153 days, so this control does not belong there. */}
          {!actTwo && (
            <Suspense fallback={null}>
              <OperationsTimeline
                cursorHour={cursorHour}
                onCursorChange={setCursorHour}
                stage={stage}
                events={events}
              />
            </Suspense>
          )}
        </main>

        {/* The four demo disclaimers that used to sit in the sidebar footer, the
            masthead, the header and the bottom of the dashboard, said once. Act 2
            carries its own provenance footer and is not this scenario. */}
        {!actTwo && (
          <footer className="app-footer">
            <span className="app-footer__badge">DEMO ENVIRONMENT</span>
            <p>Synthetic data: {displayScenario.synthetic_notice}</p>
            <p>Mocked actions only. No real terminal or carrier system is contacted.</p>
          </footer>
        )}
      </div>

      {showDispute && (
        <DisputeOverlay
          dispute={activeDispute}
          openEvent={disputeOpenEvent}
          onResolve={resolveDispute}
        />
      )}

      {showApproval && (
        <ApprovalBar
          comparison={comparison}
          selectedPlan={selectedPlan}
          onSelectPlan={setSelectedPlan}
          onDecide={decideApproval}
        />
      )}

      <TourOverlay tour={tour} />
    </div>
  )
}

export default App
