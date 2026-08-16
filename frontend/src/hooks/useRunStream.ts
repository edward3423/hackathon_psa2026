import { useCallback, useEffect, useRef, useState } from 'react'

import {
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

const RECONNECT_DELAY_MS = 1500
const MAX_RECONNECT_ATTEMPTS = 5

/** Event kinds that pause the stream and warrant a workflow-state refresh. */
const REFRESH_KINDS = new Set([
  'DISPUTE_OPENED',
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

  const sourceRef = useRef<EventSource | null>(null)
  const runRef = useRef<RunCreated | null>(null)
  const seenRef = useRef<Set<string>>(new Set())
  const endedRef = useRef(false)
  const attemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const closeSource = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

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
    (created: RunCreated) => {
      const source = new EventSource(eventsUrl(created.events_url))
      sourceRef.current = source

      source.addEventListener('trace', (message) => {
        attemptsRef.current = 0
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
        endedRef.current = true
        source.close()
        setStreaming(false)
        void refreshWorkflow()
      })

      source.onerror = () => {
        source.close()
        if (endedRef.current) return
        if (attemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          setStreaming(false)
          setError('The agent event stream was interrupted and could not reconnect.')
          void refreshWorkflow()
          return
        }
        attemptsRef.current += 1
        reconnectTimerRef.current = setTimeout(() => {
          if (!endedRef.current && runRef.current) openStream(runRef.current)
        }, RECONNECT_DELAY_MS)
      }
    },
    [refreshWorkflow],
  )

  const start = useCallback(
    async (controls: ScenarioControls, mode?: RunMode) => {
      closeSource()
      endedRef.current = false
      attemptsRef.current = 0
      seenRef.current = new Set()
      setEvents([])
      setWorkflow(null)
      setError(null)
      setStreaming(true)

      try {
        const created = await createRun(controls, mode)
        runRef.current = created
        setRun(created)
        openStream(created)
      } catch (cause: unknown) {
        setStreaming(false)
        setError(
          cause instanceof Error ? cause.message : 'The demonstration run could not start.',
        )
      }
    },
    [closeSource, openStream],
  )

  const resolveDispute = useCallback(
    async (body: DisputeResolutionRequest) => {
      const active = runRef.current
      if (!active) return
      await postDisputeResolution(active.run_id, body)
      await refreshWorkflow()
    },
    [refreshWorkflow],
  )

  const submitApproval = useCallback(
    async (body: ApprovalRequest) => {
      const active = runRef.current
      if (!active) return
      await postApproval(active.run_id, body)
      await refreshWorkflow()
    },
    [refreshWorkflow],
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
    seenRef.current = new Set()
    setRun(null)
    setEvents([])
    setWorkflow(null)
    setStreaming(false)
    setError(null)
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
    start,
    refreshWorkflow,
    resolveDispute,
    submitApproval,
    reset,
  }
}
