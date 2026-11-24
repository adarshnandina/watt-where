import { useEffect, useState } from 'react'
import { BoltIcon, ChartIcon, PinIcon, ScaleIcon, SunIcon, TrophyIcon } from './icons'

const FALLBACK = [
  'How much solar capacity is installed in Freiburg im Breisgau?',
  'Which 10 municipalities in Baden-Württemberg have the most solar capacity per inhabitant?',
  'Show me wind turbines within 25 km of Freiburg.',
  'How has battery storage capacity in Freiburg grown since 2015?',
  'Compare solar and wind capacity in the Breisgau-Hochschwarzwald district.',
]
const ICONS = [SunIcon, TrophyIcon, PinIcon, ChartIcon, ScaleIcon, SunIcon]

/** Empty state: a greeting plus clickable example questions (loaded from /api/examples). */
export function ExampleQuestions({ onPick }: { onPick: (q: string) => void }) {
  const [examples, setExamples] = useState<string[]>(FALLBACK)
  useEffect(() => {
    fetch('/api/examples')
      .then((r) => r.json())
      .then((d: unknown) => {
        const list = (d as { examples?: unknown }).examples
        if (Array.isArray(list) && list.every((x) => typeof x === 'string')) setExamples(list)
      })
      .catch(() => {}) // keep the fallback list
  }, []) // [] = run once, when the component first appears

  return (
    <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-5 py-8">
      <div className="fade-in w-full max-w-3xl">
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-2xl bg-accent text-white">
          <BoltIcon width={22} height={22} />
        </div>
        <h2 className="text-3xl font-semibold tracking-tight">What would you like to know?</h2>
        <p className="mt-2 text-[15px] text-muted">
          Ask about solar, wind, biomass, hydro and battery storage in Baden-Württemberg. Answers
          come with a map, a chart and a table.
        </p>
        <div className="mt-6 grid gap-2.5 sm:grid-cols-2">
          {examples.map((q, i) => {
            const Icon = ICONS[i % ICONS.length]
            return (
              <button
                key={q}
                type="button"
                onClick={() => onPick(q)}
                className="group flex items-start gap-3 rounded-2xl border border-line bg-card p-3.5 text-left text-sm leading-snug shadow-sm transition hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-md"
              >
                <Icon className="mt-0.5 shrink-0 text-accent" />
                <span>{q}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
