import { useMemo, type CSSProperties } from 'react'
import { Background, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { ConnectionAnalysis, ConnectionStatus } from '../api/types'
import { CARGO_LABEL, groupTotals, STATUS_LABEL } from '../lib/derive'

const STATUS_COLOR: Record<ConnectionStatus, string> = {
  SAFE: '#15803d',
  AT_RISK: '#92600a',
  MISSED: '#b42318',
  RESOLVED: '#0e7490',
}

interface CascadeGraphProps {
  inboundVessel: string
  delayHours: number
  analysis: ConnectionAnalysis | null
}

function vesselNodeStyle(accent: string): CSSProperties {
  return {
    background: '#ffffff',
    color: '#1a2530',
    border: `1px solid ${accent}`,
    borderRadius: 2,
    fontSize: 12,
    width: 172,
    padding: '10px 12px',
  }
}

export function CascadeGraph({ inboundVessel, delayHours, analysis }: CascadeGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const nodes: Node[] = [
      {
        id: 'inbound',
        position: { x: 0, y: 40 },
        data: {
          label: (
            <div className="graph-vessel">
              <span className="graph-node-kind">DELAYED INBOUND</span>
              <strong>{inboundVessel}</strong>
              <span className="graph-node-meta">+{delayHours} h late</span>
            </div>
          ),
        },
        sourcePosition: 'right',
        targetPosition: 'left',
        style: vesselNodeStyle('#92600a'),
        draggable: false,
      } as Node,
    ]
    const edges: Edge[] = []

    if (!analysis) return { nodes, edges }

    const vessels = [...new Set(analysis.groups.map((group) => group.onward_vessel))]
    const groupGapY = 74
    const totalGroupHeight = analysis.groups.length * groupGapY
    const vesselGapY = Math.max(120, totalGroupHeight / Math.max(vessels.length, 1))

    // Center the inbound node against the group column.
    nodes[0].position = { x: 0, y: Math.max(0, totalGroupHeight / 2 - 30) }

    vessels.forEach((vessel, index) => {
      nodes.push({
        id: `vessel:${vessel}`,
        position: { x: 640, y: index * vesselGapY + 10 },
        data: {
          label: (
            <div className="graph-vessel">
              <span className="graph-node-kind">OUTBOUND</span>
              <strong>{vessel}</strong>
            </div>
          ),
        },
        sourcePosition: 'right',
        targetPosition: 'left',
        style: vesselNodeStyle('#d8dee4'),
        draggable: false,
      } as Node)
    })

    analysis.groups.forEach((group, index) => {
      const id = `group:${group.onward_vessel}:${group.cargo_type}:${group.status}`
      const color = STATUS_COLOR[group.status]
      nodes.push({
        id,
        position: { x: 300, y: index * groupGapY },
        data: {
          label: (
            <div className="graph-group">
              <strong>
                {group.container_count} x {CARGO_LABEL[group.cargo_type] ?? group.cargo_type}
              </strong>
              <span className="graph-status" style={{ color }}>
                {STATUS_LABEL[group.status]}
              </span>
            </div>
          ),
        },
        sourcePosition: 'right',
        targetPosition: 'left',
        style: {
          background: '#f7f9fa',
          border: `1px solid ${color}`,
          borderRadius: 2,
          fontSize: 11,
          width: 196,
          padding: '8px 10px',
        },
        draggable: false,
      } as Node)

      edges.push({
        id: `in-${id}`,
        source: 'inbound',
        target: id,
        style: { stroke: color, strokeWidth: 1.4 },
      })
      edges.push({
        id: `out-${id}`,
        source: id,
        target: `vessel:${group.onward_vessel}`,
        style: { stroke: color, strokeWidth: 1.4 },
        animated: group.status === 'AT_RISK',
      })
    })

    return { nodes, edges }
  }, [inboundVessel, delayHours, analysis])

  const totals = analysis ? groupTotals(analysis) : null

  return (
    <section className="graph-panel" aria-labelledby="graph-title">
      <div className="panel-heading">
        <div>
          <p className="section-label">CASCADE GRAPH</p>
          <h2 id="graph-title">Connection flows</h2>
        </div>
        {totals && (
          <dl className="graph-totals">
            <div className="status-safe">
              <dt>SAFE</dt>
              <dd data-testid="total-safe">{totals.safe}</dd>
            </div>
            <div className="status-at-risk">
              <dt>AT RISK</dt>
              <dd data-testid="total-at-risk">{totals.atRisk}</dd>
            </div>
            <div className="status-missed">
              <dt>MISSED</dt>
              <dd data-testid="total-missed">{totals.missed}</dd>
            </div>
            <div className="status-resolved">
              <dt>RESOLVED</dt>
              <dd data-testid="total-resolved">{totals.resolved}</dd>
            </div>
          </dl>
        )}
      </div>

      <div className="graph-canvas">
        <ReactFlow
          key={analysis ? `flow-${analysis.groups.length}` : 'flow-empty'}
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll={false}
          minZoom={0.4}
          maxZoom={1.4}
        >
          <Background color="#e3e9ee" gap={22} />
        </ReactFlow>
      </div>

      {!analysis && (
        <p className="panel-placeholder">
          Grouped container flows appear when connection analysis completes.
        </p>
      )}
    </section>
  )
}
