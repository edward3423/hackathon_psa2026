import { useEffect, useMemo, useState } from 'react'
import type { DeckProps, PickingInfo } from '@deck.gl/core'
import { GeoJsonLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { MapboxOverlay } from '@deck.gl/mapbox'
import { DeckGL } from '@deck.gl/react'
import type { FeatureCollection } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import { Map as MapboxMap, useControl } from 'react-map-gl/mapbox'
import countries from 'world-atlas/countries-110m.json'
import 'mapbox-gl/dist/mapbox-gl.css'

import { eventsUrl, getAisStatus, type AisPosition } from '../api/client'

type Coordinate = [number, number]

interface PlannedVessel {
  id: string
  name: string
  path: Coordinate[]
  speedKnots: number
  plan: string
  color: [number, number, number]
}

interface VesselMarker {
  id: string
  name: string
  position: Coordinate
  speedKnots: number | null
  detail: string
  live: boolean
  color?: [number, number, number]
}

interface TooltipState extends VesselMarker {
  x: number
  y: number
}

interface DeckVesselMapProps {
  cursor: number
  eventCount: number
}

const MAX_LIVE_VESSELS = 400
const MAPBOX_LOAD_TIMEOUT_MS = 4_000
const INITIAL_VIEW_STATE = { longitude: 65, latitude: 4, zoom: 1.15, pitch: 0, bearing: 0 }
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN as string | undefined

const PLANNED_VESSELS: PlannedVessel[] = [
  {
    id: 'atlas-star',
    name: 'MV ATLAS STAR',
    path: [[33.2, 28.6], [42.5, 12.6], [18.1, -34.6], [55.2, -20.2], [80.2, 5.2], [103.8, 1.25]],
    speedKnots: 16.2,
    plan: 'Cape reroute to Singapore',
    color: [244, 185, 66],
  },
  {
    id: 'pacific-link',
    name: 'MV PACIFIC LINK',
    path: [[139.7, 35.4], [128.1, 25.3], [121.3, 14.4], [112.1, 4.8], [103.8, 1.25]],
    speedKnots: 14.8,
    plan: 'Protected onward connection',
    color: [89, 204, 214],
  },
  {
    id: 'borneo-feeder',
    name: 'MV BORNEO FEEDER',
    path: [[119.4, -5.1], [114.1, -2.5], [108.2, 0.2], [103.8, 1.25]],
    speedKnots: 11.6,
    plan: 'Feeder arrival re-sequenced',
    color: [239, 124, 105],
  },
]

const FALLBACK_LAND = (() => {
  const topology = countries as unknown as Topology<{ countries: GeometryCollection }>
  return feature(topology, topology.objects.countries) as FeatureCollection
})()

function interpolatePath(path: Coordinate[], progress: number): Coordinate {
  const scaled = Math.min(Math.max(progress, 0), 1) * (path.length - 1)
  const segment = Math.min(Math.floor(scaled), path.length - 2)
  const fraction = scaled - segment
  const start = path[segment]
  const end = path[segment + 1]
  return [
    start[0] + (end[0] - start[0]) * fraction,
    start[1] + (end[1] - start[1]) * fraction,
  ]
}

function DeckOverlay(props: DeckProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay({ ...props, interleaved: false }))
  overlay.setProps(props)
  return null
}

export function DeckVesselMap({ cursor, eventCount }: DeckVesselMapProps) {
  const [aisState, setAisState] = useState<'connecting' | 'live' | 'offline'>('connecting')
  const [livePositions, setLivePositions] = useState<Map<string, AisPosition>>(new Map())
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const [mapboxState, setMapboxState] = useState<'loading' | 'ready' | 'fallback'>(
    MAPBOX_TOKEN ? 'loading' : 'fallback',
  )
  const progress = eventCount > 1 ? cursor / (eventCount - 1) : 0

  useEffect(() => {
    if (mapboxState !== 'loading') return
    const timeout = window.setTimeout(() => setMapboxState('fallback'), MAPBOX_LOAD_TIMEOUT_MS)
    return () => window.clearTimeout(timeout)
  }, [mapboxState])

  useEffect(() => {
    let source: EventSource | undefined
    let cancelled = false
    void getAisStatus()
      .then((status) => {
        if (cancelled) return
        if (!status.available) {
          setAisState('offline')
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
        source.addEventListener('provider_error', () => setAisState('offline'))
        source.onerror = () => setAisState('offline')
      })
      .catch(() => setAisState('offline'))
    return () => {
      cancelled = true
      source?.close()
    }
  }, [])

  const plannedMarkers = useMemo<VesselMarker[]>(
    () =>
      PLANNED_VESSELS.map((vessel, index) => ({
        id: vessel.id,
        name: vessel.name,
        position: interpolatePath(vessel.path, Math.min(1, progress * (1 + index * 0.08))),
        speedKnots: vessel.speedKnots,
        detail: vessel.plan,
        live: false,
        color: vessel.color,
      })),
    [progress],
  )
  const liveMarkers = useMemo<VesselMarker[]>(
    () =>
      [...livePositions.values()].map((vessel) => ({
        id: vessel.mmsi,
        name: vessel.name,
        position: [vessel.longitude, vessel.latitude],
        speedKnots: vessel.speed_knots,
        detail: `MMSI ${vessel.mmsi}`,
        live: true,
      })),
    [livePositions],
  )

  const onHover = ({ object, x, y }: PickingInfo<VesselMarker>) => {
    setTooltip(object ? { ...object, x, y } : null)
  }
  const vesselLayers = [
    new PathLayer<PlannedVessel>({
      id: 'optimized-routes',
      data: PLANNED_VESSELS,
      getPath: (vessel) => vessel.path,
      getColor: (vessel) => [...vessel.color, 245],
      getWidth: 5,
      widthUnits: 'pixels',
      jointRounded: true,
      capRounded: true,
    }),
    new ScatterplotLayer<VesselMarker>({
      id: 'planned-vessel-halos',
      data: plannedMarkers,
      getPosition: (vessel) => vessel.position,
      getRadius: 17,
      radiusUnits: 'pixels',
      getFillColor: [244, 185, 66, 38],
      getLineColor: [255, 224, 151, 180],
      lineWidthMinPixels: 1,
      stroked: true,
    }),
    new ScatterplotLayer<VesselMarker>({
      id: 'planned-vessels',
      data: plannedMarkers,
      getPosition: (vessel) => vessel.position,
      getRadius: 10,
      radiusUnits: 'pixels',
      getFillColor: (vessel) => [...(vessel.color ?? [244, 185, 66]), 255],
      getLineColor: [247, 250, 248, 255],
      lineWidthMinPixels: 3,
      stroked: true,
      pickable: true,
      onHover,
    }),
    new TextLayer<VesselMarker>({
      id: 'planned-vessel-labels',
      data: plannedMarkers,
      getPosition: (vessel) => vessel.position,
      getText: (vessel) => vessel.name.replace(/^MV /, ''),
      getColor: [247, 250, 248, 255],
      getSize: 12,
      getPixelOffset: [0, -22],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'bottom',
      fontWeight: 700,
      fontSettings: { sdf: true, fontSize: 64, buffer: 4 },
      outlineColor: [4, 11, 16, 255],
      outlineWidth: 3,
      billboard: true,
      pickable: false,
    }),
    new ScatterplotLayer<VesselMarker>({
      id: 'live-ais-vessels',
      data: liveMarkers,
      getPosition: (vessel) => vessel.position,
      getRadius: 4,
      radiusUnits: 'pixels',
      getFillColor: [91, 190, 199, 230],
      pickable: true,
      onHover,
    }),
  ]
  const fallbackLayers = [
    new GeoJsonLayer({
      id: 'fallback-world-land',
      data: FALLBACK_LAND,
      filled: true,
      stroked: true,
      getFillColor: [35, 52, 58, 255],
      getLineColor: [72, 90, 95, 170],
      lineWidthMinPixels: 0.5,
      wrapLongitude: true,
      pickable: false,
    }),
    ...vesselLayers,
  ]

  return (
    <section
      className="deck-vessel-map"
      aria-label="World vessel simulation"
      data-route-progress={progress.toFixed(3)}
    >
      <header className="deck-vessel-map__header">
        <div>
          <h3>Global vessel optimization</h3>
          <p>DECK.GL SIMULATION</p>
        </div>
        <div className="deck-vessel-map__legend" aria-label="Map layers">
          <span aria-label="3 built-in simulated ships and their routes">
            <i className="deck-vessel-map__key deck-vessel-map__key--planned" />3 SIMULATED SHIPS + ROUTES
          </span>
          <span><i className="deck-vessel-map__key deck-vessel-map__key--live" />AISSTREAM {aisState.toUpperCase()}</span>
          <span>
            {mapboxState === 'ready'
              ? 'MAPBOX ACTIVE'
              : mapboxState === 'loading'
                ? 'MAPBOX LOADING'
                : 'LOCAL MAP FALLBACK'}
          </span>
        </div>
      </header>

      <div className="deck-vessel-map__canvas">
        {MAPBOX_TOKEN && mapboxState !== 'fallback' ? (
          <MapboxMap
            initialViewState={INITIAL_VIEW_STATE}
            mapboxAccessToken={MAPBOX_TOKEN}
            mapStyle="mapbox://styles/mapbox/dark-v11"
            projection={{ name: 'mercator' }}
            attributionControl
            onLoad={() => setMapboxState('ready')}
            onError={() => setMapboxState('fallback')}
          >
            <DeckOverlay layers={vesselLayers} />
          </MapboxMap>
        ) : (
          <DeckGL
            initialViewState={INITIAL_VIEW_STATE}
            controller
            layers={fallbackLayers}
            getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
          />
        )}

        {tooltip && (
          <div
            className="deck-vessel-map__tooltip"
            data-live={tooltip.live}
            role="tooltip"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            <strong>{tooltip.name}</strong>
            <span>{tooltip.live ? 'Live AIS position' : 'Simulated optimized position'}</span>
            <span>{tooltip.detail} · {tooltip.speedKnots?.toFixed(1) ?? 'Unknown'} kn</span>
          </div>
        )}
      </div>

      <footer className="deck-vessel-map__notice">
        Bright labeled circles and lines are the three simulated ships and their optimized routes.
        Live AIS (Automatic Identification System) dots appear only when the provider is connected.
      </footer>
    </section>
  )
}
