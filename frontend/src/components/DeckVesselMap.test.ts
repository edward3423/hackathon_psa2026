import { geoContains } from 'd3-geo'
import { describe, expect, it } from 'vitest'
import { feature } from 'topojson-client'
import type { FeatureCollection } from 'geojson'
import type { GeometryCollection, Topology } from 'topojson-specification'
import countries from 'world-atlas/countries-110m.json'

import { PLANNED_VESSELS } from '../data/vesselRoutes'

const topology = countries as unknown as Topology<{ countries: GeometryCollection }>
const land = feature(topology, topology.objects.countries) as FeatureCollection

describe('simulated vessel routes', () => {
  it('keeps the Atlas Star Cape diversion over water', () => {
    const route = PLANNED_VESSELS.find((vessel) => vessel.id === 'atlas-star')?.path
    expect(route).toBeDefined()

    // The final segment enters Singapore port, so only the open-water journey is checked.
    for (let segment = 0; segment < (route?.length ?? 0) - 2; segment += 1) {
      const start = route?.[segment]
      const end = route?.[segment + 1]
      if (!start || !end) continue

      for (let sample = 1; sample < 20; sample += 1) {
        const fraction = sample / 20
        const point: [number, number] = [
          start[0] + (end[0] - start[0]) * fraction,
          start[1] + (end[1] - start[1]) * fraction,
        ]
        expect(geoContains(land, point), `${point.join(', ')} is on land`).toBe(false)
      }
    }
  })
})
