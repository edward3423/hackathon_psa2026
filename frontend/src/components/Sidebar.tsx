import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  Bot,
  Cable,
  ClipboardCheck,
  History,
  LayoutDashboard,
  LineChart,
  PanelLeftClose,
  PanelLeftOpen,
  Route,
  Ship,
  Snowflake,
  Warehouse,
} from 'lucide-react'

import type { PageId } from '../data/demo'

interface NavigationItem {
  id: PageId
  label: string
  icon: LucideIcon
}

const NAVIGATION_ITEMS: NavigationItem[] = [
  { id: 'overview', label: 'Command Center', icon: LayoutDashboard },
  { id: 'connections', label: 'Connections', icon: Cable },
  { id: 'yard', label: 'Yard', icon: Warehouse },
  { id: 'reefers', label: 'Reefers', icon: Snowflake },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'recovery', label: 'Recovery', icon: Route },
  { id: 'execution', label: 'Execution', icon: ClipboardCheck },
  { id: 'replay', label: 'Replay', icon: History },
  { id: 'benchmark', label: 'Crisis Benchmark', icon: LineChart },
  { id: 'system', label: 'System', icon: Activity },
]

export interface SidebarProps {
  currentPage: PageId
  collapsed: boolean
  mobileOpen?: boolean
  replayActive?: boolean
  onNavigate: (page: PageId) => void
  onToggleCollapsed: () => void
  onCloseMobile?: () => void
}

export function Sidebar({
  currentPage,
  collapsed,
  mobileOpen = false,
  replayActive = false,
  onNavigate,
  onToggleCollapsed,
  onCloseMobile,
}: SidebarProps) {
  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="operations-sidebar__backdrop"
          aria-label="Close navigation"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`operations-sidebar${collapsed ? ' operations-sidebar--collapsed' : ''}${
          mobileOpen ? ' operations-sidebar--mobile-open' : ''
        }`}
      >
      <div className="operations-sidebar__header">
        <div className="operations-sidebar__mark" aria-hidden="true">
          <Ship size={20} strokeWidth={1.8} />
        </div>
        {!collapsed && (
          <div className="operations-sidebar__heading">
            <span>Port disruption</span>
            <strong>Control room</strong>
          </div>
        )}
        <button
          className="operations-sidebar__collapse-button"
          type="button"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'}
          aria-expanded={!collapsed}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
        </button>
      </div>

      <nav className="operations-sidebar__navigation" aria-label="CASCADE sections">
        <ul className="operations-sidebar__navigation-list" data-tour="nav-list">
          {NAVIGATION_ITEMS.map((item) => {
            const Icon = item.icon
            const active = currentPage === item.id

            return (
              <li key={item.id} className="operations-sidebar__navigation-item">
                <button
                  className={`operations-sidebar__navigation-button${
                    active ? ' operations-sidebar__navigation-button--active' : ''
                  }`}
                  type="button"
                  data-tour={`nav-${item.id}`}
                  onClick={() => {
                    onNavigate(item.id)
                    onCloseMobile?.()
                  }}
                  aria-current={active ? 'page' : undefined}
                  aria-label={collapsed ? item.label : undefined}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                  {!collapsed && <span>{item.label}</span>}
                  {item.id === 'replay' && replayActive && (
                    <span className="operations-sidebar__replay-dot" aria-label="Replay active">
                      {!collapsed && 'LIVE'}
                    </span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      <footer className="operations-sidebar__footer">
        {replayActive && (
          <div className="operations-sidebar__replay-status" role="status">
            <History size={15} aria-hidden="true" />
            {!collapsed && <span>DEMO REPLAY</span>}
          </div>
        )}
        <div className="operations-sidebar__demo-badge">DEMO ENVIRONMENT</div>
        <strong className="operations-sidebar__brand">CASCADE</strong>
        {!collapsed && (
          <span className="operations-sidebar__environment">Synthetic Port Environment</span>
        )}
      </footer>
      </aside>
    </>
  )
}
