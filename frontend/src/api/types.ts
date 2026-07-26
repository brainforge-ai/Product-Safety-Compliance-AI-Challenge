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

export interface EvaluationResult {
  product_name: string
  status: 'Accepted' | 'Rejected'
  reason: string[]
  matches: MatchResult[]
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

export interface ForbiddenListResponse {
  ingredients: string[]
}
