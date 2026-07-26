import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  evaluateBatchSamples,
  evaluateFiles,
  getForbiddenIngredients,
  replaceForbiddenIngredients,
} from './client'

const FORBIDDEN_LIST_QUERY_KEY = ['forbidden-ingredients']

export function useEvaluateFiles() {
  return useMutation({ mutationFn: evaluateFiles })
}

export function useEvaluateBatchSamples() {
  return useMutation({ mutationFn: evaluateBatchSamples })
}

export function useForbiddenList() {
  return useQuery({ queryKey: FORBIDDEN_LIST_QUERY_KEY, queryFn: getForbiddenIngredients })
}

export function useReplaceForbiddenList() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: replaceForbiddenIngredients,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: FORBIDDEN_LIST_QUERY_KEY })
    },
  })
}
