import type { BatchItemResult, EvaluationResult, MatchResult } from '../api/types'

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
  }
}
