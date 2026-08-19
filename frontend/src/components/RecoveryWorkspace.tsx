import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Gauge,
  Search,
  ShieldCheck,
  Timer,
  X,
  XCircle,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { PlanArchetype, PlanComparison, PlanEvaluation } from '../api/types'
import { formatMoney, titleCase } from '../lib/format'

interface RecoveryWorkspaceProps {
  comparison: PlanComparison | null
  selectedPlan?: PlanArchetype | null
  onSelectPlan?: (plan: PlanArchetype) => void
}

const SHORT_PLAN_NAME: Record<PlanArchetype, string> = {
  AGGRESSIVE_RUSH: 'Aggressive',
  STANDARD_REBOOK: 'Rebooking',
  OPTIMIZED_HYBRID: 'Hybrid',
}

function planRisk(evaluation: PlanEvaluation): 'HIGH' | 'MEDIUM' | 'LOW' {
  if (!evaluation.feasible || evaluation.metrics.yard_peak_occupancy_pct >= 90) return 'HIGH'
  if (
    evaluation.metrics.yard_peak_occupancy_pct >= 84 ||
    evaluation.metrics.max_additional_delay_hours >= 10
  ) {
    return 'MEDIUM'
  }
  return 'LOW'
}

function metricRows(evaluation: PlanEvaluation) {
  return [
    {
      label: 'Missed connections',
      value: String(evaluation.metrics.missed_connections),
      icon: AlertTriangle,
    },
    {
      label: 'Critical cargo protected',
      value: `${Math.round(evaluation.metrics.critical_cargo_protected_pct)}%`,
      icon: ShieldCheck,
    },
    {
      label: 'Peak yard occupancy',
      value: `${Math.round(evaluation.metrics.yard_peak_occupancy_pct)}%`,
      icon: Gauge,
    },
    {
      label: 'Maximum added delay',
      value: `${evaluation.metrics.max_additional_delay_hours} h`,
      icon: Timer,
    },
    {
      label: 'Illustrative cost',
      value: formatMoney(evaluation.metrics.cost.total),
      icon: CircleDollarSign,
    },
  ]
}

function PlanCard({
  evaluation,
  recommended,
  selected,
  onInspect,
  onSelect,
}: {
  evaluation: PlanEvaluation
  recommended: boolean
  selected: boolean
  onInspect: () => void
  onSelect?: () => void
}) {
  const risk = planRisk(evaluation)

  return (
    <article
      className={`recovery-plan-card${selected ? ' is-selected' : ''}${
        evaluation.feasible ? '' : ' is-infeasible'
      }`}
      aria-label={`Recovery plan: ${evaluation.plan.title}`}
      data-tour={recommended ? 'plan-recommended' : undefined}
    >
      <header className="recovery-plan-header">
        <div>
          <h3>{evaluation.plan.title}</h3>
        </div>
        <div className="plan-status-stack">
          {recommended && <span className="recommended-badge">Recommended</span>}
          <span className={`risk-badge risk-${risk.toLowerCase()}`}>Risk: {risk}</span>
        </div>
      </header>

      <div className="plan-feasibility">
        {evaluation.feasible ? (
          <>
            <CheckCircle2 aria-hidden="true" size={16} />
            <span>Feasible under deterministic constraints</span>
          </>
        ) : (
          <>
            <XCircle aria-hidden="true" size={16} />
            <span>Not feasible under current constraints</span>
          </>
        )}
      </div>

      <dl className="plan-metrics">
        {metricRows(evaluation).map(({ label, value, icon: Icon }) => (
          <div className="plan-metric" key={label}>
            <dt>
              <Icon aria-hidden="true" size={15} />
              {label}
            </dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      {(evaluation.rejection_reasons?.length ?? 0) > 0 && (
        <div className="plan-rejections" role="note">
          <strong>Constraint violations</strong>
          <ul>
            {evaluation.rejection_reasons?.map((reason, index) => (
              <li key={index}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <footer className="plan-card-actions">
        {onSelect && (
          <button
            type="button"
            className="secondary-action"
            onClick={onSelect}
            disabled={!evaluation.feasible}
          >
            {selected ? 'Selected' : 'Select plan'}
          </button>
        )}
        <button type="button" className="text-action" onClick={onInspect}>
          <Search aria-hidden="true" size={15} />
          Inspect Plan
        </button>
      </footer>
    </article>
  )
}

function PlanDrawer({ evaluation, onClose }: { evaluation: PlanEvaluation; onClose: () => void }) {
  const plan = evaluation.plan

  return (
    <aside
      className="plan-inspection-drawer"
      role="dialog"
      aria-modal="false"
      aria-labelledby="plan-inspection-title"
    >
      <header className="drawer-header">
        <div>
          <h2 id="plan-inspection-title">{plan.title}</h2>
        </div>
        <button type="button" className="icon-action" onClick={onClose} aria-label="Close plan details">
          <X aria-hidden="true" size={18} />
        </button>
      </header>

      <section className="drawer-section" aria-labelledby="plan-actions-title">
        <h3 id="plan-actions-title">Container movements</h3>
        {plan.actions.length > 0 ? (
          <ol className="plan-action-list">
            {plan.actions.map((action, index) => (
              <li key={`${action.action}-${action.onward_vessel}-${index}`}>
                <div className="action-route">
                  <strong>{titleCase(action.action)}</strong>
                  <ChevronRight aria-hidden="true" size={15} />
                  <span>{action.target_sailing ?? action.onward_vessel}</span>
                </div>
                <p>
                  {action.container_count} {titleCase(action.cargo_type)} containers from{' '}
                  {action.onward_vessel}.
                </p>
                <p className="action-rationale">{action.rationale}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="panel-placeholder">No container movements are included in this proposal.</p>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="plan-assumptions-title">
        <h3 id="plan-assumptions-title">Assumptions and warnings</h3>
        {(plan.assumptions?.length ?? 0) > 0 ? (
          <ul className="assumption-list">
            {plan.assumptions?.map((assumption, index) => (
              <li key={index}>{assumption}</li>
            ))}
          </ul>
        ) : (
          <p>No additional assumptions were recorded.</p>
        )}
        {(evaluation.rejection_reasons?.length ?? 0) > 0 && (
          <ul className="warning-list">
            {evaluation.rejection_reasons?.map((reason, index) => (
              <li key={index}>{reason}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="drawer-section" aria-labelledby="plan-cost-title">
        <h3 id="plan-cost-title">Illustrative cost basis</h3>
        <dl className="cost-breakdown">
          {evaluation.metrics.cost.components.map((component) => (
            <div key={component.name}>
              <dt>{component.name}</dt>
              <dd>{formatMoney(component.amount)}</dd>
              <dd className="cost-basis">{component.basis}</dd>
            </div>
          ))}
          <div className="cost-total">
            <dt>Total</dt>
            <dd>{formatMoney(evaluation.metrics.cost.total)}</dd>
          </div>
        </dl>
      </section>
    </aside>
  )
}

export function RecoveryWorkspace({
  comparison,
  selectedPlan = null,
  onSelectPlan,
}: RecoveryWorkspaceProps) {
  const [inspectedPlan, setInspectedPlan] = useState<PlanArchetype | null>(null)

  if (!comparison) {
    return (
      <section className="recovery-workspace" aria-labelledby="recovery-title">
        <header className="page-section-header">
          <div>
            <h2 id="recovery-title">Candidate strategies</h2>
          </div>
        </header>
        <p className="panel-placeholder">
          Recovery strategies appear after impact analysis, yard forecasting, and human conflict
          resolution are complete.
        </p>
      </section>
    )
  }

  const inspected = comparison.evaluations.find(
    (evaluation) => evaluation.plan.archetype === inspectedPlan,
  )
  const chartData = comparison.evaluations.map((evaluation) => ({
    plan: SHORT_PLAN_NAME[evaluation.plan.archetype],
    'Critical cargo protected': Math.round(evaluation.metrics.critical_cargo_protected_pct),
    'Yard peak': Math.round(evaluation.metrics.yard_peak_occupancy_pct),
    'Missed connections': evaluation.metrics.missed_connections,
  }))

  return (
    <section className="recovery-workspace" aria-labelledby="recovery-title">
      <header className="page-section-header">
        <div>
          <h2 id="recovery-title">Three strategies, one operator decision</h2>
        </div>
        <span className={`confidence-badge confidence-${comparison.confidence.toLowerCase()}`}>
          {comparison.confidence} confidence
        </span>
      </header>

      <div className="deterministic-notice" role="note" data-tour="deterministic-notice">
        <ShieldCheck aria-hidden="true" size={20} />
        <div>
          <strong>Deterministic Plan Evaluation</strong>
          <p>
            AI agents propose actions. Deterministic Python engines calculate every numerical
            outcome and enforce physical constraints.
          </p>
        </div>
        <span className="calculated-badge">Calculated by deterministic engine</span>
      </div>

      <div className="recovery-plan-grid" data-tour="plan-cards">
        {comparison.evaluations.map((evaluation) => (
          <PlanCard
            key={evaluation.plan.archetype}
            evaluation={evaluation}
            recommended={evaluation.plan.archetype === comparison.recommended}
            selected={evaluation.plan.archetype === selectedPlan}
            onInspect={() => setInspectedPlan(evaluation.plan.archetype)}
            onSelect={
              onSelectPlan ? () => onSelectPlan(evaluation.plan.archetype) : undefined
            }
          />
        ))}
      </div>

      <p className="recommendation-rationale">{comparison.rationale}</p>

      <section className="plan-comparison-panel" aria-labelledby="comparison-title" data-tour="plan-tradeoffs">
        <header className="panel-heading">
          <div>
            <h3 id="comparison-title">Operational trade-offs</h3>
          </div>
        </header>

        <div
          className="plan-comparison-chart"
          role="img"
          aria-label="Comparison of critical cargo protection, yard peak occupancy, and missed connections"
        >
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 12, right: 12, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#263746" strokeDasharray="2 4" />
              <XAxis dataKey="plan" stroke="#8292a1" fontSize={11} />
              <YAxis stroke="#8292a1" fontSize={11} width={34} />
              <Tooltip
                contentStyle={{
                  background: '#111b24',
                  border: '1px solid #354655',
                  color: '#e5edf3',
                  fontSize: 12,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#a9b7c3' }} />
              <Bar dataKey="Critical cargo protected" fill="#4ea3a8" isAnimationActive={false} />
              <Bar dataKey="Yard peak" fill="#c59a52" isAnimationActive={false} />
              <Bar dataKey="Missed connections" fill="#c86d68" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="comparison-table-wrap">
          <table className="comparison-table">
            <caption>Deterministic recovery-plan metrics</caption>
            <thead>
              <tr>
                <th scope="col">Plan</th>
                <th scope="col">Feasible</th>
                <th scope="col">Missed</th>
                <th scope="col">Critical cargo</th>
                <th scope="col">Yard peak</th>
                <th scope="col">Maximum delay</th>
                <th scope="col">Illustrative cost</th>
              </tr>
            </thead>
            <tbody>
              {comparison.evaluations.map((evaluation) => (
                <tr key={evaluation.plan.archetype}>
                  <th scope="row">{evaluation.plan.title}</th>
                  <td>{evaluation.feasible ? 'YES' : 'NO'}</td>
                  <td>{evaluation.metrics.missed_connections}</td>
                  <td>{Math.round(evaluation.metrics.critical_cargo_protected_pct)}%</td>
                  <td>{Math.round(evaluation.metrics.yard_peak_occupancy_pct)}%</td>
                  <td>{evaluation.metrics.max_additional_delay_hours} h</td>
                  <td>{formatMoney(evaluation.metrics.cost.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {inspected && <PlanDrawer evaluation={inspected} onClose={() => setInspectedPlan(null)} />}
    </section>
  )
}
