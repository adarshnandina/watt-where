/** Quantile class boundaries: each class holds roughly the same number of municipalities. */
export function quantileBreaks(values: number[], classes = 6): number[] {
  const sorted = [...values].sort((a, b) => a - b)
  if (sorted.length === 0) return []
  const breaks: number[] = []
  for (let i = 1; i < classes; i++) {
    const v = sorted[Math.floor((sorted.length * i) / classes)]
    if (breaks.length === 0 || v > breaks[breaks.length - 1]) breaks.push(v)
  }
  return breaks // upper-exclusive thresholds between classes
}
export const classOf = (v: number, breaks: number[]) => breaks.filter((b) => v >= b).length
