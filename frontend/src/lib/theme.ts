// Light / dark theme.
//
// How it works: all colours are CSS variables (see index.css). Dark mode is just the class "dark" on
// <html>, which swaps the variable values. This module decides which theme is active, remembers the choice in
// localStorage, and exposes it to components that need it in JavaScript (the map and chart colours).
// (The provider component lives in ThemeProvider.tsx so this file exports no components.)

import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark'
export const THEME_KEY = 'ww.theme'

/** A saved choice wins; otherwise follow the operating system's preference. */
export function resolveInitialTheme(stored: string | null, prefersDark: boolean): Theme {
  if (stored === 'light' || stored === 'dark') return stored
  return prefersDark ? 'dark' : 'light'
}

export function readInitial(): Theme {
  try {
    return resolveInitialTheme(
      localStorage.getItem(THEME_KEY),
      window.matchMedia('(prefers-color-scheme: dark)').matches,
    )
  } catch {
    return 'light'
  }
}

export interface ThemeValue {
  theme: Theme
  toggle: () => void
}
export const ThemeContext = createContext<ThemeValue>({ theme: 'light', toggle: () => {} })

export const useTheme = () => useContext(ThemeContext)
