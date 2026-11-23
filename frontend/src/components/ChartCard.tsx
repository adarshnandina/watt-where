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

export function ChartCard({ chart }: { chart: ChartData }) {
  // Recharts wants one object per x value: [{x: 2015, solar: 1.2, wind: 0.3}, ...]
  const rows = chart.x.map((x, i) => {
    const row: Record<string, string | number> = { x }
    for (const s of chart.series) row[s.name] = s.values[i]
    return row
  })
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="mb-2 text-sm font-semibold">{chart.title}</h3>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="x" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit={` ${chart.y_unit}`} width={72} />
            <Tooltip formatter={(v) => `${Number(v).toLocaleString('en-US')} ${chart.y_unit}`} />
            <Legend />
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
