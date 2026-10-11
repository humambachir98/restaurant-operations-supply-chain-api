import axios from 'axios'

// Override with VITE_API_URL in frontend/.env.local, e.g. for a deployed backend.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 10_000,
})

/** A readable message for a failed request, using FastAPI's `detail` when there is one. */
export function errorMessage(err) {
  if (!err.response) return `Can't reach the API at ${API_URL}. Is the backend running?`
  const { detail } = err.response.data ?? {}
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ') // 422 validation errors
  return `The API returned ${err.response.status}.`
}

export default api
