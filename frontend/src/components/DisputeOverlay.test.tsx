import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Dispute } from '../api/types'
import { DisputeOverlay } from './DisputeOverlay'

const dispute: Dispute = {
  dispute_id: 'disp-1',
  question: 'Which constraint governs refrigerated containers?',
  positions: [
    {
      agent: 'Impact Agent',
      position: 'Rush all threatened pharmaceutical reefers.',
      evidence: ['Protect the medicine cargo.'],
    },
    {
      agent: 'Yard Agent',
      position: 'Stay within physical reefer plug capacity.',
      evidence: ['Shortage starts 2026-09-15T05:00:00+00:00 in block YB1.'],
    },
  ],
  confirmed_constraint: null,
  resolved_by_human: false,
}

describe('DisputeOverlay', () => {
  it('offers one physical-capacity choice and formats evidence in GMT+8', async () => {
    const onResolve = vi.fn().mockResolvedValue(undefined)
    render(<DisputeOverlay dispute={dispute} openEvent={null} onResolve={onResolve} />)

    const dialog = screen.getByRole('dialog')
    expect(
      within(dialog).queryByRole('button', { name: 'Stay within physical reefer plug capacity.' }),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Respect physical reefer plug capacity' }),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Shortage starts 15 Sept, 13:00 GMT+8 in block YB1.')).toBeVisible()

    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Respect physical reefer plug capacity' }),
    )
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm constraint' }))
    expect(onResolve).toHaveBeenCalledWith('disp-1', 'Respect physical reefer plug capacity')
  })
})
