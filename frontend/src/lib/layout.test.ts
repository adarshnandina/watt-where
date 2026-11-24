import { expect, it } from 'vitest'
import { clamp, fractionInRect } from './layout'

const rect = { left: 100, top: 50, width: 1000, height: 500 }

it('clamps into range', () => {
  expect(clamp(5, 10, 20)).toBe(10)
  expect(clamp(25, 10, 20)).toBe(20)
  expect(clamp(15, 10, 20)).toBe(15)
})

it('computes the pointer position as a fraction of the container', () => {
  expect(fractionInRect('x', { x: 600, y: 0 }, rect)).toBe(0.5)
  expect(fractionInRect('y', { x: 0, y: 300 }, rect)).toBe(0.5)
  expect(fractionInRect('x', { x: 100, y: 0 }, rect)).toBe(0)
})
