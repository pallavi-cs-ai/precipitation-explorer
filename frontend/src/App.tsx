import { useCallback, useEffect, useReducer, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  CloudRain,
  Droplets,
  Info,
  Layers,
  LoaderCircle,
  MapPin,
  Pause,
  Play,
  RefreshCw,
  ScanLine,
  Search,
  Waves,
} from 'lucide-react'
import { Button } from './components/ui/button'
import { ForecastMap } from './components/ForecastMap'
import { ForecastChart } from './components/ForecastChart'
import {
  ApiError,
  amount,
  day,
  getJson,
  initialInterval,
  shouldRetry,
  time,
  total,
  type Location,
  type Manifest,
  type PointForecast,
} from './lib/api'

interface State {
  index: number
  location: Location
  playing: boolean
  range: [number, number] | null
}
type Action =
  | { type: 'select'; index: number }
  | { type: 'location'; location: Location }
  | { type: 'play' }
  | { type: 'stop' }
  | { type: 'range'; range: [number, number] | null }
export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'select':
      return { ...state, index: action.index, range: null }
    case 'location':
      return { ...state, location: action.location }
    case 'play':
      return { ...state, playing: !state.playing, range: null }
    case 'stop':
      return { ...state, playing: false }
    case 'range':
      return {
        ...state,
        index: action.range?.[0] ?? state.index,
        range: action.range,
        playing: false,
      }
  }
}
const cities: Location[] = [
  { name: 'Chennai', lat: 13.0827, lon: 80.2707 },
  { name: 'Bengaluru', lat: 12.9716, lon: 77.5946 },
  { name: 'Mumbai', lat: 19.076, lon: 72.8777 },
  { name: 'Pune', lat: 18.5204, lon: 73.8567 },
  { name: 'New Delhi', lat: 28.6139, lon: 77.209 },
  { name: 'Kolkata', lat: 22.5726, lon: 88.3639 },
  { name: 'Hyderabad', lat: 17.385, lon: 78.4867 },
  { name: 'Guwahati', lat: 26.1445, lon: 91.7362 },
]
function ErrorNotice({ error, retry }: { error: Error; retry: () => void }) {
  return (
    <div className="error-notice" role="alert">
      <strong>Forecast unavailable</strong>
      <p>{error.message}</p>
      {error instanceof ApiError && error.requestId && <small>Reference: {error.requestId}</small>}
      <Button variant="outline" size="sm" onClick={retry}>
        <RefreshCw size={13} />
        Try again
      </Button>
    </div>
  )
}

export default function App() {
  const latest = useQuery({
    queryKey: ['latest'],
    queryFn: ({ signal }) => getJson<Manifest>('/api/v1/forecast/latest', signal),
    staleTime: 60_000,
    refetchInterval: (query) => (query.state.data ? 300_000 : 15_000),
    retry: shouldRetry,
  })
  const [active, setActive] = useState<Manifest | null>(null)
  const manifest = active ?? latest.data
  const [about, setAbout] = useState(false)
  return (
    <div className="app-shell">
      <header className="header">
        <a href="/" className="brand" aria-label="Pluvia home">
          <span className="brand-icon">
            <Waves size={23} />
          </span>
          pluvia
          <span className="brand-divider" />
          <span className="brand-sub">PRECIPITATION EXPLORER</span>
        </a>
        <div className="header-right">
          <span className="source-badge">
            <span className="dot" />
            ECMWF · IFS
          </span>
          <button className="about-button" onClick={() => setAbout(!about)}>
            <Info size={16} />
            <span>About the data</span>
          </button>
        </div>
      </header>
      {about && (
        <div className="about-panel">
          <strong>A forecast, clearly presented.</strong>
          <p>
            Real ECMWF IFS total precipitation at 0.25° resolution. Amounts include liquid and
            frozen precipitation as water equivalent. Each bar represents three hours, not exact
            rain timing. Location values use the nearest grid cell. This explorer is not a warning
            service.
          </p>
          <a
            href="https://www.ecmwf.int/en/forecasts/datasets/open-data"
            target="_blank"
            rel="noreferrer"
          >
            ECMWF Open Data · CC BY 4.0 ↗
          </a>
          <Button variant="ghost" size="sm" onClick={() => setAbout(false)}>
            Close
          </Button>
        </div>
      )}
      {!manifest && latest.isPending && (
        <main className="fatal">
          <LoaderCircle className="spin" size={30} />
          <h1>Finding the latest forecast</h1>
          <p>Loading a complete, verified IFS run.</p>
        </main>
      )}
      {!manifest && latest.error && (
        <main className="fatal">
          <ErrorNotice error={latest.error} retry={() => void latest.refetch()} />
        </main>
      )}
      {manifest && (
        <Explorer
          key={manifest.run_id}
          manifest={manifest}
          freezeRun={() => setActive(manifest)}
          newer={
            latest.data && latest.data.run_id !== manifest.run_id
              ? () => setActive(latest.data!)
              : undefined
          }
        />
      )}
    </div>
  )
}

function Explorer({
  manifest,
  freezeRun,
  newer,
}: {
  manifest: Manifest
  freezeRun: () => void
  newer?: () => void
}) {
  const [state, dispatch] = useReducer(reducer, {
    index: initialInterval(manifest),
    location: cities[0],
    playing: false,
    range: null,
  })
  const [mode, setMode] = useState<'interval' | 'range'>('interval')
  const [mapStatus, setMapStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [opacity, setOpacity] = useState(0.75)
  const [retryImage, setRetryImage] = useState(0)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  useEffect(() => {
    freezeRun()
  }, [freezeRun])
  const point = useQuery({
    queryKey: ['point', manifest.run_id, state.location.lat, state.location.lon],
    queryFn: ({ signal }) =>
      getJson<PointForecast>(
        `/api/v1/forecasts/${manifest.run_id}/point?lat=${state.location.lat}&lon=${state.location.lon}`,
        signal,
      ),
    staleTime: Infinity,
    gcTime: 15 * 60_000,
    retry: shouldRetry,
  })
  const select = useCallback((index: number) => {
    dispatch({ type: 'stop' })
    dispatch({ type: 'select', index })
    setMode('interval')
  }, [])
  const selectRange = useCallback((range: [number, number]) => {
    dispatch({ type: 'range', range })
    setMode('range')
  }, [])
  const selectLocation = useCallback(
    (location: Location) => {
      const [w, s, e, n] = manifest.bounds
      if (location.lon < w || location.lon > e || location.lat < s || location.lat > n) {
        setSelectionError('Choose a location inside the India-region forecast (65–100°E, 5–38°N).')
        return
      }
      setSelectionError(null)
      dispatch({ type: 'location', location })
      setSearch('')
      setSearchOpen(false)
    },
    [manifest.bounds],
  )
  useEffect(() => {
    if (!state.playing || mapStatus !== 'ready') return
    const timer = window.setTimeout(() => {
      if (state.index >= manifest.intervals.length - 1) dispatch({ type: 'stop' })
      else dispatch({ type: 'select', index: state.index + 1 })
    }, 1400)
    return () => clearTimeout(timer)
  }, [state.playing, state.index, mapStatus, manifest.intervals.length])
  useEffect(() => {
    if (mapStatus === 'error') dispatch({ type: 'stop' })
  }, [mapStatus])
  useEffect(() => {
    const next = manifest.intervals[state.index + 1]
    if (!next) return
    const controller = new AbortController()
    void fetch(next.image_url, { signal: controller.signal }).catch(() => undefined)
    return () => controller.abort()
  }, [state.index, manifest.intervals])
  const selected = manifest.intervals[state.index]
  const range = mode === 'range' ? state.range : null
  const first = range ? manifest.intervals[range[0]] : selected
  const last = range ? manifest.intervals[range[1] - 1] : selected
  const values = point.data?.intervals.map((i) => i.amount_mm)
  const selectionValue = values
    ? range
      ? total(values.slice(range[0], range[1]))
      : values[state.index]
    : null
  const horizonTotal = values ? total(values) : null
  const peakIndex = values?.some((v) => v === null)
    ? -1
    : (values?.reduce<number>((best, v, i, arr) => ((v ?? -1) > (arr[best] ?? -1) ? i : best), 0) ??
      -1)
  const age = (Date.now() - new Date(manifest.initialization).getTime()) / 3600000
  const stale = age > 18
  const expired = Date.now() > new Date(manifest.intervals.at(-1)!.end).getTime()
  const baseImage = range
    ? `/api/v1/forecasts/${manifest.run_id}/accumulation.png?start=${range[0]}&end=${range[1]}`
    : selected.image_url
  const imageUrl = retryImage
    ? `${baseImage}${baseImage.includes('?') ? '&' : '?'}retry=${retryImage}`
    : baseImage
  const chooseMode = (value: 'interval' | 'range') => {
    setMode(value)
    dispatch({
      type: 'range',
      range: value === 'range' ? [state.index, Math.min(state.index + 2, 24)] : null,
    })
  }
  const download = () => {
    if (!point.data) return
    const text =
      'run_id,sampled_lat,sampled_lon,start_utc,end_utc,precipitation_mm\n' +
      point.data.intervals
        .map(
          (i) =>
            `${manifest.run_id},${point.data!.sampled.lat},${point.data!.sampled.lon},${i.start},${i.end},${i.amount_mm ?? ''}`,
        )
        .join('\n')
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${manifest.run_id}-point.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <>
      <section className="intro">
        <div>
          <div className="eyebrow">72-HOUR FORECAST EXPLORER</div>
          <h1>Follow the rain.</h1>
          <p>Explore where, when, and how much precipitation is forecast.</p>
        </div>
        <div className="run-meta">
          <span className="run-label">
            <span className={`dot ${stale ? 'amber' : ''}`} />
            {expired
              ? 'Forecast window ended'
              : stale
                ? 'Older forecast · refresh delayed'
                : 'Forecast available'}
          </span>
          <span>
            Initialized {day(manifest.initialization)} · {time(manifest.initialization)} IST
          </span>
          <span className="resolution">
            0.25° grid <span>·</span> 3-hour intervals <span>·</span> India region
          </span>
          {newer && (
            <Button size="sm" onClick={newer}>
              Load newer forecast
            </Button>
          )}
        </div>
      </section>
      <main className="workspace">
        <section className="map-panel" aria-label="Forecast map">
          <ForecastMap
            manifest={manifest}
            location={state.location}
            imageUrl={imageUrl}
            onLocation={selectLocation}
            onStatus={setMapStatus}
            opacity={opacity}
          />
          <div className="map-toolbar">
            <div className="mode-switch" role="group" aria-label="Map mode">
              <button
                className={mode === 'interval' ? 'active' : ''}
                onClick={() => chooseMode('interval')}
              >
                <CloudRain size={14} />
                3-hour amount
              </button>
              <button
                className={mode === 'range' ? 'active' : ''}
                onClick={() => chooseMode('range')}
              >
                <Layers size={14} />
                Period total
              </button>
            </div>
          </div>
          <div className="map-stamp">
            <span className="eyebrow">
              {range ? 'ACCUMULATED PRECIPITATION' : 'TOTAL PRECIPITATION'}
            </span>
            <strong>{day(first.start)}</strong>
            <span>
              {time(first.start)} →{' '}
              {range && day(first.start) !== day(last.end) ? `${day(last.end)} · ` : ''}
              {time(last.end)} IST
            </span>
          </div>
          {mapStatus !== 'ready' && (
            <div className={`map-load ${mapStatus}`} role="status">
              {mapStatus === 'loading' ? (
                <>
                  <LoaderCircle className="spin" size={15} />
                  Loading selected forecast layer…
                </>
              ) : (
                <>
                  Forecast layer unavailable{' '}
                  <button onClick={() => setRetryImage((v) => v + 1)}>Retry</button>
                </>
              )}
            </div>
          )}
          {selectionError && (
            <div className="selection-error" role="alert">
              {selectionError}
              <button aria-label="Dismiss location message" onClick={() => setSelectionError(null)}>
                ×
              </button>
            </div>
          )}
          <div className="legend">
            <div>
              <strong>Precipitation</strong>
              <span>{range ? 'mm / selected period' : 'mm / 3 hours'}</span>
            </div>
            <div className="legend-colors">
              {manifest.colors.map((color, i) => (
                <span
                  key={color}
                  style={{ background: color }}
                  title={`${manifest.thresholds[i] * (range ? 3 : 1)} mm`}
                />
              ))}
            </div>
            <div className="legend-labels">
              {manifest.thresholds.map((v) => (
                <span key={v}>{+(v * (range ? 3 : 1)).toFixed(1)}</span>
              ))}
            </div>
            <label className="opacity-control">
              Layer opacity
              <input
                aria-label="Layer opacity"
                type="range"
                min="0.15"
                max="1"
                step="0.05"
                value={opacity}
                onChange={(e) => setOpacity(+e.target.value)}
              />
            </label>
            <small>
              Clear areas: below {range ? '0.3' : '0.1'} mm · above scale uses darkest color
            </small>
          </div>
          <div className="map-hint">
            <MapPin size={13} />
            Click the map to explore a location
          </div>
        </section>
        <aside className="location-panel">
          <div className="panel-heading">
            <span className="eyebrow">LOCATION FORECAST</span>
            <ScanLine size={17} />
          </div>
          <div className="search-wrap">
            <Search size={16} />
            <input
              aria-label="Search supported cities"
              placeholder="Search a city"
              value={search}
              onFocus={() => setSearchOpen(true)}
              onChange={(e) => {
                setSearch(e.target.value)
                setSearchOpen(true)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Escape') setSearchOpen(false)
              }}
            />
            <button aria-label="Toggle city list" onClick={() => setSearchOpen(!searchOpen)}>
              <ChevronDown size={15} />
            </button>
            {searchOpen && (
              <div className="city-results">
                {cities
                  .filter((c) => c.name!.toLowerCase().includes(search.toLowerCase()))
                  .map((c) => (
                    <button key={c.name} onClick={() => selectLocation(c)}>
                      <MapPin size={13} />
                      {c.name}
                    </button>
                  ))}
                {!cities.some((c) => c.name!.toLowerCase().includes(search.toLowerCase())) && (
                  <p>No preset found. Select a location on the map.</p>
                )}
              </div>
            )}
          </div>
          <div className="location-name">
            <span className="pin-icon">
              <MapPin size={20} />
            </span>
            <div>
              <h2>{state.location.name ?? 'Selected location'}</h2>
              <p>
                {state.location.lat.toFixed(2)}°N, {state.location.lon.toFixed(2)}°E
              </p>
            </div>
            <span className="location-tag">INDIA REGION</span>
          </div>
          {point.isPending ? (
            <div className="point-loading" role="status">
              <LoaderCircle className="spin" size={20} />
              Loading location forecast…
            </div>
          ) : point.error ? (
            <ErrorNotice error={point.error} retry={() => void point.refetch()} />
          ) : (
            point.data && (
              <>
                <div className="main-amount">
                  <span className="eyebrow">
                    {range ? 'SELECTED PERIOD TOTAL' : 'SELECTED 3-HOUR AMOUNT'}
                  </span>
                  <div>
                    <strong>{amount(selectionValue)}</strong>
                    <span>mm</span>
                    <Droplets size={28} />
                  </div>
                  <p>
                    {selectionValue === null
                      ? 'Data unavailable for this period'
                      : selectionValue === 0
                        ? 'No precipitation in this forecast interval'
                        : 'Forecast water-equivalent precipitation'}
                  </p>
                </div>
                <div className="chart-heading">
                  <h3>Precipitation over time</h3>
                  <span>mm / 3h</span>
                </div>
                <ForecastChart
                  data={point.data}
                  selected={state.index}
                  range={range}
                  onSelect={select}
                  onRange={selectRange}
                  rangeMode={mode === 'range'}
                />
                <div className="chart-hint">
                  {mode === 'range'
                    ? 'Drag across the chart to select a period.'
                    : 'Select a bar to explore that forecast interval.'}
                </div>
                {range && (
                  <div className="range-inputs">
                    <label>
                      From
                      <select
                        aria-label="Accumulation start"
                        value={range[0]}
                        onChange={(e) =>
                          selectRange([+e.target.value, Math.max(+e.target.value + 1, range[1])])
                        }
                      >
                        {manifest.intervals.map((i) => (
                          <option key={i.id} value={i.id}>
                            {day(i.start)} {time(i.start)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      To
                      <select
                        aria-label="Accumulation end"
                        value={range[1]}
                        onChange={(e) =>
                          selectRange([Math.min(range[0], +e.target.value - 1), +e.target.value])
                        }
                      >
                        {manifest.intervals.map((i) => (
                          <option key={i.id} value={i.id + 1}>
                            {day(i.end)} {time(i.end)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
                <div className="summary-grid">
                  <div>
                    <span>72-hour total</span>
                    <strong>
                      {amount(horizonTotal)} <small>mm</small>
                    </strong>
                  </div>
                  <div>
                    <span>Wettest interval</span>
                    <strong>
                      {peakIndex >= 0 ? amount(values![peakIndex]) : '—'} <small>mm</small>
                    </strong>
                    <small>
                      {peakIndex >= 0 && (values![peakIndex] ?? 0) > 0
                        ? `${day(manifest.intervals[peakIndex].start)} · ${time(manifest.intervals[peakIndex].start)}`
                        : 'No distinct wet interval'}
                    </small>
                  </div>
                </div>
                <details className="data-table">
                  <summary>Inspect forecast values</summary>
                  <div>
                    <table>
                      <thead>
                        <tr>
                          <th>Interval start · IST</th>
                          <th>mm / 3h</th>
                        </tr>
                      </thead>
                      <tbody>
                        {point.data.intervals.map((i) => (
                          <tr key={i.id}>
                            <td>
                              {day(i.start)} {time(i.start)}
                            </td>
                            <td>{amount(i.amount_mm)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
                <button className="download" onClick={download}>
                  <ArrowDownToLine size={14} />
                  Download location data <span>CSV</span>
                </button>
                <div className="grid-note">
                  <Info size={14} />
                  <p>
                    Sampled at {point.data.sampled.lat.toFixed(2)}°N,{' '}
                    {point.data.sampled.lon.toFixed(2)}°E. Grid values represent an area, not a
                    street-level prediction.
                  </p>
                </div>
              </>
            )
          )}
        </aside>
        <section className="timeline" aria-label="Forecast timeline">
          <div className="timeline-top">
            <div>
              <span className="eyebrow">FORECAST TIMELINE</span>
              <strong>
                {day(first.start)}{' '}
                <span>
                  {time(first.start)}–
                  {range && day(first.start) !== day(last.end) ? `${day(last.end)} · ` : ''}
                  {time(last.end)} IST
                </span>
              </strong>
            </div>
            <div className="playback">
              <Button
                variant="ghost"
                size="icon"
                aria-label="Previous interval"
                disabled={state.index === 0}
                onClick={() => select(state.index - 1)}
              >
                <ArrowLeft size={16} />
              </Button>
              <Button
                size="icon"
                aria-label={state.playing ? 'Pause forecast' : 'Play forecast'}
                onClick={() => {
                  setMode('interval')
                  if (state.index === 23) dispatch({ type: 'select', index: 0 })
                  dispatch({ type: 'play' })
                }}
              >
                {state.playing ? <Pause size={16} /> : <Play size={16} />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Next interval"
                disabled={state.index === 23}
                onClick={() => select(state.index + 1)}
              >
                <ArrowRight size={16} />
              </Button>
            </div>
          </div>
          <input
            className="timeline-slider"
            type="range"
            aria-label="Forecast interval"
            min="0"
            max="23"
            step="1"
            value={state.index}
            onChange={(e) => select(+e.target.value)}
          />
          <div className="timeline-ticks">
            {[0, 6, 12, 18, 23].map((i) => (
              <button key={i} onClick={() => select(i)}>
                <strong>{day(manifest.intervals[i].start)}</strong>
                <span>{time(manifest.intervals[i].start)}</span>
              </button>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <span>
          <Check size={13} />
          Real forecast data · ECMWF Open Data
        </span>
        <span>All times IST (UTC+05:30) · 72h from model initialization</span>
        <a
          href="https://github.com/pallavi-cs-ai/precipitation-explorer"
          target="_blank"
          rel="noreferrer"
        >
          Source & methodology ↗
        </a>
      </footer>
    </>
  )
}
