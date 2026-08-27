/**
 * One monochrome chart palette, shared by every chart in the app.
 *
 * The page is black, white and a single blue, so a chart cannot tell two series
 * apart by hue. It tells them apart the way print does: fill, texture and dash.
 * Values mirror the CSS tokens in styles.css - recharts takes strings, not
 * custom properties, so this file is where the two meet.
 */

export const CHART_INK = '#111111'
export const CHART_INK_SOFT = '#3d3d3d'
export const CHART_RULE = '#a3a094'
export const CHART_SURFACE = '#ffffff'
export const CHART_ACCENT = '#0f3bff'

/** Hairline, solid. Recharts dashes the grid by default, and a dashed grid
 *  competes with dashed data. */
export const gridProps = { stroke: CHART_RULE, strokeDasharray: '0' } as const

export const axisProps = {
  stroke: CHART_INK_SOFT,
  fontSize: 12,
  tick: { fill: CHART_INK_SOFT },
} as const

/** Square, ink-edged, opaque. Same object as the panels around it. */
export const tooltipStyle = {
  background: CHART_SURFACE,
  border: `2px solid ${CHART_INK}`,
  borderRadius: 0,
  color: CHART_INK,
  fontSize: 12,
} as const

export const legendStyle = { fontSize: 12, color: CHART_INK_SOFT } as const

/**
 * Recharts paints each legend label in its series' fill, which turns the hollow
 * series' label white on white. Labels wear an ink token; the swatch beside them
 * carries the identity.
 */
export function legendLabel(value: unknown) {
  return <span style={{ color: CHART_INK_SOFT }}>{String(value)}</span>
}

/**
 * Bar identity: solid, then 45-degree hatch, then outline-only. Ordered loudest
 * first so the series that matters most reads first, and never cycled - a fourth
 * bar series would need a fourth channel, not a repeat.
 *
 * Only the hatch needs an SVG pattern. Solid and hollow are a plain fill and a
 * stroke: an objectBoundingBox pattern also needs patternContentUnits to match,
 * and without it the tile collapses to one pixel and the bar disappears.
 */
export const barSeries = [
  { fill: CHART_INK },
  { fill: 'url(#ink-hatch-45)', stroke: CHART_INK, strokeWidth: 1 },
  { fill: CHART_SURFACE, stroke: CHART_INK, strokeWidth: 2 },
] as const

/** Line identity: dash pattern, with the accent reserved for the live series. */
export const lineStyles = [
  { stroke: CHART_INK, strokeWidth: 2, strokeDasharray: undefined },
  { stroke: CHART_INK_SOFT, strokeWidth: 2, strokeDasharray: '7 4' },
  { stroke: CHART_INK_SOFT, strokeWidth: 2, strokeDasharray: '2 3' },
  { stroke: CHART_ACCENT, strokeWidth: 2.5, strokeDasharray: undefined },
] as const
