import { CheckCircle2, ClipboardCheck, FileCheck2, LockKeyhole, RadioTower } from 'lucide-react'

import type { ActionReceipt, MockedAction } from '../api/types'
import { humanizeOperationalText, titleCase } from '../lib/format'

interface ExecutionPageProps {
  actions?: MockedAction[] | null
  receipts?: ActionReceipt[] | null
}

const ACTION_ICON = {
  TERMINAL_WORK_ORDER: ClipboardCheck,
  REEFER_CHECK: CheckCircle2,
  CARRIER_NOTICE: RadioTower,
} as const

export function ExecutionPage({ actions = [], receipts = [] }: ExecutionPageProps) {
  const actionItems = actions ?? []
  const receiptItems = receipts ?? []
  const hasExecution = actionItems.length > 0 || receiptItems.length > 0

  return (
    <section className="execution-page" aria-labelledby="execution-title">
      <header className="page-section-header">
        <div>
          <h2 id="execution-title">Validated mock actions</h2>
        </div>
        <span className="simulation-badge">
          <LockKeyhole aria-hidden="true" size={15} />
          SIMULATION ONLY
        </span>
      </header>

      {!hasExecution ? (
        <div className="execution-empty-state">
          <LockKeyhole aria-hidden="true" size={24} />
          <h3>Execution is locked</h3>
          <p>Mock actions appear only after explicit operator approval.</p>
          <strong>NO REAL-WORLD ACTIONS WERE EXECUTED</strong>
        </div>
      ) : (
        <>
          <div className="execution-safety-notice" role="note" data-tour="execution-safety">
            <LockKeyhole aria-hidden="true" size={20} />
            <div>
              <strong>NO REAL-WORLD ACTIONS WERE EXECUTED</strong>
              <p>Every item below was validated and recorded inside the synthetic environment.</p>
            </div>
          </div>

          {actionItems.length > 0 && (
            <section
              className="mock-action-section"
              aria-labelledby="mock-actions-title"
              data-tour="execution-actions"
            >
              <header className="panel-heading">
                <div>
                  <h3 id="mock-actions-title">Mocked action register</h3>
                </div>
                <span className="record-count">{actionItems.length} actions</span>
              </header>

              <div className="mock-action-list">
                {actionItems.map((action) => {
                  const Icon = ACTION_ICON[action.action_type]
                  const receipt = receiptItems.find((candidate) => candidate.action_id === action.action_id)

                  return (
                    <article className="mock-action-card" key={action.action_id}>
                      <header>
                        <span className="action-icon">
                          <Icon aria-hidden="true" size={18} />
                        </span>
                        <div>
                          <p className="action-type">
                            {humanizeOperationalText(action.action_type)}
                          </p>
                          <h4>{action.action_id}</h4>
                        </div>
                      </header>
                      <p className="action-description">
                        {humanizeOperationalText(action.description)}
                      </p>
                      <details className="execution-details">
                        <summary>Inspect action details</summary>
                        <dl>
                          <div>
                            <dt>Plan</dt>
                            <dd>{titleCase(action.plan_archetype)}</dd>
                          </div>
                          <div>
                            <dt>Payload summary</dt>
                            <dd>{humanizeOperationalText(action.payload_summary)}</dd>
                          </div>
                          <div>
                            <dt>Validation</dt>
                            <dd>{receipt?.status ?? 'Pending'}</dd>
                          </div>
                        </dl>
                      </details>
                    </article>
                  )
                })}
              </div>
            </section>
          )}

          {receiptItems.length > 0 && (
            <section
              className="receipt-section"
              aria-labelledby="execution-receipts-title"
              data-tour="execution-receipts"
            >
              <header className="panel-heading">
                <div>
                  <h3 id="execution-receipts-title">EXECUTION RECEIPTS (MOCKED)</h3>
                </div>
                <span className="record-count">{receiptItems.length} records</span>
              </header>

              <div className="receipt-list">
                {receiptItems.map((receipt) => (
                  <details className="receipt-card" key={`${receipt.action_id}-${receipt.receipt_ref ?? 'none'}`}>
                    <summary>
                      <FileCheck2 aria-hidden="true" size={18} />
                      <span>
                        <strong>{receipt.receipt_ref ?? receipt.action_id}</strong>
                        <small>{receipt.action_id}</small>
                      </span>
                      <span className={`receipt-status status-${receipt.status.toLowerCase()}`}>
                        {receipt.status}
                      </span>
                    </summary>
                    <div className="receipt-detail">
                      <p>{humanizeOperationalText(receipt.detail)}</p>
                      <dl>
                        <div>
                          <dt>Source</dt>
                          <dd>Execution Agent</dd>
                        </div>
                        <div>
                          <dt>Mode</dt>
                          <dd>MOCK</dd>
                        </div>
                        <div>
                          <dt>External effect</dt>
                          <dd>NONE</dd>
                        </div>
                      </dl>
                    </div>
                  </details>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </section>
  )
}
