import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import type { PickingInfo } from '@deck.gl/core'
import { GeoJsonLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import { DeckGL } from '@deck.gl/react'
import type { FeatureCollection } from 'geojson'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import countries from 'world-atlas/countries-110m.json'

import { eventsUrl, getAisStatus, type AisPosition } from '../api/client'
import { PLANNED_VESSELS, type Coordinate, type PlannedVessel } from '../data/vesselRoutes'

export interface VesselMarker {
  id: string
  name: string
  position: Coordinate
  speedKnots: number | null
  detail: string
  live: boolean
  color?: [number, number, number]
  labelOffset?: [number, number]
}

export interface TooltipState extends VesselMarker {
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
const CLUSTERED_LABEL_OFFSETS: Record<string, [number, number]> = {
  'atlas-star': [-68, -22],
  'pacific-link': [68, -22],
  'borneo-feeder': [0, 34],
}

const MapboxVesselMap = lazy(() =>
  import('./MapboxVesselMap').then((module) => ({ default: module.MapboxVesselMap })),
)

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
        labelOffset:
          progress >= 0.8 ? (CLUSTERED_LABEL_OFFSETS[vessel.id] ?? [0, -22]) : [0, -22],
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
        detail: `Maritime Mobile Service Identity (MMSI) ${vessel.mmsi}`,
        live: true,
      })),
    [livePositions],
  )
  const liveGeoJson = useMemo<FeatureCollection>(
    () => ({
      type: 'FeatureCollection',
      features: liveMarkers.map((vessel) => ({
        type: 'Feature',
        properties: {
          id: vessel.id,
          name: vessel.name,
          speedKnots: vessel.speedKnots,
          detail: vessel.detail,
        },
        geometry: { type: 'Point', coordinates: vessel.position },
      })),
    }),
    [liveMarkers],
  )

  const onHover = ({ object, x, y }: PickingInfo<VesselMarker>) => {
    setTooltip(object ? { ...object, x, y } : null)
  }
  // Paper and ink on the map too. Live AIS traffic is ink; the planned routes
  // and the vessels on them are the accent, because the route is the thing the
  // page is asking you to look at.
  const liveVesselLayer = new ScatterplotLayer<VesselMarker>({
    id: 'live-ais-vessels',
    data: liveMarkers,
    getPosition: (vessel) => vessel.position,
    getRadius: 5,
    radiusUnits: 'pixels',
    getFillColor: [17, 17, 17, 220],
    getLineColor: [255, 255, 255, 255],
    lineWidthMinPixels: 1,
    stroked: true,
    pickable: true,
    onHover,
  })
  const vesselLayers = [
    /*
     * Two passes for one route: a white casing, then the line. Water is now
     * pale blue and the accent route is blue, so without the casing the two
     * would be separated by lightness alone. This is what every printed chart
     * does with a shipping lane, and it costs one layer.
     */
    new PathLayer<PlannedVessel>({
      id: 'optimized-routes-casing',
      data: PLANNED_VESSELS,
      getPath: (vessel) => vessel.path,
      getColor: [255, 255, 255, 235],
      getWidth: 8,
      widthUnits: 'pixels',
      jointRounded: true,
      capRounded: true,
    }),
    new PathLayer<PlannedVessel>({
      id: 'optimized-routes',
      data: PLANNED_VESSELS,
      getPath: (vessel) => vessel.path,
      getColor: (vessel) => [...vessel.color, 245],
      getWidth: 4,
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
      getFillColor: [15, 59, 255, 30],
      getLineColor: [15, 59, 255, 130],
      lineWidthMinPixels: 1,
      stroked: true,
    }),
    new ScatterplotLayer<VesselMarker>({
      id: 'planned-vessels',
      data: plannedMarkers,
      getPosition: (vessel) => vessel.position,
      getRadius: 10,
      radiusUnits: 'pixels',
      getFillColor: (vessel) => [...(vessel.color ?? [15, 59, 255]), 255],
      getLineColor: [255, 255, 255, 255],
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
      getColor: [17, 17, 17, 255],
      getSize: 12,
      getPixelOffset: (vessel) => vessel.labelOffset ?? [0, -22],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'bottom',
      fontWeight: 700,
      fontSettings: { sdf: true, fontSize: 64, buffer: 4 },
      outlineColor: [255, 255, 255, 255],
      outlineWidth: 3,
      billboard: true,
      pickable: false,
    }),
    liveVesselLayer,
  ]
  const fallbackLayers = [
    new GeoJsonLayer({
      id: 'fallback-world-land',
      data: FALLBACK_LAND,
      filled: true,
      stroked: true,
      // --land / --land-edge. The canvas behind is --water, so the two
      // together read as coast without a single label.
      getFillColor: [211, 229, 196, 255],
      getLineColor: [157, 192, 127, 230],
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
            <i className="deck-vessel-map__key deck-vessel-map__key--planned" />
            3 SIMULATED SHIPS + ROUTES
          </span>
          <span role="status" aria-live="polite">
            {/* The accent means live. Filling this dot while the stream is
                offline contradicted the word beside it. */}
            <i
              className={`deck-vessel-map__key deck-vessel-map__key--live${
                aisState === 'live' ? ' is-live' : ''
              }`}
            />
            AISSTREAM {aisState.toUpperCase()}
          </span>
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
          <Suspense fallback={<div className="deck-vessel-map__loading">Loading Mapbox…</div>}>
            <MapboxVesselMap
              accessToken={MAPBOX_TOKEN}
              liveGeoJson={liveGeoJson}
              plannedMarkers={plannedMarkers}
              onReady={() => setMapboxState('ready')}
              onFallback={() => setMapboxState('fallback')}
              onTooltipChange={setTooltip}
            />
          </Suspense>
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
            <span>
              {tooltip.detail} · {tooltip.speedKnots?.toFixed(1) ?? 'Unknown'} knots
            </span>
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
