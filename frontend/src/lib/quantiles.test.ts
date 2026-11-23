import { expect, it } from 'vitest'
import { classOf, quantileBreaks } from './quantiles'

it('splits values into roughly equal-sized classes', () => {
  const values = Array.from({ length: 60 }, (_, i) => i)
  const breaks = quantileBreaks(values, 6)
  expect(breaks).toEqual([10, 20, 30, 40, 50])
  expect(classOf(0, breaks)).toBe(0)
  expect(classOf(10, breaks)).toBe(1)
  expect(classOf(59, breaks)).toBe(5)
})

it('collapses duplicate breaks when many values are equal (e.g. lots of zeros)', () => {
  const breaks = quantileBreaks([0, 0, 0, 0, 0, 0, 0, 0, 5, 9], 6)
  expect(new Set(breaks).size).toBe(breaks.length)
  expect(quantileBreaks([], 6)).toEqual([])
})
