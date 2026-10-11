import axios from 'axios'

// Override with VITE_API_URL in frontend/.env.local, e.g. for a deployed backend.
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 10_000,
})

export default api
