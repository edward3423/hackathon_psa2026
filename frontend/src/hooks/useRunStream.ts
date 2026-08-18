import { useCallback, useEffect, useRef, useState } from 'react'

import {
  ApiError,
  createRun,
  eventsUrl,
  getRun,
  postApproval,
  postDisputeResolution,
  resetDemo,
} from '../api/client'
import type {
  ApprovalRequest,
  DisputeResolutionRequest,
  RunCreated,
  RunMode,
  ScenarioControls,
  TraceEvent,
  WorkflowStage,
  WorkflowState,
} from '../api/types'
import {
  FALLBACK_SCENARIO,
  MOCK_ACTIONS,
  MOCK_CONNECTION_ANALYSIS,
  MOCK_DISPUTE,
  MOCK_PLAN_COMPARISON,
  MOCK_PLANNED_YARD,
  MOCK_RECEIPTS,
  MOCK_SAILINGS,
  MOCK_YARD_FORECAST,
  OFFLINE_OPENING_STEPS,
} from '../data/demo'

const RECONNECT_DELAY_MS = 1500
const MAX_RECONNECT_ATTEMPTS = 5

export type TransportState =
  | 'READY'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'DISCONNECTED'
  | 'OFFLINE'
  | 'ENDED'

function errorMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

function canUseOfflineFallback(cause: unknown): boolean {
  if (cause instanceof ApiError) return cause.status >= 500
  return cause instanceof TypeError
}

/** Event kinds that pause the stream and warrant a workflow-state refresh. */
const REFRESH_KINDS = new Set([
  'DISPUTE_OPENED',
  'AGENT_COMPLETED',
  'HUMAN_DECISION',
  'APPROVAL_REQUIRED',
  'ACTION_DISPATCHED',
  'RUN_COMPLETED',
  'ERROR',
])

export interface RunStream {
  run: RunCreated | null
  events: TraceEvent[]
  workflow: WorkflowState | null
  stage: WorkflowStage
  streaming: boolean
  error: string | null
  offline: boolean
  transportState: TransportState
  start: (controls: ScenarioControls, mode?: RunMode) => Promise<void>
  refreshWorkflow: () => Promise<void>
  resolveDispute: (body: DisputeResolutionRequest) => Promise<void>
  submitApproval: (body: ApprovalRequest) => Promise<void>
  reset: () => Promise<void>
}

export function useRunStream(): RunStream {
  const [run, setRun] = useState<RunCreated | null>(null)
  const [events, setEvents] = useState<TraceEvent[]>([])
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [offline, setOffline] = useState(false)
  const [transportState, setTransportState] = useState<TransportState>('READY')

  const sourceRef = useRef<EventSource | null>(null)
  const runRef = useRef<RunCreated | null>(null)
  const seenRef = useRef<Set<string>>(new Set())
  const endedRef = useRef(false)
  const attemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const offlineTimersRef = useRef<Array<ReturnType<typeof setTimeout>>>([])
  const offlineRef = useRef(false)
  const offlineSequenceRef = useRef(0)
  const offlineControlsRef = useRef<ScenarioControls | null>(null)

  const clearOfflineTimers = useCallback(() => {
    for (const timer of offlineTimersRef.current) clearTimeout(timer)
    offlineTimersRef.current = []
  }, [])

  const closeSource = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    clearOfflineTimers()
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [clearOfflineTimers])

  useEffect(() => closeSource, [closeSource])

  const refreshWorkflow = useCallback(async () => {
    const active = runRef.current
    if (!active) return
    try {
      const state = await getRun(active.run_id)
      setWorkflow(state)
    } catch {
      // Non-fatal: the trace stream remains the primary data source.
    }
  }, [])

  const openStream = useCallback(
    (created: RunCreated, reconnecting = false) => {
      setTransportState(reconnecting ? 'RECONNECTING' : 'CONNECTING')
      const source = new EventSource(eventsUrl(created.events_url))
      sourceRef.current = source

      const markConnected = () => {
        if (sourceRef.current !== source) return
        attemptsRef.current = 0
        setTransportState('CONNECTED')
        setStreaming(true)
        setError(null)
      }

      source.onopen = markConnected

      source.addEventListener('mode', markConnected)

      source.addEventListener('trace', (message) => {
        if (sourceRef.current !== source) return
        markConnected()
        let event: TraceEvent
        try {
          event = JSON.parse((message as MessageEvent<string>).data) as TraceEvent
        } catch {
          return
        }
        if (seenRef.current.has(event.event_id)) return
        seenRef.current.add(event.event_id)
        setEvents((current) => {
          const next = [...current, event]
          next.sort((a, b) => a.sequence - b.sequence)
          return next
        })
        if (REFRESH_KINDS.has(event.kind)) void refreshWorkflow()
      })

      source.addEventListener('stream_end', () => {
        if (sourceRef.current !== source) return
        endedRef.current = true
        source.close()
        if (sourceRef.current === source) sourceRef.current = null
        setStreaming(false)
        setTransportState('ENDED')
        void refreshWorkflow()
      })

      source.onerror = () => {
        if (sourceRef.current !== source) return
        source.close()
        sourceRef.current = null
        if (endedRef.current) return
        if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          setStreaming(false)
          setTransportState('DISCONNECTED')
          setError('The agent event stream was interrupted and could not reconnect.')
          void refreshWorkflow()
          return
        }
        attemptsRef.current += 1
        setTransportState('RECONNECTING')
        reconnectTimerRef.current = setTimeout(() => {
          if (!endedRef.current && runRef.current) openStream(runRef.current, true)
        }, RECONNECT_DELAY_MS)
      }
    },
    [refreshWorkflow],
  )

  const appendOfflineEvent = useCallback(
    (event: Omit<TraceEvent, 'event_id' | 'sequence' | 'timestamp'>): TraceEvent => {
      offlineSequenceRef.current += 1
      const sequence = offlineSequenceRef.current
      const timestamp = new Date(
        Date.parse(FALLBACK_SCENARIO.alert.event_time) + sequence * 3_000,
      ).toISOString()
      const complete: TraceEvent = {
        ...event,
        event_id: `offline-event-${sequence}`,
        sequence,
        timestamp,
      }
      seenRef.current.add(complete.event_id)
      setEvents((current) => [...current, complete])
      return complete
    },
    [],
  )

  const startOffline = useCallback(
    (controls: ScenarioControls, requestedMode: RunMode = 'LIVE_STUB') => {
      const mode: RunMode = requestedMode === 'DEMO_REPLAY' ? 'DEMO_REPLAY' : 'LIVE_STUB'
      offlineRef.current = true
      offlineControlsRef.current = controls
      offlineSequenceRef.current = 0
      setOffline(true)
      setTransportState('OFFLINE')
      setError(null)
      setStreaming(true)
      const created: RunCreated = {
        run_id: `offline-${Date.now()}`,
        mode,
        stage: 'READY',
        events_url: 'offline://scripted-events',
      }
      runRef.current = created
      setRun(created)
      setWorkflow({
        run_id: created.run_id,
        mode,
        stage: 'READY',
        scenario: {
          ...FALLBACK_SCENARIO,
          controls,
        },
        activities: [],
        trace: [],
        active_dispute: null,
        results: null,
      })

      for (const step of OFFLINE_OPENING_STEPS) {
        const timer = setTimeout(() => {
          const event = appendOfflineEvent(step.event)
          setWorkflow((current) => {
            if (!current) return current
            const previous = current.results ?? {}
            const results = { ...previous }
            if (event.tool === 'calculate_connection_risk()') {
              results.connection_analysis = MOCK_CONNECTION_ANALYSIS
            }
            if (event.tool === 'forecast_yard_and_reefer()') {
              results.baseline_yard = MOCK_YARD_FORECAST
            }
            return {
              ...current,
              stage: step.stage,
              trace: [...(current.trace ?? []), event],
              active_dispute: step.stage === 'DISPUTE' ? MOCK_DISPUTE : current.active_dispute,
              results,
            }
          })
          if (step.stage === 'DISPUTE') setStreaming(false)
        }, step.delayMs)
        offlineTimersRef.current.push(timer)
      }
    },
    [appendOfflineEvent],
  )

  const start = useCallback(
    async (controls: ScenarioControls, mode?: RunMode) => {
      closeSource()
      endedRef.current = false
      attemptsRef.current = 0
      seenRef.current = new Set()
      runRef.current = null
      setRun(null)
      setEvents([])
      setWorkflow(null)
      setError(null)
      setStreaming(true)
      setOffline(false)
      setTransportState('CONNECTING')
      offlineRef.current = false
      offlineControlsRef.current = controls

      try {
        const created = await createRun(controls, mode)
        runRef.current = created
        setRun(created)
        openStream(created)
      } catch (cause: unknown) {
        if (canUseOfflineFallback(cause)) {
          startOffline(controls, mode)
          return
        }
        setStreaming(false)
        setTransportState('DISCONNECTED')
        setError(errorMessage(cause, 'The demonstration run could not start.'))
      }
    },
    [closeSource, openStream, startOffline],
  )

  const resolveDispute = useCallback(
    async (body: DisputeResolutionRequest) => {
      const active = runRef.current
      if (!active) return
      if (offlineRef.current) {
        clearOfflineTimers()
        const decision = appendOfflineEvent({
          kind: 'HUMAN_DECISION',
          stage: 'PLANNING',
          agent: 'Coordinator Agent',
          decision_summary: `Constraint added to Recovery Agent: ${body.confirmed_constraint}`,
          confidence: 'HIGH',
          assumptions: [],
          next_handoff: 'Recovery Agent',
        })
        setStreaming(true)
        setWorkflow((current) =>
          current
            ? {
                ...current,
                stage: 'PLANNING',
                active_dispute: null,
                trace: [...(current.trace ?? []), decision],
                results: {
                  ...(current.results ?? {}),
                  connection_analysis: MOCK_CONNECTION_ANALYSIS,
                  baseline_yard: MOCK_YARD_FORECAST,
                },
              }
            : current,
        )

        const controls = offlineControlsRef.current
        const planningSteps: Array<{
          delay: number
          event: Omit<TraceEvent, 'event_id' | 'sequence' | 'timestamp'>
        }> = []
        if (controls?.alternative_sailing_failure) {
          planningSteps.push({
            delay: 220,
            event: {
              kind: 'ERROR',
              stage: 'PLANNING',
              agent: 'Recovery Agent',
              tool: 'find_alternative_sailings',
              error: 'Vessel schedule lookup timed out. Using cached data from 34 minutes ago.',
              confidence: 'MEDIUM',
              assumptions: ['Cached synthetic sailing capacity remains available.'],
            },
          })
        }
        planningSteps.push(
          {
            delay: 420,
            event: {
              kind: 'AGENT_STARTED',
              stage: 'PLANNING',
              agent: 'Recovery Agent',
              objective: 'Generate three candidate recovery plans under the confirmed constraint.',
              confidence: 'MEDIUM',
              assumptions: [],
            },
          },
          {
            delay: 720,
            event: {
              kind: 'TOOL_CALLED',
              stage: 'PLANNING',
              agent: 'Recovery Agent',
              tool: 'evaluate_recovery_plans()',
              input_summary: 'Three agent-proposed strategies and the human constraint',
              result: 'Deterministic engine evaluated feasibility, delay, cost, yard, and reefer pressure.',
              confidence: 'HIGH',
              assumptions: [],
            },
          },
          {
            delay: 1080,
            event: {
              kind: 'APPROVAL_REQUIRED',
              stage: 'AWAITING_APPROVAL',
              agent: 'Coordinator Agent',
              decision_summary: 'Optimized Hybrid is recommended. Human authorization is required.',
              confidence: 'MEDIUM',
              assumptions: [],
            },
          },
        )

        for (const step of planningSteps) {
          const timer = setTimeout(() => {
            const event = appendOfflineEvent(step.event)
            setWorkflow((current) => {
              if (!current) return current
              const approval = event.kind === 'APPROVAL_REQUIRED'
              return {
                ...current,
                stage: approval ? 'AWAITING_APPROVAL' : 'PLANNING',
                trace: [...(current.trace ?? []), event],
                results: {
                  ...(current.results ?? {}),
                  alternative_sailings: MOCK_SAILINGS,
                  ...(approval
                    ? {
                        plan_comparison: MOCK_PLAN_COMPARISON,
                        planned_yard: MOCK_PLANNED_YARD,
                      }
                    : {}),
                },
              }
            })
            if (event.kind === 'APPROVAL_REQUIRED') setStreaming(false)
          }, step.delay)
          offlineTimersRef.current.push(timer)
        }
        return
      }
      try {
        const state = await postDisputeResolution(active.run_id, body)
        setWorkflow(state)
      } catch (cause: unknown) {
        setError(errorMessage(cause, 'The constraint could not be submitted.'))
        throw cause
      }
    },
    [appendOfflineEvent, clearOfflineTimers],
  )

  const submitApproval = useCallback(
    async (body: ApprovalRequest) => {
      const active = runRef.current
      if (!active) return
      if (offlineRef.current) {
        clearOfflineTimers()
        const approved = body.decision === 'APPROVED'
        const decision = appendOfflineEvent({
          kind: 'HUMAN_DECISION',
          stage: approved ? 'EXECUTING' : 'COMPLETE',
          agent: 'Coordinator Agent',
          decision_summary: approved
            ? `${body.plan_archetype} approved for simulated execution.`
            : `${body.plan_archetype} rejected. No actions issued.`,
          confidence: 'HIGH',
          assumptions: [],
          next_handoff: approved ? 'Execution Agent' : null,
        })
        setWorkflow((current) =>
          current
            ? {
                ...current,
                stage: approved ? 'EXECUTING' : 'COMPLETE',
                trace: [...(current.trace ?? []), decision],
              }
            : current,
        )

        if (!approved) {
          const complete = appendOfflineEvent({
            kind: 'RUN_COMPLETED',
            stage: 'COMPLETE',
            agent: 'Coordinator Agent',
            result: 'Plan rejected. Workflow complete with no actions issued.',
            confidence: 'HIGH',
            assumptions: [],
          })
          setWorkflow((current) =>
            current
              ? {
                  ...current,
                  stage: 'COMPLETE',
                  trace: [...(current.trace ?? []), complete],
                }
              : current,
          )
          setStreaming(false)
          return
        }

        setStreaming(true)
        const actionTimer = setTimeout(() => {
          const event = appendOfflineEvent({
            kind: 'ACTION_DISPATCHED',
            stage: 'EXECUTING',
            agent: 'Execution Agent',
            tool: 'dispatch_mock_actions()',
            result: 'Three simulated actions validated and recorded locally.',
            confidence: 'HIGH',
            assumptions: ['No external terminal system is connected.'],
          })
          setWorkflow((current) =>
            current
              ? {
                  ...current,
                  stage: 'EXECUTING',
                  trace: [...(current.trace ?? []), event],
                  results: {
                    ...(current.results ?? {}),
                    dispatched_actions: MOCK_ACTIONS,
                    receipts: MOCK_RECEIPTS,
                  },
                }
              : current,
          )
        }, 360)
        const completionTimer = setTimeout(() => {
          const event = appendOfflineEvent({
            kind: 'RUN_COMPLETED',
            stage: 'COMPLETE',
            agent: 'Execution Agent',
            result: 'Simulated execution completed. No real-world actions were executed.',
            confidence: 'HIGH',
            assumptions: [],
          })
          setWorkflow((current) =>
            current
              ? {
                  ...current,
                  stage: 'COMPLETE',
                  trace: [...(current.trace ?? []), event],
                  results: {
                    ...(current.results ?? {}),
                    dispatched_actions: MOCK_ACTIONS,
                    receipts: MOCK_RECEIPTS,
                  },
                }
              : current,
          )
          setStreaming(false)
        }, 760)
        offlineTimersRef.current.push(actionTimer, completionTimer)
        return
      }
      try {
        const state = await postApproval(active.run_id, body)
        setWorkflow(state)
      } catch (cause: unknown) {
        setError(errorMessage(cause, 'The approval decision could not be submitted.'))
        throw cause
      }
    },
    [appendOfflineEvent, clearOfflineTimers],
  )

  const reset = useCallback(async () => {
    closeSource()
    endedRef.current = true
    try {
      await resetDemo()
    } catch {
      // Reset must always clear the local view even if the backend is down.
    }
    runRef.current = null
    offlineRef.current = false
    offlineControlsRef.current = null
    offlineSequenceRef.current = 0
    seenRef.current = new Set()
    setRun(null)
    setEvents([])
    setWorkflow(null)
    setStreaming(false)
    setError(null)
    setOffline(false)
    setTransportState('READY')
  }, [closeSource])

  const stage: WorkflowStage =
    workflow && (events.length === 0 || (workflow.trace?.length ?? 0) >= events.length)
      ? workflow.stage
      : (events.at(-1)?.stage ?? run?.stage ?? 'READY')

  return {
    run,
    events,
    workflow,
    stage,
    streaming,
    error,
    offline,
    transportState,
    start,
    refreshWorkflow,
    resolveDispute,
    submitApproval,
    reset,
  }
}
