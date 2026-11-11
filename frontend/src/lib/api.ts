import type { components } from './schema'
export type Interval = components['schemas']['Interval']
export type Manifest = components['schemas']['Manifest']
export type PointForecast = components['schemas']['PointForecast']
export type Location = components['schemas']['Coordinates'] & { name?: string }
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public requestId?: string,
  ) {
    super(message)
  }
}
export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(15000)
  const response = await fetch(url, {
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new ApiError(
      payload?.error?.message ?? 'Could not load forecast. Please try again.',
      response.status,
      payload?.error?.request_id,
    )
  }
  return response.json() as Promise<T>
}
export function shouldRetry(count: number, error: Error) {
  return count < 2 && (!(error instanceof ApiError) || error.status >= 500)
}
export const time = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  }).format(new Date(value))
export const day = (value: string) =>
  new Intl.DateTimeFormat('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(value))
export const amount = (value: number | null | undefined) =>
  value == null ? '—' : value > 0 && value < 0.1 ? '<0.1' : value.toFixed(1)
export function total(values: (number | null)[]) {
  return values.some((v) => v === null)
    ? null
    : values.reduce<number>((sum, v) => sum + (v ?? 0), 0)
}
export function initialInterval(manifest: Manifest, now = Date.now()) {
  const found = manifest.intervals.findIndex((i) => new Date(i.end).getTime() > now)
  return found < 0 ? manifest.intervals.length - 1 : found
}

export const coordinates = (lat: number, lon: number) =>
  `${Math.abs(lat).toFixed(2)}°${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(2)}°${lon < 0 ? 'W' : 'E'}`
export const normalizeLongitude = (lon: number) => ((((lon + 180) % 360) + 360) % 360) - 180
