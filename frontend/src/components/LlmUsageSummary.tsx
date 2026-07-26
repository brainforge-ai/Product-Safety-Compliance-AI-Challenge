import type { LlmUsage } from '../api/types'

function formatCost(cost: number): string {
  return cost < 0.01 ? `$${cost.toFixed(6)}` : `$${cost.toFixed(4)}`
}

export function LlmUsageSummary({ usage }: { usage: LlmUsage }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-neutral-400">
      <span className="rounded bg-indigo-50 px-1.5 py-0.5 font-medium uppercase tracking-wide text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300">
        llm
      </span>
      <span>{usage.total_tokens.toLocaleString()} tokens</span>
      <span className="text-neutral-300 dark:text-neutral-600">·</span>
      {usage.estimated_cost_usd != null ? (
        <span>{formatCost(usage.estimated_cost_usd)} estimated cost</span>
      ) : (
        <span>cost unavailable</span>
      )}
    </div>
  )
}
