import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartData } from '../api/types'
import { techColor } from '../lib/colors'
import { useTheme } from '../lib/theme'

export function ChartCard({ chart }: { chart: ChartData }) {
  const dark = useTheme().theme === 'dark'
  const grid = dark ? '#44443f' : '#e7e5df'
  const axis = dark ? '#a8a59c' : '#6b6a66'
  // Recharts wants one object per x value: [{x: 2015, solar: 1.2, wind: 0.3}, ...]
  const rows = chart.x.map((x, i) => {
    const row: Record<string, string | number> = { x }
    for (const s of chart.series) row[s.name] = s.values[i]
    return row
  })
  return (
    <div className="flex h-full min-h-[200px] flex-col rounded-2xl border border-line bg-card p-3 shadow-sm">
      <h3 className="mb-2 text-sm font-semibold">{chart.title}</h3>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={grid} />
            <XAxis dataKey="x" tick={{ fontSize: 11, fill: axis }} stroke={grid} />
            <YAxis
              tick={{ fontSize: 11, fill: axis }}
              stroke={grid}
              unit={` ${chart.y_unit}`}
              width={72}
            />
            <Tooltip
              formatter={(v) => `${Number(v).toLocaleString('en-US')} ${chart.y_unit}`}
              contentStyle={{
                background: dark ? '#30302e' : '#ffffff',
                border: `1px solid ${grid}`,
                borderRadius: 8,
                color: dark ? '#f2f0e8' : '#1f1e1d',
              }}
            />
            <Legend wrapperStyle={{ color: axis, fontSize: 12 }} />
            {chart.series.map((s) => (
              <Line
                key={s.name}
                type="monotone"
                dataKey={s.name}
                stroke={techColor(s.name)}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
