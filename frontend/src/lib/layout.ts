import { useCallback, useState } from 'react'

export const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v))

/** Where is the pointer inside `rect`, as a fraction (0..1) along the given axis? */
export function fractionInRect(
  axis: 'x' | 'y',
  pointer: { x: number; y: number },
  rect: { left: number; top: number; width: number; height: number },
): number {
  return axis === 'x' ? (pointer.x - rect.left) / rect.width : (pointer.y - rect.top) / rect.height
}

/** A number kept in localStorage, so panel sizes survive a page reload. */
export function usePersistentFraction(key: string, initial: number, min: number, max: number) {
  const [value, setValue] = useState(() => {
    try {
      const stored = Number(localStorage.getItem(key))
      return stored > 0 ? clamp(stored, min, max) : initial
    } catch {
      return initial // storage unavailable (private mode etc.)
    }
  })
  const set = useCallback(
    (v: number) => {
      const next = clamp(v, min, max)
      setValue(next)
      try {
        localStorage.setItem(key, String(next))
      } catch {
        /* ignore */
      }
    },
    [key, min, max],
  )
  return [value, set] as const
}
