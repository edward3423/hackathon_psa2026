import type {
  ApprovalRequest,
  DisputeResolutionRequest,
  RunCreated,
  RunMode,
  ScenarioControls,
  ScenarioState,
  WorkflowState,
} from './types'

/**
 * API base. Empty by default so requests stay relative and go through the
 * Vite dev proxy. Set VITE_API_BASE to target another host or port.
 */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(path: string, status: number, detail: unknown) {
    const detailMessage =
      typeof detail === 'string'
        ? detail
        : detail === undefined || detail === null
          ? `Request to ${path} failed with status ${status}.`
          : JSON.stringify(detail)
    super(detailMessage)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function errorDetail(response: Response): Promise<unknown> {
  const body = await response.text()
  if (!body) return response.statusText || undefined

  try {
    const parsed = JSON.parse(body) as unknown
    if (typeof parsed === 'object' && parsed !== null && 'detail' in parsed) {
      return (parsed as { detail: unknown }).detail
    }
    return parsed
  } catch {
    return body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    throw new ApiError(path, response.status, await errorDetail(response))
  }
  return (await response.json()) as T
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getScenario(): Promise<ScenarioState> {
  return request<ScenarioState>('/api/scenario')
}

export interface AisStatus {
  available: boolean
  provider: string | null
  coverage: string
}

export interface AisPosition {
  mmsi: string
  name: string
  latitude: number
  longitude: number
  course: number | null
  speed_knots: number | null
  heading: number | null
  timestamp: string | null
  source: 'LIVE_AIS'
}

export function getAisStatus(): Promise<AisStatus> {
  return request<AisStatus>('/api/ais/status')
}

/**
 * Create a run. When `mode` is given (DEMO_REPLAY), it is sent both as a
 * query parameter and as an extra body field so either backend contract
 * variant works; see plan/contract_requests_frontend.md.
 */
export function createRun(controls: ScenarioControls, mode?: RunMode): Promise<RunCreated> {
  const path = mode ? `/api/runs?mode=${mode}` : '/api/runs'
  const body = mode ? { ...controls, mode } : controls
  return postJson<RunCreated>(path, body)
}

export function getRun(runId: string): Promise<WorkflowState> {
  return request<WorkflowState>(`/api/runs/${runId}`)
}

export function postDisputeResolution(
  runId: string,
  body: DisputeResolutionRequest,
): Promise<WorkflowState> {
  return postJson<WorkflowState>(`/api/runs/${runId}/dispute-resolution`, body)
}

export function postApproval(runId: string, body: ApprovalRequest): Promise<WorkflowState> {
  return postJson<WorkflowState>(`/api/runs/${runId}/approval`, body)
}

export async function resetDemo(): Promise<void> {
  await request<ScenarioState>('/api/reset', { method: 'POST' })
}

/** Resolve a possibly relative SSE URL against the configured API base. */
export function eventsUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${API_BASE}${url}`
}
