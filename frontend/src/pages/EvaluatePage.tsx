import { useState } from 'react'
import { useEvaluateBatchSamples, useEvaluateFiles } from '../api/hooks'
import { isBatchEvaluationResponse } from '../api/types'
import { fromBatchItem, fromSingleResult, type ResultRow } from '../lib/resultRow'

interface EvaluatePageProps {
  onResults: (rows: ResultRow[]) => void
  onNavigateToResults: () => void
}

export function EvaluatePage({ onResults, onNavigateToResults }: EvaluatePageProps) {
  const [files, setFiles] = useState<File[]>([])
  const evaluateFiles = useEvaluateFiles()
  const evaluateBatchSamples = useEvaluateBatchSamples()

  function handleEvaluate() {
    if (files.length === 0) return
    evaluateFiles.mutate(files, {
      onSuccess: (response) => {
        const rows = isBatchEvaluationResponse(response)
          ? response.results.map(fromBatchItem)
          : [fromSingleResult(files[0].name, response)]
        onResults(rows)
        onNavigateToResults()
      },
    })
  }

  function handleRunAllSamples() {
    evaluateBatchSamples.mutate(undefined, {
      onSuccess: (response) => {
        onResults(response.results.map(fromBatchItem))
        onNavigateToResults()
      },
    })
  }

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
        <h2 className="mb-1 text-lg font-medium">Evaluate product files</h2>
        <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
          Upload a PDF, image, text, or CSV file describing one product -- or select more than
          one file to evaluate them together as a batch.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            key={files.length === 0 ? 'empty' : files.map((f) => f.name).join(',')}
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.txt,.csv"
            onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
            className="text-sm text-neutral-600 file:mr-3 file:rounded-md file:border-0 file:bg-neutral-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-neutral-700 dark:text-neutral-400 dark:file:bg-neutral-100 dark:file:text-neutral-900"
          />
          <button
            type="button"
            onClick={handleEvaluate}
            disabled={files.length === 0 || evaluateFiles.isPending}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {evaluateFiles.isPending
              ? 'Evaluating…'
              : files.length > 1
                ? `Evaluate ${files.length} files`
                : 'Evaluate'}
          </button>
        </div>
        {evaluateFiles.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {(evaluateFiles.error as Error).message}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
        <h2 className="mb-1 text-lg font-medium">Run all sample products</h2>
        <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
          Evaluates every product listed in the backend's sample product index in one batch.
        </p>
        <button
          type="button"
          onClick={handleRunAllSamples}
          disabled={evaluateBatchSamples.isPending}
          className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium disabled:opacity-40 dark:border-neutral-700"
        >
          {evaluateBatchSamples.isPending ? 'Running…' : 'Run all samples'}
        </button>
        {evaluateBatchSamples.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {(evaluateBatchSamples.error as Error).message}
          </p>
        )}
      </section>
    </div>
  )
}
