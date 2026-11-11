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
