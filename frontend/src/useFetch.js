import { useCallback, useEffect, useState } from 'react'

import api, { errorMessage } from './api.js'

/**
 * Load `path` from the API whenever it (or `params`) changes. `reload()` fetches again.
 * Returns { data, error, loading, reload }; `data` keeps the last result while reloading.
 */
export function useFetch(path, { params, method = 'get' } = {}) {
  const paramsKey = JSON.stringify(params ?? null)
  const [reloads, setReloads] = useState(0)
  const requestKey = `${method} ${path} ${paramsKey} ${reloads}`
  const [result, setResult] = useState({ key: null, data: null, error: null })

  useEffect(() => {
    const controller = new AbortController()
    api
      .request({ url: path, method, params: JSON.parse(paramsKey), signal: controller.signal })
      .then(({ data }) => setResult({ key: requestKey, data, error: null }))
      .catch((err) => {
        if (!controller.signal.aborted) setResult((prev) => ({ ...prev, key: requestKey, error: errorMessage(err) }))
      })
    return () => controller.abort()
  }, [path, method, paramsKey, requestKey])

  const reload = useCallback(() => setReloads((n) => n + 1), [])
  return { data: result.data, error: result.error, loading: result.key !== requestKey, reload }
}
