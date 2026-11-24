import { expect, it } from 'vitest'
import { resolveInitialTheme } from './theme'

it('a saved choice wins over the system preference', () => {
  expect(resolveInitialTheme('light', true)).toBe('light')
  expect(resolveInitialTheme('dark', false)).toBe('dark')
})

it('falls back to the system preference, and ignores junk values', () => {
  expect(resolveInitialTheme(null, true)).toBe('dark')
  expect(resolveInitialTheme(null, false)).toBe('light')
  expect(resolveInitialTheme('purple', true)).toBe('dark')
})
