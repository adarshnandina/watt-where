import { useMemo, useState } from 'react'
import type { TableData } from '../api/types'

type Cell = string | number | null

function format(v: Cell, column: string): string {
  if (v === null) return '–'
  if (typeof v === 'number' && !/year|jahr|ags|key/i.test(column)) {
    return v.toLocaleString('en-US', { maximumFractionDigits: 3 }) // thousands separators
  }
  return String(v)
}

function compare(a: Cell, b: Cell): number {
  if (a === b) return 0
  if (a === null) return 1 // nulls last
  if (b === null) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b))
}

/** A small table; click a column header to sort by it (click again to reverse). */
export function ResultTable({ table }: { table: TableData }) {
  const [sort, setSort] = useState<{ col: number; dir: 1 | -1 } | null>(null)
  const rows = useMemo(() => {
    if (!sort) return table.rows
    return [...table.rows].sort((a, b) => sort.dir * compare(a[sort.col], b[sort.col]))
  }, [table.rows, sort])

  return (
    <div className="flex h-full min-h-[200px] flex-col rounded-2xl border border-line bg-card p-3 shadow-sm">
      <h3 className="mb-2 text-sm font-semibold">{table.title}</h3>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-stone-50">
            <tr>
              {table.columns.map((c, i) => (
                <th
                  key={c}
                  className="cursor-pointer select-none whitespace-nowrap px-2 py-1 font-semibold"
                  onClick={() =>
                    setSort((s) =>
                      s?.col === i ? { col: i, dir: (s.dir * -1) as 1 | -1 } : { col: i, dir: 1 },
                    )
                  }
                >
                  {c}
                  {sort?.col === i ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-stone-100">
                {r.map((v, j) => (
                  <td
                    key={j}
                    className={`px-2 py-1 ${typeof v === 'number' ? 'text-right tabular-nums' : ''}`}
                  >
                    {format(v, table.columns[j] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
