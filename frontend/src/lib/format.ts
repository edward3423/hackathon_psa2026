const DISPLAY_TIME_ZONE = 'Asia/Singapore'
export const DISPLAY_TIME_ZONE_LABEL = 'GMT+8'

export function formatTime(timestamp: string): string {
  return new Intl.DateTimeFormat('en-SG', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: DISPLAY_TIME_ZONE,
  }).format(new Date(timestamp))
}

export function formatDateTime(timestamp: string): string {
  return `${new Intl.DateTimeFormat('en-SG', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: DISPLAY_TIME_ZONE,
  }).format(new Date(timestamp))} ${DISPLAY_TIME_ZONE_LABEL}`
}

export function formatElapsed(ms: number | null | undefined): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

export function formatMoney(amount: number): string {
  return new Intl.NumberFormat('en-SG', {
    style: 'currency',
    currency: 'SGD',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function spaced(value: string): string {
  return value.replaceAll('_', ' ')
}

const ISO_TIMESTAMP =
  /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})\b/g

const OPERATIONAL_TERMS: ReadonlyArray<readonly [RegExp, string]> = [
  [/AGGRESSIVE_RUSH_REJECTED/g, 'Aggressive Rush rejected'],
  [/AGGRESSIVE_RUSH/g, 'Aggressive Rush'],
  [/STANDARD_REBOOK/g, 'Standard Rebook'],
  [/OPTIMIZED_HYBRID/g, 'Optimized Hybrid'],
  [/PHARMA_REEFER/g, 'refrigerated medicine'],
  [/TIME_CRITICAL_MANUFACTURING/g, 'time-critical manufacturing cargo'],
  [/GENERAL_DRY/g, 'standard dry cargo'],
  [/TERMINAL_WORK_ORDER/g, 'terminal work order'],
  [/REEFER_CHECK/g, 'refrigerated-container check'],
  [/CARRIER_NOTICE/g, 'carrier notice'],
  [/TIMEOUT_CACHED_FALLBACK/g, 'cached result after timeout'],
  [/pharma reefers/gi, 'refrigerated medicine containers'],
  [/pharmaceutical reefers/gi, 'refrigerated medicine containers'],
  [/analyse_connections/g, 'analyze connections'],
  [/simulate_yard/g, 'simulate yard'],
  [/evaluate_plan/g, 'evaluate plan'],
  [/\bRUSH\b/g, 'rush'],
  [/\bREBOOK\b/g, 'rebook'],
]

/** Convert backend-authored operational prose into operator-facing text. */
export function humanizeOperationalText(value: string): string {
  const withDates = value.replace(ISO_TIMESTAMP, (timestamp) => formatDateTime(timestamp))
  const readable = OPERATIONAL_TERMS.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    withDates,
  )
  return readable.length > 0 ? readable[0].toUpperCase() + readable.slice(1) : readable
}

/** A count and its noun, agreeing: "1 plug", "3 plugs". */
export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString()} ${Math.abs(count) === 1 ? singular : plural}`
}
