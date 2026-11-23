import { useEffect, useState } from 'react'

const FALLBACK = [
  'How much solar capacity is installed in Freiburg im Breisgau?',
  'Which 10 municipalities in Baden-Württemberg have the most solar capacity per inhabitant?',
  'Show me wind turbines within 25 km of Freiburg.',
  'How has battery storage capacity in Freiburg grown since 2015?',
  'Compare solar and wind capacity in the Breisgau-Hochschwarzwald district.',
]

/** Empty-state: clickable example questions, loaded from the backend (/api/examples). */
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
    <div className="flex flex-1 flex-col justify-center gap-3 px-4">
      <p className="text-sm text-slate-500">Try asking:</p>
      {examples.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onPick(q)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 shadow-sm hover:border-slate-400"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
