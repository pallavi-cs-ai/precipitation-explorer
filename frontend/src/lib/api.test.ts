import { describe, expect, it } from 'vitest'
import { amount, total, shouldRetry, ApiError } from './api'
import { reducer } from '../App'
describe('forecast correctness', () => {
  it('does not turn missing values into dry weather', () => {
    expect(total([1, null, 2])).toBeNull()
    expect(total([1, 2])).toBe(3)
    expect(amount(null)).toBe('—')
    expect(amount(0)).toBe('0.0')
  })
  it('bounds retries and does not retry invalid requests', () => {
    expect(shouldRetry(0, new ApiError('invalid', 422))).toBe(false)
    expect(shouldRetry(1, new ApiError('offline', 503))).toBe(true)
    expect(shouldRetry(2, Error())).toBe(false)
  })
  it('keeps range selection and playback mutually exclusive', () => {
    const s = { index: 0, location: { lat: 13, lon: 80 }, playing: true, range: null }
    expect(reducer(s, { type: 'range', range: [1, 4] })).toEqual({
      ...s,
      index: 1,
      playing: false,
      range: [1, 4],
    })
    expect(reducer({ ...s, range: [1, 4] }, { type: 'select', index: 2 }).range).toBeNull()
  })
})

import { coordinates, normalizeLongitude } from './api'
it('handles western/southern coordinates and wrapped longitudes', () => {
  expect(coordinates(-33.87, -70.66)).toBe('33.87°S, 70.66°W')
  expect(normalizeLongitude(181)).toBe(-179)
  expect(normalizeLongitude(-181)).toBe(179)
})

import { chartRange, matchingLocations, time, day } from './api'
it('formats UTC midnight and preserves the UTC calendar day', () => {
  expect(time('2026-11-12T00:00:00Z')).toBe('00:00')
  expect(time('2026-11-12T00:30:00+05:30')).toBe('19:00')
  expect(day('2026-11-12T00:30:00+05:30')).toContain('11 Nov')
})
it('searches accents and whitespace and respects available coverage', () => {
  const cities = [
    { name: 'São Paulo', lat: -23.5, lon: -46.6 },
    { name: 'Chennai', lat: 13, lon: 80 },
  ]
  expect(matchingLocations(cities, '  sao ', [-180, -85, 180, 85])).toHaveLength(1)
  expect(matchingLocations(cities, 'sao', [65, 5, 100, 38])).toHaveLength(0)
})
it('bounds brush ranges and handles reversed selection', () => {
  expect(chartRange([8, 2], 24)).toEqual([2, 9])
  expect(chartRange([-10, 30], 24)).toEqual([0, 24])
  expect(chartRange([24, 24], 24)).toEqual([23, 24])
  expect(chartRange([NaN, 2], 24)).toBeNull()
})
