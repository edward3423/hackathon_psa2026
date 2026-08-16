import type { components } from './schema'

export type ScenarioState = components['schemas']['ScenarioState']
export type ScenarioControls = components['schemas']['ScenarioControls']
export type TraceEvent = components['schemas']['TraceEvent']
export type RunCreated = components['schemas']['RunCreated']
export type AgentName = components['schemas']['AgentName']
export type AgentActivity = components['schemas']['AgentActivity']
export type AgentStatus = components['schemas']['AgentStatus']
export type WorkflowState = components['schemas']['WorkflowState']
export type WorkflowStage = components['schemas']['WorkflowStage']
export type RunMode = components['schemas']['RunMode']
export type RunResults = components['schemas']['RunResults']
export type ConnectionAnalysis = components['schemas']['ConnectionAnalysis']
export type ConnectionGroupSummary = components['schemas']['ConnectionGroupSummary']
export type ConnectionStatus = components['schemas']['ConnectionStatus']
export type CargoType = components['schemas']['CargoType']
export type YardForecast = components['schemas']['YardForecast']
export type BlockForecast = components['schemas']['BlockForecast']
export type ReeferShortage = components['schemas']['ReeferShortage']
export type PlanComparison = components['schemas']['PlanComparison']
export type AlternativeSailingResult = components['schemas']['AlternativeSailingResult']
export type PlanEvaluation = components['schemas']['PlanEvaluation']
export type PlanArchetype = components['schemas']['PlanArchetype']
export type MockedAction = components['schemas']['MockedAction']
export type ActionReceipt = components['schemas']['ActionReceipt']
export type Dispute = components['schemas']['Dispute']
export type Confidence = components['schemas']['Confidence']
export type EventKind = components['schemas']['EventKind']

/**
 * Request bodies for endpoints that exist in the integration contract but are
 * not yet part of the generated OpenAPI schema. See
 * plan/contract_requests_frontend.md for the request to add them.
 */
export interface DisputeResolutionRequest {
  dispute_id: string
  confirmed_constraint: string
}

export type ApprovalDecision = 'APPROVED' | 'REJECTED'

export interface ApprovalRequest {
  plan_archetype: PlanArchetype
  decision: ApprovalDecision
  note?: string
}
