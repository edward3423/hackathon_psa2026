import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, createBenchmark, eventsUrl, getBenchmark } from '../api/client'
import type {
  BenchmarkCreated,
  BenchmarkEvent,
  BenchmarkResult,
  BenchmarkStage,
  CreateBenchmarkRequest,
  FleetArm,
} from '../api/types'
import { MOCK_BENCHMARK_RESULT, OFFLINE_BENCHMARK_NOTICE } from '../data/demo'

/**
 * Deliberately separate from `useRunStream`. That hook models one single-vessel
 * workflow with pauses for human decisions; a benchmark has no pauses, no
 * approvals, and three concurrent series. Sharing the state machine would force
 * both to carry the other's assumptions.
 */

export type BenchmarkTransport = 'READY' | 'CONNECTING' | 'STREAMING' | 'ENDED' | 'OFFLINE' | 'ERROR'

/** One point on one arm's line, accumulated as day ticks arrive. */
export interface ArmSeriesPoint {
  date: string
  dayIndex: number
  rollingWaitDays: number
  queueLength: number
  teuWaiting: number
}

export type ArmSeries = Record<string, ArmSeriesPoint[]>

function errorMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

function canUseOfflineFallback(cause: unknown): boolean {
  if (cause instanceof ApiError) return cause.status >= 500
  return cause instanceof TypeError
}

/** Rebuild the per-arm series a completed result already contains. */
function seriesFromResult(result: BenchmarkResult): ArmSeries {
  const series: ArmSeries = {}
  for (const arm of result.arms) {
    series[arm.arm] = arm.daily.map((day) => ({
      date: day.date,
      dayIndex: day.day_index,
      rollingWaitDays: day.rolling_wait_days,
      queueLength: day.queue_length,
      teuWaiting: day.teu_waiting,
    }))
  }
  return series
}

/**
 * The decisions a completed result carries, keyed by the day they were taken,
 * so offline playback can release them in step with the lines instead of
 * dropping the panel that explains what CASCADE actually did.
 */
function decisionEventsByDay(result: BenchmarkResult): Map<number, BenchmarkEvent[]> {
  const byDay = new Map<number, BenchmarkEvent[]>()
  let sequence = 0
  for (const arm of result.arms) {
    for (const decision of arm.decisions ?? []) {
      sequence += 1
      const event: BenchmarkEvent = {
        event_id: `offline-decision-${sequence}`,
        sequence,
        timestamp: `${decision.date}T00:00:00Z`,
        kind: 'DECISION_TAKEN',
        arm: arm.arm,
        decision,
        message: decision.decision.rationale,
      }
      byDay.set(decision.day_index, [...(byDay.get(decision.day_index) ?? []), event])
    }
  }
  return byDay
}

export interface BenchmarkStream {
  created: BenchmarkCreated | null
  stage: BenchmarkStage
  transport: BenchmarkTransport
  /** Arms announced so far, in the order the backend ran them. */
  arms: FleetArm[]
  series: ArmSeries
  decisions: BenchmarkEvent[]
  dayIndex: number
  result: BenchmarkResult | null
  playbackNotice: string | null
  error: string | null
  offline: boolean
  running: boolean
  start: (request?: CreateBenchmarkRequest) => Promise<void>
}

export function useBenchmark(): BenchmarkStream {
  const [created, setCreated] = useState<BenchmarkCreated | null>(null)
  const [stage, setStage] = useState<BenchmarkStage>('READY')
  const [transport, setTransport] = useState<BenchmarkTransport>('READY')
  const [arms, setArms] = useState<FleetArm[]>([])
  const [series, setSeries] = useState<ArmSeries>({})
  const [decisions, setDecisions] = useState<BenchmarkEvent[]>([])
  const [dayIndex, setDayIndex] = useState(-1)
  const [result, setResult] = useState<BenchmarkResult | null>(null)
  const [playbackNotice, setPlaybackNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [offline, setOffline] = useState(false)

  const sourceRef = useRef<EventSource | null>(null)
  const receivedRef = useRef(0)
  const offlineTimersRef = useRef<Array<ReturnType<typeof setTimeout>>>([])

  const closeStream = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    for (const timer of offlineTimersRef.current) clearTimeout(timer)
    offlineTimersRef.current = []
  }, [])

  useEffect(() => closeStream, [closeStream])

  const applyEvent = useCallback((event: BenchmarkEvent) => {
    receivedRef.current += 1
    switch (event.kind) {
      case 'ARM_STARTED':
        if (event.arm) {
          const arm = event.arm
          setArms((current) => (current.includes(arm) ? current : [...current, arm]))
        }
        break
      case 'DAY_TICK':
        if (event.arm && event.day) {
          const arm = event.arm
          const day = event.day
          setSeries((current) => ({
            ...current,
            [arm]: [
              ...(current[arm] ?? []),
              {
                date: day.date,
                dayIndex: day.day_index,
                rollingWaitDays: day.rolling_wait_days,
                queueLength: day.queue_length,
                teuWaiting: day.teu_waiting,
              },
            ],
          }))
          setDayIndex((current) => Math.max(current, day.day_index))
        }
        break
      case 'DECISION_TAKEN':
        setDecisions((current) => [...current, event])
        break
      case 'BENCHMARK_FAILED':
        setStage('FAILED')
        setError(event.error ?? event.message)
        break
      default:
        break
    }
  }, [])

  const startOffline = useCallback(() => {
    // Same shape as the Act 1 offline fallback: the page stays useful with no
    // backend, and every number on screen is the committed mock result.
    setOffline(true)
    setTransport('OFFLINE')
    setError(null)
    setArms(MOCK_BENCHMARK_RESULT.arms.map((arm) => arm.arm))
    setDecisions([])
    setSeries({})
    setDayIndex(-1)

    const full = seriesFromResult(MOCK_BENCHMARK_RESULT)
    const decisionsByDay = decisionEventsByDay(MOCK_BENCHMARK_RESULT)
    const longest = Math.max(...Object.values(full).map((points) => points.length), 0)
    for (let index = 0; index < longest; index += 1) {
      const timer = setTimeout(() => {
        const due = decisionsByDay.get(index)
        if (due) setDecisions((current) => [...current, ...due])
        setSeries((current) => {
          const next: ArmSeries = { ...current }
          for (const [arm, points] of Object.entries(full)) {
            if (index < points.length) next[arm] = [...(next[arm] ?? []), points[index]]
          }
          return next
        })
        setDayIndex(index)
        if (index === longest - 1) {
          setResult(MOCK_BENCHMARK_RESULT)
          setStage('COMPLETE')
          setTransport('ENDED')
        }
      }, index * 12)
      offlineTimersRef.current.push(timer)
    }
  }, [])

  const openStream = useCallback(
    (benchmark: BenchmarkCreated) => {
      const source = new EventSource(eventsUrl(benchmark.events_url))
      sourceRef.current = source

      source.addEventListener('benchmark', (message) => {
        if (sourceRef.current !== source) return
        setTransport('STREAMING')
        let event: BenchmarkEvent
        try {
          event = JSON.parse((message as MessageEvent<string>).data) as BenchmarkEvent
        } catch {
          return
        }
        applyEvent(event)
      })

      source.addEventListener('stream_end', () => {
        if (sourceRef.current !== source) return
        source.close()
        sourceRef.current = null
        setTransport('ENDED')
        // The events are already on screen; ask only for the final result.
        void getBenchmark(benchmark.benchmark_id, receivedRef.current)
          .then((state) => {
            setStage(state.stage)
            setResult(state.result ?? null)
            if (state.error) setError(state.error)
          })
          .catch((cause: unknown) => {
            setError(errorMessage(cause, 'The benchmark result could not be fetched.'))
          })
      })

      source.onerror = () => {
        if (sourceRef.current !== source) return
        source.close()
        sourceRef.current = null
        setTransport('ERROR')
        setError('The benchmark event stream was interrupted.')
      }
    },
    [applyEvent],
  )

  const start = useCallback(
    async (
      request: CreateBenchmarkRequest = { seed: 42, playback_speed: 1, brain: 'SCRIPTED' },
    ) => {
      closeStream()
      receivedRef.current = 0
      setCreated(null)
      setArms([])
      setSeries({})
      setDecisions([])
      setDayIndex(-1)
      setResult(null)
      setError(null)
      setOffline(false)
      setStage('RUNNING')
      setTransport('CONNECTING')

      try {
        const benchmark = await createBenchmark(request)
        setCreated(benchmark)
        setPlaybackNotice(benchmark.playback_notice)
        openStream(benchmark)
      } catch (cause: unknown) {
        if (canUseOfflineFallback(cause)) {
          setPlaybackNotice(OFFLINE_BENCHMARK_NOTICE)
          startOffline()
          return
        }
        setStage('FAILED')
        setTransport('ERROR')
        setError(errorMessage(cause, 'The benchmark could not start.'))
      }
    },
    [closeStream, openStream, startOffline],
  )

  return {
    created,
    stage,
    transport,
    arms,
    series,
    decisions,
    dayIndex,
    result,
    playbackNotice,
    error,
    offline,
    running: transport === 'CONNECTING' || transport === 'STREAMING' || transport === 'OFFLINE',
    start,
  }
}
