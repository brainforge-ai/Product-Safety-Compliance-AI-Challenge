// Mirrors the backend's Pydantic schemas (app/domain/models.py,
// app/api/schemas/*.py) by hand -- the project has no OpenAPI codegen step,
// so these must be kept in sync manually when the backend contract changes.

export type MatchMethod = 'exact' | 'formula' | 'fuzzy' | 'acronym' | 'embedding' | 'llm'

export interface MatchResult {
  forbidden_ingredient: string
  matched_text: string
  method: MatchMethod
  confidence: number
}

// Token usage/cost for the Gemini calls made while producing one
// evaluation (tier 6 matching and/or the LLM extraction fallback). The cost
// fields are null when pricing data wasn't available for the model, rather
// than a guessed number -- see backend app/infra/llm/usage.py.
export interface LlmUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_usd: number | null
  output_cost_usd: number | null
  estimated_cost_usd: number | null
}

export interface EvaluationResult {
  product_name: string
  status: 'Accepted' | 'Rejected'
  reason: string[]
  matches: MatchResult[]
  llm_usage: LlmUsage | null
}

export interface BatchItemResult {
  filename: string
  product_id: string | null
  status: 'ok' | 'error'
  result: EvaluationResult | null
  error: string | null
}

export interface BatchEvaluationResponse {
  results: BatchItemResult[]
}

// /evaluate returns EvaluationResult | BatchEvaluationResponse depending on
// whether the request resolved to exactly one product; the two shapes are
// distinguishable by the presence of `results`.
export function isBatchEvaluationResponse(
  response: EvaluationResult | BatchEvaluationResponse,
): response is BatchEvaluationResponse {
  return 'results' in response
}

export interface ForbiddenListResponse {
  ingredients: string[]
}
