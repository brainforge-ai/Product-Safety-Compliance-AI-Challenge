import { useState } from 'react'
import { useForbiddenList, useReplaceForbiddenList } from '../api/hooks'

export function ForbiddenListPage() {
  const { data, isLoading, isError, error } = useForbiddenList()
  const replaceList = useReplaceForbiddenList()
  const [file, setFile] = useState<File | null>(null)

  function handleUpload() {
    if (!file) return
    replaceList.mutate(file, {
      onSuccess: () => setFile(null),
    })
  }

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
        <h2 className="mb-1 text-lg font-medium">Replace forbidden ingredients list</h2>
        <p className="mb-4 text-sm text-neutral-500 dark:text-neutral-400">
          Upload a CSV with an ingredient name in the first column. Replaces the active list
          used by every future evaluation.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            key={file ? file.name : 'empty'}
            type="file"
            accept=".csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-sm text-neutral-600 file:mr-3 file:rounded-md file:border-0 file:bg-neutral-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-neutral-700 dark:text-neutral-400 dark:file:bg-neutral-100 dark:file:text-neutral-900"
          />
          <button
            type="button"
            onClick={handleUpload}
            disabled={!file || replaceList.isPending}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {replaceList.isPending ? 'Uploading…' : 'Upload replacement list'}
          </button>
        </div>
        {replaceList.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">
            {(replaceList.error as Error).message}
          </p>
        )}
        {replaceList.isSuccess && (
          <p className="mt-3 text-sm text-green-600 dark:text-green-400">
            Forbidden list replaced.
          </p>
        )}
      </section>

      <section className="rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
        <h2 className="mb-3 text-lg font-medium">
          Current forbidden ingredients {data ? `(${data.ingredients.length})` : ''}
        </h2>
        {isLoading && <p className="text-sm text-neutral-500 dark:text-neutral-400">Loading…</p>}
        {isError && (
          <p className="text-sm text-red-600 dark:text-red-400">{(error as Error).message}</p>
        )}
        {data && data.ingredients.length === 0 && (
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            No forbidden ingredients loaded.
          </p>
        )}
        {data && data.ingredients.length > 0 && (
          <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
            {data.ingredients.map((ingredient) => (
              <li key={ingredient} className="truncate text-neutral-700 dark:text-neutral-300">
                {ingredient}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
