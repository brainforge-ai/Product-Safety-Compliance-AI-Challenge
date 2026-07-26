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

export async function evaluateFile(file: File): Promise<EvaluationResult> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/evaluate`, { method: 'POST', body: formData })
  return handleResponse<EvaluationResult>(response)
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
