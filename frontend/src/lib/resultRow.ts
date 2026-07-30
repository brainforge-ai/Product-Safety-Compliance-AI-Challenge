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

// The method(s) that produced a forbidden-ingredient match for this row.
// LLM usage alone is deliberately not a method: the model may have checked
// unresolved ingredients without contributing any match to the decision.
export function methodsUsed(row: ResultRow): MatchMethod[] {
  return [...new Set(row.matches.map((match) => match.method))]
}
