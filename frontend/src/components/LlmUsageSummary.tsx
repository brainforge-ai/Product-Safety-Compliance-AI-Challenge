import type { LlmUsage } from '../api/types'

function formatCost(cost: number): string {
  return cost < 0.01 ? `$${cost.toFixed(6)}` : `$${cost.toFixed(4)}`
}

export function LlmUsageSummary({
  usage,
  hasLlmMatch,
}: {
  usage: LlmUsage
  hasLlmMatch: boolean
}) {
  return (
    <section
      aria-label="Supplemental LLM review"
      className="mt-3 rounded-md border border-neutral-200 bg-white/70 px-3 py-2.5 text-xs dark:border-neutral-700 dark:bg-neutral-950/40"
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold text-neutral-700 dark:text-neutral-200">
          Supplemental LLM review
        </span>
        <span className="text-neutral-300 dark:text-neutral-600" aria-hidden="true">
          ·
        </span>
        <span className="text-neutral-500 dark:text-neutral-400">
          {usage.total_tokens.toLocaleString()} tokens
        </span>
        <span className="text-neutral-300 dark:text-neutral-600" aria-hidden="true">
          ·
        </span>
        <span className="text-neutral-500 dark:text-neutral-400">
          {usage.estimated_cost_usd != null
            ? `${formatCost(usage.estimated_cost_usd)} estimated cost`
            : 'cost unavailable'}
        </span>
      </div>
      <p className="mt-1 text-neutral-500 dark:text-neutral-400">
        {hasLlmMatch
          ? 'The LLM contributed a match to this decision; see the LLM-tagged match above.'
          : 'No LLM match contributed to this decision. This usage reflects supplemental analysis, not the method that determined the status.'}
      </p>
    </section>
  )
}
