import axios from 'axios'
import { AlertTriangle, CheckCircle2, Package, RefreshCw, TrendingDown, WifiOff } from 'lucide-react'
import { useEffect, useState } from 'react'

import api, { API_URL } from '../api.js'

const numberFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 })
const fmt = (value) => numberFormat.format(value)

// Mirrors the backend's low-stock rule: a reorder level of 0 means "not managed".
function stockStatus(item) {
  if (item.quantity < 0) return 'negative'
  if (item.reorder_level > 0 && item.quantity <= item.reorder_level) return 'low'
  return 'ok'
}

const STATUS = {
  negative: { label: 'Negative', className: 'bg-red-50 text-red-700 ring-red-600/20', Icon: TrendingDown },
  low: { label: 'Reorder', className: 'bg-amber-50 text-amber-800 ring-amber-600/20', Icon: AlertTriangle },
  ok: { label: 'In stock', className: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20', Icon: CheckCircle2 },
}

function StatusBadge({ status }) {
  const { label, className, Icon } = STATUS[status]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}>
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  )
}

function StatCard({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    api
      .get('/inventory/daily-items', { signal: controller.signal })
      .then(({ data }) => {
        setItems(data)
        setError(null)
        setLoading(false)
      })
      .catch((err) => {
        if (axios.isCancel(err)) return
        setError(err.response ? `The API returned ${err.response.status}.` : `Can't reach the API at ${API_URL}.`)
        setLoading(false)
      })
    return () => controller.abort()
  }, [reloadKey])

  const refresh = () => {
    setLoading(true)
    setError(null)
    setReloadKey((key) => key + 1)
  }

  const lowCount = items.filter((item) => stockStatus(item) === 'low').length
  const negativeCount = items.filter((item) => stockStatus(item) === 'negative').length

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-indigo-600">Daily count</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Key Items</h1>
            <p className="mt-1 text-sm text-slate-500">
              High-turnover items checked every day. Stock below zero is corrected by the next count.
            </p>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium shadow-sm transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Refresh
          </button>
        </header>

        <section className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3" aria-label="Summary">
          <StatCard label="Key items" value={loading ? '–' : items.length} />
          <StatCard label="At or below reorder level" value={loading ? '–' : lowCount} tone={lowCount ? 'text-amber-700' : undefined} />
          <StatCard label="Negative stock" value={loading ? '–' : negativeCount} tone={negativeCount ? 'text-red-700' : undefined} />
        </section>

        {error ? (
          <div role="alert" className="mt-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <WifiOff className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">Couldn't load the Key Items.</p>
              <p className="mt-1">{error} Is the backend running (<code className="font-mono">uvicorn app.main:app</code>)?</p>
              <button type="button" onClick={refresh} className="mt-2 font-medium underline underline-offset-2">
                Try again
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-3">Item</th>
                    <th scope="col" className="px-4 py-3 text-right">Stock</th>
                    <th scope="col" className="px-4 py-3 text-right">Reorder level</th>
                    <th scope="col" className="px-4 py-3 text-right">Pack size</th>
                    <th scope="col" className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading
                    ? Array.from({ length: 8 }, (_, i) => (
                        <tr key={i} className="animate-pulse">
                          {Array.from({ length: 5 }, (_, j) => (
                            <td key={j} className="px-4 py-3.5">
                              <div className="h-4 rounded bg-slate-100" />
                            </td>
                          ))}
                        </tr>
                      ))
                    : items.map((item) => {
                        const status = stockStatus(item)
                        return (
                          <tr key={item.id} className="transition hover:bg-slate-50">
                            <td className="px-4 py-3 font-medium">
                              <span className="inline-flex items-center gap-2">
                                <Package className="size-4 text-slate-400" aria-hidden="true" />
                                {item.name}
                              </span>
                            </td>
                            <td className={`px-4 py-3 text-right tabular-nums ${status === 'negative' ? 'font-semibold text-red-700' : ''}`}>
                              {fmt(item.quantity)} <span className="text-slate-400">{item.unit}</span>
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                              {fmt(item.reorder_level)} <span className="text-slate-400">{item.unit}</span>
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-slate-600">
                              {fmt(item.pack_size)} <span className="text-slate-400">{item.unit}</span>
                            </td>
                            <td className="px-4 py-3">
                              <StatusBadge status={status} />
                            </td>
                          </tr>
                        )
                      })}
                  {!loading && items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                        No Key Items yet. Run <code className="font-mono">python seed.py</code> in the project root.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
