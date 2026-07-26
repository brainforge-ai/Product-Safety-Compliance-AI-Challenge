import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  evaluateBatchSamples,
  evaluateFile,
  getForbiddenIngredients,
  replaceForbiddenIngredients,
} from './client'

const FORBIDDEN_LIST_QUERY_KEY = ['forbidden-ingredients']

export function useEvaluateFile() {
  return useMutation({ mutationFn: evaluateFile })
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
