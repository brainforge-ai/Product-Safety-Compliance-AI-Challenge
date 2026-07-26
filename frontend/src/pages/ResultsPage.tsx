import { Fragment, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { MatchList } from '../components/MatchList'
import { LlmUsageSummary } from '../components/LlmUsageSummary'
import type { ResultRow } from '../lib/resultRow'

export function ResultsPage({ results }: { results: ResultRow[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  if (results.length === 0) {
    return (
      <p className="text-sm text-neutral-500 dark:text-neutral-400">
        No evaluations yet. Run one from the Evaluate tab.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 dark:border-neutral-800">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="border-b border-neutral-200 bg-neutral-50 text-neutral-500 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400">
          <tr>
            <th className="px-4 py-2 font-medium">Source</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Reason</th>
          </tr>
        </thead>
        <tbody>
          {results.map((row) => {
            const isOpen = expanded.has(row.key)
            const canExpand = row.matches.length > 0 || !!row.llmUsage
            return (
              <Fragment key={row.key}>
                <tr
                  className={`border-b border-neutral-100 last:border-0 dark:border-neutral-900 ${
                    canExpand ? 'cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-900' : ''
                  }`}
                  onClick={() => canExpand && toggle(row.key)}
                >
                  <td className="px-4 py-3 align-top">
                    <div className="font-medium">{row.source}</div>
                    {row.productId && (
                      <div className="text-xs text-neutral-400">{row.productId}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-3 align-top">
                    {row.status === 'Error' ? (
                      <span className="text-red-600 dark:text-red-400">{row.error}</span>
                    ) : (
                      <span>
                        {row.reason.length > 0 ? (
                          row.reason.join(', ')
                        ) : (
                          <span className="text-neutral-400">—</span>
                        )}
                        {canExpand && (
                          <span className="ml-2 text-xs text-neutral-400">
                            {isOpen ? '▲ hide details' : '▼ show details'}
                          </span>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-b border-neutral-100 bg-neutral-50/60 dark:border-neutral-900 dark:bg-neutral-900/40">
                    <td colSpan={3} className="px-4 py-3">
                      <MatchList matches={row.matches} />
                      {row.llmUsage && <LlmUsageSummary usage={row.llmUsage} />}
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
