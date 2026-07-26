import { useState } from 'react'
import { EvaluatePage } from './pages/EvaluatePage'
import { ResultsPage } from './pages/ResultsPage'
import { ForbiddenListPage } from './pages/ForbiddenListPage'
import type { ResultRow } from './lib/resultRow'

type Tab = 'evaluate' | 'results' | 'forbidden-list'

const TABS: { id: Tab; label: string }[] = [
  { id: 'evaluate', label: 'Evaluate' },
  { id: 'results', label: 'Results' },
  { id: 'forbidden-list', label: 'Forbidden List' },
]

function App() {
  const [tab, setTab] = useState<Tab>('evaluate')
  const [results, setResults] = useState<ResultRow[]>([])

  function addResults(rows: ResultRow[]) {
    setResults((previous) => [...rows, ...previous])
  }

  return (
    <div className="mx-auto min-h-screen max-w-4xl px-4 py-8 text-neutral-900 dark:text-neutral-100">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Product Safety Compliance</h1>
        <p className="text-sm text-neutral-500 dark:text-neutral-400">
          Evaluate product ingredient lists against the forbidden ingredients list.
        </p>
      </header>

      <nav className="mb-6 flex gap-1 border-b border-neutral-200 dark:border-neutral-800">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === id
                ? 'border-neutral-900 text-neutral-900 dark:border-neutral-100 dark:text-neutral-100'
                : 'border-transparent text-neutral-500 hover:text-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-200'
            }`}
          >
            {label}
            {id === 'results' && results.length > 0 && (
              <span className="ml-1.5 rounded-full bg-neutral-200 px-1.5 py-0.5 text-xs text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                {results.length}
              </span>
            )}
          </button>
        ))}
      </nav>

      <main>
        {tab === 'evaluate' && (
          <EvaluatePage onResults={addResults} onNavigateToResults={() => setTab('results')} />
        )}
        {tab === 'results' && <ResultsPage results={results} />}
        {tab === 'forbidden-list' && <ForbiddenListPage />}
      </main>
    </div>
  )
}

export default App
