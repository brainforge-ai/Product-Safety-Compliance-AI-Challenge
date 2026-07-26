import type {
  BatchEvaluationResponse,
  EvaluationResult,
  ForbiddenListResponse,
} from './types'

const API_BASE = '/api'

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

// The backend's single /evaluate endpoint accepts one or more files under
// the repeated "files" field, and returns a bare EvaluationResult when the
// request resolves to exactly one product, or the batch shape otherwise
// (see backend/app/api/routes_evaluate.py's evaluate() docstring).
export async function evaluateFiles(
  files: File[],
): Promise<EvaluationResult | BatchEvaluationResponse> {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }
  const response = await fetch(`${API_BASE}/evaluate`, { method: 'POST', body: formData })
  return handleResponse<EvaluationResult | BatchEvaluationResponse>(response)
}

export async function evaluateBatchSamples(): Promise<BatchEvaluationResponse> {
  const response = await fetch(`${API_BASE}/evaluate/batch-samples`, { method: 'POST' })
  return handleResponse<BatchEvaluationResponse>(response)
}

export async function getForbiddenIngredients(): Promise<ForbiddenListResponse> {
  const response = await fetch(`${API_BASE}/forbidden-ingredients`)
  return handleResponse<ForbiddenListResponse>(response)
}

export async function replaceForbiddenIngredients(file: File): Promise<ForbiddenListResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/forbidden-ingredients`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<ForbiddenListResponse>(response)
}
