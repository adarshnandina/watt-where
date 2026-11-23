// One colour per technology, shared by the map points and the chart lines so the same
// technology always looks the same.
export const TECH_COLORS: Record<string, string> = {
  solar: '#f59e0b',
  wind: '#0ea5e9',
  biomass: '#16a34a',
  hydro: '#6366f1',
  storage: '#a855f7',
}
export const techColor = (t: string): string => TECH_COLORS[t] ?? '#64748b'

// 6-class sequential ramp (light -> dark) for the choropleth.
export const RAMP = ['#eff6ff', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c']
