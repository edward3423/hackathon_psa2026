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

/*
 * Ten destinations and nothing else. The rail used to open with a two-line
 * heading and close with four stacked badges - a replay chip, DEMO ENVIRONMENT,
 * the wordmark, and "Synthetic Port Environment" - all of which the masthead or
 * the app footer already says once.
 */
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
          <span className="operations-sidebar__mark" aria-hidden="true">
            <Ship size={17} strokeWidth={1.8} />
          </span>
          <button
            className="operations-sidebar__collapse-button"
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'}
            aria-expanded={!collapsed}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <PanelLeftOpen size={17} aria-hidden="true" />
            ) : (
              <PanelLeftClose size={17} aria-hidden="true" />
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
                    /*
                     * The dot is decorative. Labelling it made the button's
                     * accessible name "Replay Replay active" for the whole of a
                     * replay - clumsy to hear, and it silently broke any
                     * name-based selector for this control. The state belongs in
                     * the description, and the masthead's DEMO REPLAY badge
                     * announces it once as a live status.
                     */
                    title={
                      item.id === 'replay' && replayActive
                        ? 'Replay active'
                        : collapsed
                          ? item.label
                          : undefined
                    }
                  >
                    <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
                    {!collapsed && <span>{item.label}</span>}
                    {item.id === 'replay' && replayActive && (
                      <span className="operations-sidebar__replay-dot" aria-hidden="true" />
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      </aside>
    </>
  )
}
