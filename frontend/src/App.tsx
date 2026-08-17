import { useEffect, useMemo, useState } from 'react'

import { getScenario } from './api/client'
import type {
  ApprovalDecision,
  PlanArchetype,
  RunMode,
  ScenarioControls,
  ScenarioState,
} from './api/types'
import type { BrainMode } from './components/ControlsBar'
import { AgentActivityPanel } from './components/AgentActivityPanel'
import { ApprovalBar } from './components/ApprovalBar'
import { CascadeGraph } from './components/CascadeGraph'
import { ControlsBar } from './components/ControlsBar'
import { DisputeOverlay } from './components/DisputeOverlay'
import { MetricsPanel } from './components/MetricsPanel'
import { TopBar } from './components/TopBar'
import { TraceDrawer } from './components/TraceDrawer'
import { YardForecastPanel } from './components/YardForecastPanel'
import { useRunStream } from './hooks/useRunStream'

function App() {
  const [scenario, setScenario] = useState<ScenarioState | null>(null)
  const [scenarioError, setScenarioError] = useState<string | null>(null)
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

  const stream = useRunStream()
  const { events, workflow, run, stage, streaming, error } = stream

  useEffect(() => {
    getScenario()
      .then((data) => {
        setScenario(data)
        setControls(data.controls)
      })
      .catch((cause: unknown) => {
        setScenarioError(
          cause instanceof Error ? cause.message : 'Scenario could not be loaded.',
        )
      })
  }, [])

  const results = workflow?.results ?? null
  const comparison = results?.plan_comparison ?? null

  useEffect(() => {
    if (comparison && selectedPlan === null) {
      setSelectedPlan(comparison.recommended ?? comparison.evaluations[0]?.plan.archetype ?? null)
    }
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
  }

  const startRun = (mode?: RunMode) => {
    setSelectedPlan(null)
    setResolvedDisputeIds(new Set())
    setDismissedDisputeEventIds(new Set())
    setApprovalSubmitted(false)
    void stream.start(controls, mode)
  }

  const resetRun = async () => {
    setSelectedPlan(null)
    setResolvedDisputeIds(new Set())
    setDismissedDisputeEventIds(new Set())
    setApprovalSubmitted(false)
    await stream.reset()
    const fresh = await getScenario().catch(() => null)
    if (fresh) {
      setScenario(fresh)
      setControls(fresh.controls)
    } else if (scenario) {
      setControls(scenario.controls)
    }
  }

  if (!scenario) {
    return <main className="loading">{scenarioError ?? 'Loading synthetic scenario...'}</main>
  }

  const showApproval = stage === 'AWAITING_APPROVAL' && !approvalSubmitted
  const receipts = results?.receipts ?? []

  return (
    <main className={`app-shell${showApproval ? ' with-approval' : ''}`}>
      <TopBar scenario={scenario} run={run} stage={stage} delayHours={controls.delay_hours} />

      <ControlsBar
        controls={controls}
        brainMode={brainMode}
        disabled={streaming}
        onChange={setControls}
        onBrainModeChange={setBrainMode}
        onStart={() => startRun(brainMode === 'LIVE_STUB' ? undefined : brainMode)}
        onStartReplay={() => startRun('DEMO_REPLAY')}
        onReset={() => void resetRun()}
      />

      {error && <p className="error-banner" role="alert">{error}</p>}

      <div className="workspace">
        <CascadeGraph
          inboundVessel={scenario.alert.vessel_name}
          delayHours={controls.delay_hours}
          analysis={results?.connection_analysis ?? null}
        />
        <AgentActivityPanel
          events={events}
          activities={workflow?.activities}
          streaming={streaming}
        />
        <MetricsPanel
          analysis={results?.connection_analysis ?? null}
          baselineYard={results?.baseline_yard ?? null}
          comparison={comparison}
          sailings={results?.alternative_sailings ?? null}
          selectedPlan={selectedPlan}
          onSelectPlan={setSelectedPlan}
          receipts={receipts}
        />
      </div>

      <YardForecastPanel
        baseline={results?.baseline_yard ?? null}
        planned={results?.planned_yard ?? null}
        selectedPlan={selectedPlan}
      />

      <TraceDrawer events={events} />

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
    </main>
  )
}

export default App
