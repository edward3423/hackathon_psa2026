import type { FeatureCollection } from 'geojson'
import { Layer, Map as MapboxMap, Marker, Source } from 'react-map-gl/mapbox'
import 'mapbox-gl/dist/mapbox-gl.css'

import { PLANNED_VESSELS } from '../data/vesselRoutes'
import type { TooltipState, VesselMarker } from './DeckVesselMap'

interface MapboxVesselMapProps {
  accessToken: string
  liveGeoJson: FeatureCollection
  plannedMarkers: VesselMarker[]
  onReady: () => void
  onFallback: () => void
  onTooltipChange: (tooltip: TooltipState | null) => void
}

const INITIAL_VIEW_STATE = {
  longitude: 65,
  latitude: 4,
  zoom: 1.15,
  pitch: 0,
  bearing: 0,
}

export function MapboxVesselMap({
  accessToken,
  liveGeoJson,
  plannedMarkers,
  onReady,
  onFallback,
  onTooltipChange,
}: MapboxVesselMapProps) {
  return (
    <MapboxMap
      initialViewState={INITIAL_VIEW_STATE}
      mapboxAccessToken={accessToken}
      mapStyle="mapbox://styles/mapbox/dark-v11"
      projection={{ name: 'globe' }}
      attributionControl
      interactiveLayerIds={['live-ais-vessels-mapbox']}
      onLoad={onReady}
      onError={onFallback}
      onMouseMove={(event) => {
        const vessel = event.features?.[0]
        if (!vessel?.properties) {
          onTooltipChange(null)
          return
        }
        const speed = vessel.properties.speedKnots
        onTooltipChange({
          id: String(vessel.properties.id),
          name: String(vessel.properties.name),
          position: [event.lngLat.lng, event.lngLat.lat],
          speedKnots: typeof speed === 'number' ? speed : null,
          detail: String(vessel.properties.detail),
          live: true,
          x: event.point.x,
          y: event.point.y,
        })
      }}
      onMouseLeave={() => onTooltipChange(null)}
    >
      {PLANNED_VESSELS.map((vessel) => (
        <Source
          id={`simulated-route-${vessel.id}`}
          key={`route-${vessel.id}`}
          type="geojson"
          data={{
            type: 'Feature',
            properties: {},
            geometry: { type: 'LineString', coordinates: vessel.path },
          }}
        >
          <Layer
            id={`simulated-route-${vessel.id}`}
            type="line"
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{
              'line-color': `rgb(${vessel.color.join(', ')})`,
              'line-opacity': 0.95,
              'line-width': 4,
            }}
          />
        </Source>
      ))}
      {plannedMarkers.map((vessel) => (
        <Marker
          key={`marker-${vessel.id}`}
          longitude={vessel.position[0]}
          latitude={vessel.position[1]}
          anchor="center"
        >
          <div className="mapbox-simulated-vessel">
            <button
              type="button"
              aria-label={`${vessel.name}, simulated optimized position`}
              className="mapbox-simulated-vessel__marker"
            >
              <span
                className="mapbox-simulated-vessel__dot"
                style={{ backgroundColor: `rgb(${vessel.color?.join(', ')})` }}
              />
              <span
                className="mapbox-simulated-vessel__name"
                style={{
                  marginLeft: vessel.labelOffset?.[0] ?? 0,
                  bottom: 4 - (vessel.labelOffset?.[1] ?? -22),
                }}
              >
                {vessel.name.replace(/^MV /, '')}
              </span>
            </button>
            <span className="mapbox-simulated-vessel__tooltip" role="tooltip">
              <strong>{vessel.name}</strong>
              <span>{vessel.detail}</span>
              <span>{vessel.speedKnots?.toFixed(1)} knots</span>
            </span>
          </div>
        </Marker>
      ))}
      <Source id="live-ais-vessels" type="geojson" data={liveGeoJson}>
        <Layer
          id="live-ais-vessels-mapbox"
          type="circle"
          paint={{
            'circle-color': '#5bbec7',
            'circle-opacity': 0.9,
            'circle-radius': 5,
            'circle-stroke-color': '#e8fafb',
            'circle-stroke-width': 1,
          }}
        />
      </Source>
    </MapboxMap>
  )
}
