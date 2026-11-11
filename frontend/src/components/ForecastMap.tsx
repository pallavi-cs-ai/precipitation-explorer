import { normalizeLongitude } from '../lib/api'
import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Location, Manifest } from '../lib/api'
import { Button } from './ui/button'
import { LocateFixed } from 'lucide-react'
interface Props {
  manifest: Manifest
  location: Location
  imageUrl: string
  onLocation: (value: Location) => void
  onStatus: (status: 'loading' | 'ready' | 'error') => void
  opacity: number
}
export function ForecastMap({
  manifest,
  location,
  imageUrl,
  onLocation,
  onStatus,
  opacity,
}: Props) {
  const initialBounds = useRef(manifest.bounds)
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<maplibregl.Map | null>(null)
  const marker = useRef<maplibregl.Marker | null>(null)
  const opacityRef = useRef(opacity)
  useEffect(() => {
    opacityRef.current = opacity
  }, [opacity])
  const callbacks = useRef({ onLocation, onStatus })
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    callbacks.current = { onLocation, onStatus }
  }, [onLocation, onStatus])
  useEffect(() => {
    if (!container.current) return
    let m: maplibregl.Map
    try {
      m = new maplibregl.Map({
        container: container.current,
        style: 'https://tiles.openfreemap.org/styles/positron',
        center: initialBounds.current[0] === -180 ? [0, 15] : [82, 21],
        zoom: initialBounds.current[0] === -180 ? 0.8 : 3.7,
        minZoom: 0,
        renderWorldCopies: false,
        maxZoom: 10,
        attributionControl: { compact: true },
      })
    } catch {
      setMapError(
        'This browser could not start the interactive map. The location chart remains available.',
      )
      callbacks.current.onStatus('error')
      return
    }
    map.current = m
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    m.on('load', () => {
      clearTimeout(timeout)
      const [w, s, e, n] = initialBounds.current
      if (w === -180)
        m.fitBounds(
          [
            [w, s],
            [e, n],
          ],
          { padding: 12, duration: 0 },
        )
      setReady(true)
      setMapError(null)
    })
    m.on('error', () =>
      setMapError(
        'Some map tiles could not load. Check your connection; the forecast chart remains available.',
      ),
    )
    m.on('click', (e) =>
      callbacks.current.onLocation({
        lat: Number(e.lngLat.lat.toFixed(4)),
        lon: Number(normalizeLongitude(e.lngLat.lng).toFixed(4)),
      }),
    )
    const observer = new ResizeObserver(() => m.resize())
    observer.observe(container.current)
    const timeout = window.setTimeout(() => {
      if (!m.isStyleLoaded()) {
        setMapError('Basemap is taking too long to load. Try reloading the page.')
        callbacks.current.onStatus('error')
      }
    }, 20000)
    return () => {
      clearTimeout(timeout)
      observer.disconnect()
      marker.current?.remove()
      marker.current = null
      m.remove()
      map.current = null
      setReady(false)
    }
  }, [])
  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    if (!marker.current)
      marker.current = new maplibregl.Marker({ color: '#133e43' })
        .setLngLat([location.lon, location.lat])
        .addTo(m)
    else marker.current.setLngLat([location.lon, location.lat])
  }, [location, ready])
  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    const controller = new AbortController()
    let active = true
    let objectUrl: string | null = null
    let finish: (() => void) | undefined
    const timeout = window.setTimeout(() => {
      if (active) {
        controller.abort()
        callbacks.current.onStatus('error')
      }
    }, 20000)
    callbacks.current.onStatus('loading')
    if (m.getLayer('precipitation')) m.setLayoutProperty('precipitation', 'visibility', 'none')
    const load = async () => {
      try {
        const response = await fetch(imageUrl, { signal: controller.signal })
        if (!response.ok) throw new Error('Image unavailable')
        objectUrl = URL.createObjectURL(await response.blob())
        const img = new Image()
        img.src = objectUrl
        await img.decode()
        if (!active) return
        const [w, s, e, n] = manifest.bounds
        if (m.getLayer('precipitation')) m.removeLayer('precipitation')
        if (m.getSource('precipitation')) m.removeSource('precipitation')
        m.addSource('precipitation', {
          type: 'image',
          url: objectUrl,
          coordinates: [
            [w, n],
            [e, n],
            [e, s],
            [w, s],
          ],
        })
        const labels = m.getStyle().layers?.find((layer) => layer.type === 'symbol')?.id
        m.addLayer(
          {
            id: 'precipitation',
            type: 'raster',
            source: 'precipitation',
            paint: {
              'raster-opacity': opacityRef.current,
              'raster-fade-duration': 0,
              'raster-resampling': 'nearest',
            },
          },
          labels,
        )
        finish = () => {
          if (active && m.getSource('precipitation') && m.isSourceLoaded('precipitation')) {
            clearTimeout(timeout)
            callbacks.current.onStatus('ready')
            if (finish) m.off('sourcedata', finish)
          }
        }
        m.on('sourcedata', finish)
        finish()
      } catch {
        clearTimeout(timeout)
        if (active) callbacks.current.onStatus('error')
      }
    }
    void load()
    return () => {
      active = false
      clearTimeout(timeout)
      if (finish) m.off('sourcedata', finish)
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [imageUrl, manifest.bounds, ready, retry])
  useEffect(() => {
    if (map.current?.getLayer('precipitation'))
      map.current.setPaintProperty('precipitation', 'raster-opacity', opacity)
  }, [opacity, imageUrl])
  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        aria-label="Interactive precipitation forecast map. Click to inspect a location."
      />
      <Button
        variant="outline"
        size="icon"
        className="map-reset"
        aria-label="Reset map to forecast coverage"
        onClick={() =>
          map.current?.fitBounds(
            [
              [manifest.bounds[0], manifest.bounds[1]],
              [manifest.bounds[2], manifest.bounds[3]],
            ],
            { padding: 45, duration: 600 },
          )
        }
      >
        <LocateFixed size={18} />
      </Button>
      {mapError && (
        <div className="map-warning" role="status">
          {mapError}
          <button
            onClick={() => {
              setMapError(null)
              setRetry((r) => r + 1)
            }}
          >
            Retry forecast layer
          </button>
        </div>
      )}
    </>
  )
}
