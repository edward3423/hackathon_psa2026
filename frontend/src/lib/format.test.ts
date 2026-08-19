import { describe, expect, it } from 'vitest'

import {
  DISPLAY_TIME_ZONE_LABEL,
  formatDateTime,
  formatTime,
  humanizeOperationalText,
} from './format'

describe('operator-facing time formatting', () => {
  it('renders structured timestamps in GMT+8', () => {
    expect(DISPLAY_TIME_ZONE_LABEL).toBe('GMT+8')
    expect(formatTime('2026-09-13T18:00:01Z')).toBe('02:00:01')
    expect(formatDateTime('2026-09-13T18:00:00Z')).toBe('14 Sept, 02:00 GMT+8')
  })

  it('converts ISO timestamps embedded in backend prose', () => {
    expect(
      humanizeOperationalText('Shortage starts 2026-09-15T05:00:00+00:00 in block YB1.'),
    ).toBe('Shortage starts 15 Sept, 13:00 GMT+8 in block YB1.')
  })

  it('humanizes plan and tool identifiers', () => {
    expect(humanizeOperationalText('AGGRESSIVE_RUSH_REJECTED by evaluate_plan')).toBe(
      'Aggressive Rush rejected by evaluate plan',
    )
    expect(humanizeOperationalText('Revise the rejected OPTIMIZED_HYBRID proposal.')).toBe(
      'Revise the rejected Optimized Hybrid proposal.',
    )
  })
})
