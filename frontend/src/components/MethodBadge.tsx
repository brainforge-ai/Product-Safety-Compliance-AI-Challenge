import type { MatchMethod } from '../api/types'

export function MethodBadge({ method }: { method: MatchMethod }) {
  return (
    <span className="rounded bg-neutral-100 px-1.5 py-0.5 text-xs uppercase tracking-wide text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
      {method}
    </span>
  )
}
