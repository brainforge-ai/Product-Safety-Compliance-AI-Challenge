import type { BatchItemResult, EvaluationResult, LlmUsage, MatchMethod, MatchResult } from '../api/types'

// A single row for the Results table, unifying the two shapes the backend
// returns (a bare EvaluationResult from /evaluate, a BatchItemResult -- which
// may itself be a per-file error -- from /evaluate/batch-samples) into one
// type the ResultsPage can render without caring which endpoint produced it.
export interface ResultRow {
  key: string
  source: string
  productId?: string | null
  status: 'Accepted' | 'Rejected' | 'Error'
  reason: string[]
  matches: MatchResult[]
  llmUsage?: LlmUsage | null
  error?: string | null
}

let nextRowId = 0

function makeKey(source: string): string {
  nextRowId += 1
  return `${source}-${nextRowId}`
}

export function fromSingleResult(source: string, result: EvaluationResult): ResultRow {
  return {
    key: makeKey(source),
    source,
    status: result.status,
    reason: result.reason,
    matches: result.matches,
    llmUsage: result.llm_usage,
  }
}

export function fromBatchItem(item: BatchItemResult): ResultRow {
  if (item.status === 'error' || !item.result) {
    return {
      key: makeKey(item.filename),
      source: item.filename,
      productId: item.product_id,
      status: 'Error',
      reason: [],
      matches: [],
      error: item.error,
    }
  }

  return {
    key: makeKey(item.filename),
    source: item.filename,
    productId: item.product_id,
    status: item.result.status,
    reason: item.result.reason,
    matches: item.result.matches,
    llmUsage: item.result.llm_usage,
  }
}

// The method(s) that determined this row's result, at a glance -- without
// having to expand the row. For a Rejected row this is the distinct set of
// tiers behind its matches. For an Accepted row there is no match to read a
// method off of; `llm_usage` is the only signal the LLM tier ran at all
// (tiers 1-5 leave no trace on a clean product), so that's the only case we
// can honestly report -- an Accepted row with no llm_usage shows no method.
export function methodsUsed(row: ResultRow): MatchMethod[] {
  if (row.matches.length > 0) {
    return [...new Set(row.matches.map((match) => match.method))]
  }
  if (row.llmUsage) {
    return ['llm']
  }
  return []
}
