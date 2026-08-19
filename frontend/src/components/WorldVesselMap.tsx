import { useEffect, useMemo, useState } from 'react'
import { geoGraticule10, geoInterpolate, geoNaturalEarth1, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import type { FeatureCollection } from 'geojson'
import type { GeometryCollection, Topology } from 'topojson-specification'
import countries from 'world-atlas/countries-110m.json'

import { eventsUrl, getAisStatus, type AisPosition } from '../api/client'

const MAP_WIDTH = 1000
const MAP_HEIGHT = 460
const MAX_LIVE_VESSELS = 350

type Coordinate = [number, number]

interface ReplayVessel {
  name: string
  route: Coordinate[]
  speedKnots: number
  plan: string
}

const REPLAY_VESSELS: ReplayVessel[] = [
  {
    name: 'MV ATLAS STAR',
    route: [
      [33.2, 28.6],
      [42.5, 12.6],
      [18.1, -34.6],
      [55.2, -20.2],
      [80.2, 5.2],
      [103.8, 1.25],
    ],
    speedKnots: 16.2,
    plan: 'Cape reroute to Singapore',
  },
  {
    name: 'MV PACIFIC LINK',
    route: [
      [139.7, 35.4],
      [128.1, 25.3],
      [121.3, 14.4],
      [112.1, 4.8],
      [103.8, 1.25],
    ],
    speedKnots: 14.8,
    plan: 'Protected onward connection',
  },
  {
    name: 'MV BORNEO FEEDER',
    route: [
      [119.4, -5.1],
      [114.1, -2.5],
      [108.2, 0.2],
      [103.8, 1.25],
    ],
    speedKnots: 11.6,
    plan: 'Feeder arrival re-sequenced',
  },
]

interface WorldVesselMapProps {
  cursor: number
  eventCount: number
  scenarioTitle: string
}

interface HoveredVessel {
  name: string
  detail: string
  speed: number | null
  position: Coordinate
  mapPoint: [number, number]
  live: boolean
}

function routePosition(route: Coordinate[], progress: number): Coordinate {
  const scaled = Math.min(Math.max(progress, 0), 1) * (route.length - 1)
  const segment = Math.min(Math.floor(scaled), route.length - 2)
  return geoInterpolate(route[segment], route[segment + 1])(scaled - segment) as Coordinate
}

function formatCoordinate([longitude, latitude]: Coordinate): string {
  const lat = `${Math.abs(latitude).toFixed(2)}°${latitude >= 0 ? 'N' : 'S'}`
  const lon = `${Math.abs(longitude).toFixed(2)}°${longitude >= 0 ? 'E' : 'W'}`
  return `${lat}, ${lon}`
}

export function WorldVesselMap({ cursor, eventCount, scenarioTitle }: WorldVesselMapProps) {
  const [livePositions, setLivePositions] = useState<Map<string, AisPosition>>(new Map())
  const [aisState, setAisState] = useState<'checking' | 'live' | 'unavailable' | 'error'>(
    'checking',
  )
  const [hovered, setHovered] = useState<HoveredVessel | null>(null)

  const projection = useMemo(
    () => geoNaturalEarth1().fitExtent([[18, 18], [MAP_WIDTH - 18, MAP_HEIGHT - 18]], { type: 'Sphere' }),
    [],
  )
  const path = useMemo(() => geoPath(projection), [projection])
  const land = useMemo(() => {
    const topology = countries as unknown as Topology<{ countries: GeometryCollection }>
    return feature(topology, topology.objects.countries) as FeatureCollection
  }, [])

  useEffect(() => {
    let source: EventSource | undefined
    let cancelled = false

    void getAisStatus()
      .then((status) => {
        if (cancelled) return
        if (!status.available) {
          setAisState('unavailable')
          return
        }
        source = new EventSource(eventsUrl('/api/ais/stream'))
        source.addEventListener('position', (event) => {
          const position = JSON.parse((event as MessageEvent<string>).data) as AisPosition
          setAisState('live')
          setLivePositions((current) => {
            const next = new Map(current)
            next.delete(position.mmsi)
            next.set(position.mmsi, position)
            while (next.size > MAX_LIVE_VESSELS) {
              const oldest = next.keys().next().value as string | undefined
              if (oldest === undefined) break
              next.delete(oldest)
            }
            return next
          })
        })
        source.addEventListener('provider_error', () => setAisState('error'))
        source.onerror = () => setAisState('error')
      })
      .catch(() => setAisState('unavailable'))

    return () => {
      cancelled = true
      source?.close()
    }
  }, [])

  const progress = eventCount > 1 ? cursor / (eventCount - 1) : 0
  const replayPositions = REPLAY_VESSELS.map((vessel, index) => ({
    ...vessel,
    position: routePosition(vessel.route, Math.min(1, progress * (1 + index * 0.08))),
  }))
  const liveLabel =
    aisState === 'live'
      ? `LIVE AIS · ${livePositions.size} SHIPS`
      : aisState === 'checking'
        ? 'Checking live AIS'
        : aisState === 'error'
          ? 'Live AIS disconnected'
          : 'Live AIS unavailable'

  return (
    <section className="vessel-map" aria-label="World vessel map">
      <header className="vessel-map__header">
        <div>
          <h3>Global vessel movement</h3>
          <p>{scenarioTitle} optimized route replay</p>
        </div>
        <div className="vessel-map__legend" aria-label="Map layers">
          <span><i className="vessel-map__key vessel-map__key--planned" />SIMULATED ROUTES</span>
          <span><i className="vessel-map__key vessel-map__key--live" />{liveLabel}</span>
        </div>
      </header>

      <div className="vessel-map__canvas">
        <svg viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`} role="img" aria-label="World map with vessel positions">
          <path className="vessel-map__ocean" d={path({ type: 'Sphere' }) ?? undefined} />
          <path className="vessel-map__graticule" d={path(geoGraticule10()) ?? undefined} />
          <path className="vessel-map__land" d={path(land) ?? undefined} />

          {REPLAY_VESSELS.map((vessel) => (
            <path
              key={`${vessel.name}-route`}
              className="vessel-map__route"
              d={path({ type: 'LineString', coordinates: vessel.route }) ?? undefined}
            />
          ))}

          {replayPositions.map((vessel) => {
            const point = projection(vessel.position)
            if (!point) return null
            return (
              <g
                key={vessel.name}
                data-replay-vessel
                className="vessel-map__marker vessel-map__marker--planned"
                transform={`translate(${point[0].toFixed(2)} ${point[1].toFixed(2)})`}
                tabIndex={0}
                aria-label={`${vessel.name}, planned position`}
                onMouseEnter={() =>
                  setHovered({
                    name: vessel.name,
                    detail: `Planned position · ${vessel.plan}`,
                    speed: vessel.speedKnots,
                    position: vessel.position,
                    mapPoint: point,
                    live: false,
                  })
                }
                onMouseLeave={() => setHovered(null)}
                onFocus={() =>
                  setHovered({
                    name: vessel.name,
                    detail: `Planned position · ${vessel.plan}`,
                    speed: vessel.speedKnots,
                    position: vessel.position,
                    mapPoint: point,
                    live: false,
                  })
                }
                onBlur={() => setHovered(null)}
              >
                <circle r="7" />
                <circle className="vessel-map__marker-ring" r="12" />
              </g>
            )
          })}

          {[...livePositions.values()].map((vessel) => {
            const coordinate: Coordinate = [vessel.longitude, vessel.latitude]
            const point = projection(coordinate)
            if (!point) return null
            return (
              <circle
                key={vessel.mmsi}
                className="vessel-map__live-vessel"
                cx={point[0]}
                cy={point[1]}
                r="3"
                tabIndex={0}
                aria-label={`${vessel.name}, live AIS position`}
                onMouseEnter={() =>
                  setHovered({
                    name: vessel.name,
                    detail: `Live AIS · MMSI ${vessel.mmsi}`,
                    speed: vessel.speed_knots,
                    position: coordinate,
                    mapPoint: point,
                    live: true,
                  })
                }
                onMouseLeave={() => setHovered(null)}
              />
            )
          })}
        </svg>

        {hovered && (
          <div
            className="vessel-map__tooltip"
            role="tooltip"
            data-live={hovered.live ? 'true' : 'false'}
            style={{
              left: `${(hovered.mapPoint[0] / MAP_WIDTH) * 100}%`,
              top: `${(hovered.mapPoint[1] / MAP_HEIGHT) * 100}%`,
            }}
          >
            <strong>{hovered.name}</strong>
            <span>{hovered.detail}</span>
            <span>{hovered.speed?.toFixed(1) ?? 'Unknown'} kn · {formatCoordinate(hovered.position)}</span>
          </div>
        )}
      </div>

      <footer className="vessel-map__notice">
        Scenario ships are simulated. AIS (Automatic Identification System) dots are real provider
        reports when connected and may be delayed by coverage.
      </footer>
    </section>
  )
}
