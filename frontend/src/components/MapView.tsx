import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo } from 'react'
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Popup,
  TileLayer,
  useMap,
} from 'react-leaflet'
import type { Feature, FeatureCollection, Point } from 'geojson'
import type { MapPayload } from '../api/types'
import { TECH_COLORS, rampFor, techColor } from '../lib/colors'
import { useTheme } from '../lib/theme'
import { classOf, quantileBreaks } from '../lib/quantiles'

const FREIBURG: [number, number] = [47.995, 7.85]
const fmt = (v: number) => v.toLocaleString('en-US', { maximumFractionDigits: 3 })

/** Leaflet measures its container once; tell it whenever the container is resized (panel dragging). */
function ResizeSync() {
  const map = useMap()
  useEffect(() => {
    const el = map.getContainer()
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(el)
    return () => observer.disconnect()
  }, [map])
  return null
}

/** Zoom to whatever was just drawn. useMap() gives access to the Leaflet map instance. */
function FitBounds({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap()
  useEffect(() => {
    if (bounds?.isValid()) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 })
  }, [bounds, map])
  return null
}

function boundsOf(payloads: MapPayload[]): L.LatLngBounds | null {
  let all: L.LatLngBounds | null = null
  const extend = (b: L.LatLngBounds) =>
    (all = all ? all.extend(b) : L.latLngBounds(b.getSouthWest(), b.getNorthEast()))
  for (const p of payloads) {
    if (p.kind === 'map_points' && p.circle) {
      extend(L.latLng(p.circle.lat, p.circle.lon).toBounds(p.circle.radius_km * 2000))
    } else if (p.geojson.features.length > 0) {
      const b = L.geoJSON(p.geojson).getBounds()
      if (b.isValid()) extend(b)
    }
  }
  return all
}

function Choropleth({
  payload,
  onPick,
}: {
  payload: Extract<MapPayload, { kind: 'map_choropleth' }>
  onPick: (name: string) => void
}) {
  const { theme } = useTheme()
  const ramp = rampFor(theme)
  const dark = theme === 'dark'
  const breaks = useMemo(
    () =>
      quantileBreaks(
        payload.geojson.features
          .map((f) => f.properties?.value)
          .filter((v): v is number => typeof v === 'number'),
      ),
    [payload],
  )
  return (
    <GeoJSON
      key={`${payload.title}-${payload.geojson.features.length}-${theme}`} // re-create the layer when the theme changes
      data={payload.geojson as FeatureCollection}
      style={(f) => {
        const v = f?.properties?.value
        return {
          weight: 0.6,
          color: dark ? '#1d1d1b' : '#64748b',
          fillOpacity: 0.8,
          fillColor:
            typeof v === 'number' ? ramp[classOf(v, breaks)] : dark ? '#3b3b38' : '#e5e7eb',
        }
      }}
      onEachFeature={(f, layer) => {
        const v = f.properties?.value
        layer.bindTooltip(
          `${f.properties?.name}: ${typeof v === 'number' ? `${fmt(v)} ${payload.unit}` : 'n/a'}`,
          { sticky: true },
        )
        layer.on('click', () => onPick(String(f.properties?.name)))
      }}
    />
  )
}

function ChoroplethLegend({
  payload,
}: {
  payload: Extract<MapPayload, { kind: 'map_choropleth' }>
}) {
  const { theme } = useTheme()
  const vals = payload.geojson.features
    .map((f) => f.properties?.value)
    .filter((v): v is number => typeof v === 'number')
  const breaks = quantileBreaks(vals)
  const lo = [Math.min(...vals), ...breaks]
  const hi = [...breaks, Math.max(...vals)]
  return (
    <div className="absolute bottom-6 left-3 z-[1000] rounded-md bg-card/95 text-ink p-2 text-xs shadow">
      <div className="mb-1 font-semibold">{payload.unit}</div>
      {lo.map((l, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-4 border border-line"
            style={{ background: rampFor(theme)[i] }}
          />
          {fmt(l)} – {fmt(hi[i])}
        </div>
      ))}
    </div>
  )
}

function PointsLayer({ payload }: { payload: Extract<MapPayload, { kind: 'map_points' }> }) {
  const { theme } = useTheme()
  return (
    <>
      {payload.circle && (
        <Circle
          center={[payload.circle.lat, payload.circle.lon]}
          radius={payload.circle.radius_km * 1000}
          pathOptions={{
            color: theme === 'dark' ? '#f2f0e8' : '#0f172a',
            weight: 1.5,
            dashArray: '6 4',
            fillOpacity: 0.03,
          }}
        />
      )}
      {payload.geojson.features.map((f: Feature, i) => {
        const [lon, lat] = (f.geometry as Point).coordinates
        const p = f.properties ?? {}
        const kw = Number(p.capacity_kw ?? 0)
        const color = techColor(String(p.technology))
        return (
          <CircleMarker
            key={i}
            center={[lat, lon]}
            radius={Math.min(14, 3 + Math.sqrt(kw) / 5)} // area-ish scaling, capped
            pathOptions={{
              color: theme === 'dark' ? '#1d1d1b' : '#1e293b',
              weight: 0.8,
              fillColor: color,
              fillOpacity: 0.85,
            }}
          >
            <Popup>
              <b>{String(p.technology)}</b>
              <br />
              {fmt(kw)} kW net
              <br />
              {p.municipality ? `${String(p.municipality)} · ` : ''}
              {p.year ? `commissioned ${String(p.year)}` : ''}
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}

function PointsLegend({ payload }: { payload: Extract<MapPayload, { kind: 'map_points' }> }) {
  const techs = [...new Set(payload.geojson.features.map((f) => String(f.properties?.technology)))]
  return (
    <div className="absolute bottom-6 left-3 z-[1000] rounded-md bg-card/95 text-ink p-2 text-xs shadow">
      <div className="mb-1 font-semibold">{payload.title}</div>
      {techs.map((t) => (
        <div key={t} className="flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ background: TECH_COLORS[t] ?? '#64748b' }}
          />
          {t}
        </div>
      ))}
      <div className="mt-1 text-muted">Size ~ capacity. Only units with public coordinates.</div>
    </div>
  )
}

export function MapView({
  payloads,
  onPickMunicipality,
}: {
  payloads: MapPayload[]
  onPickMunicipality: (name: string) => void
}) {
  const bounds = useMemo(() => boundsOf(payloads), [payloads])
  const choropleth = payloads.find((p) => p.kind === 'map_choropleth')
  const points = payloads.find((p) => p.kind === 'map_points')
  return (
    <div className="relative h-full w-full">
      <MapContainer center={FREIBURG} zoom={9} className="h-full w-full" scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {payloads.map((p, i) => {
          if (p.kind === 'map_choropleth')
            return <Choropleth key={i} payload={p} onPick={onPickMunicipality} />
          if (p.kind === 'map_highlight')
            return (
              <GeoJSON
                key={`${p.title}-${i}`}
                data={p.geojson as FeatureCollection}
                style={{ color: '#dc2626', weight: 2.5, fillColor: '#dc2626', fillOpacity: 0.08 }}
              />
            )
          return <PointsLayer key={i} payload={p} />
        })}
        <ResizeSync />
        <FitBounds bounds={bounds} />
      </MapContainer>
      {choropleth?.kind === 'map_choropleth' && <ChoroplethLegend payload={choropleth} />}
      {!choropleth && points?.kind === 'map_points' && <PointsLegend payload={points} />}
    </div>
  )
}
