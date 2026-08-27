import { CHART_INK, CHART_SURFACE } from '../lib/chartTheme'

/**
 * The one pattern the bar series needs. Render once inside any chart
 * that uses `barFills`. 45 degrees and its 135-degree mirror only: horizontal or
 * vertical hatching reads as gridlines.
 */
export function ChartTextures() {
  return (
    <defs>
      <pattern
        id="ink-hatch-45"
        width="6"
        height="6"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(45)"
      >
        <rect width="6" height="6" fill={CHART_SURFACE} />
        <line x1="0" y1="0" x2="0" y2="6" stroke={CHART_INK} strokeWidth="3" />
      </pattern>

      <pattern
        id="ink-hatch-135"
        width="6"
        height="6"
        patternUnits="userSpaceOnUse"
        patternTransform="rotate(135)"
      >
        <rect width="6" height="6" fill={CHART_SURFACE} />
        <line x1="0" y1="0" x2="0" y2="6" stroke={CHART_INK} strokeWidth="3" />
      </pattern>
    </defs>
  )
}
