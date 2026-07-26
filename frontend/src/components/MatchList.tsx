import type { MatchResult } from '../api/types'

export function MatchList({ matches }: { matches: MatchResult[] }) {
  if (matches.length === 0) return null

  return (
    <ul className="space-y-1.5 text-sm">
      {matches.map((match, index) => (
        <li key={index} className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium text-neutral-800 dark:text-neutral-200">
            {match.matched_text}
          </span>
          <span className="text-neutral-400">matches forbidden</span>
          <span className="font-medium text-neutral-800 dark:text-neutral-200">
            {match.forbidden_ingredient}
          </span>
          <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
            {match.method}
          </span>
          <span className="text-xs text-neutral-400">
            {Math.round(match.confidence * 100)}% confidence
          </span>
        </li>
      ))}
    </ul>
  )
}
