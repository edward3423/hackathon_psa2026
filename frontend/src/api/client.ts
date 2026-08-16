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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}.`)
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
): Promise<unknown> {
  return postJson(`/api/runs/${runId}/dispute-resolution`, body)
}

export function postApproval(runId: string, body: ApprovalRequest): Promise<unknown> {
  return postJson(`/api/runs/${runId}/approval`, body)
}

export async function resetDemo(): Promise<void> {
  const response = await fetch(`${API_BASE}/api/reset`, { method: 'POST' })
  if (!response.ok) {
    throw new Error(`Reset failed with status ${response.status}.`)
  }
}

/** Resolve a possibly relative SSE URL against the configured API base. */
export function eventsUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `${API_BASE}${url}`
}
