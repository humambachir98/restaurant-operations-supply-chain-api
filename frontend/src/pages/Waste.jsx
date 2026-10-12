import { Loader2, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import Banner from '../components/Banner.jsx'
import { formatDateTime, formatNumber as fmt, todayInBerlin } from '../format.js'
import { useFetch } from '../useFetch.js'

/** "2,5" or "2.5" -> 2.5; '' or 0 -> null (no waste); anything invalid -> NaN. */
function parseWaste(text) {
  const trimmed = (text ?? '').trim().replace(',', '.')
  if (trimmed === '') return null
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return NaN
  return Number(trimmed) === 0 ? null : Number(trimmed)
}

export default function Waste() {
  const items = useFetch('/inventory/')
  const today = useFetch('/waste/', { params: { on: todayInBerlin(), limit: 200 } })

  const [entries, setEntries] = useState({}) // item_id -> { qty, reason }
  const [search, setSearch] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const setEntry = (id, changes) => setEntries((prev) => ({ ...prev, [id]: { qty: '', reason: '', ...prev[id], ...changes } }))

  const all = items.data ?? []
  const term = search.trim().toLowerCase()
  const shown = term ? all.filter((item) => item.name.toLowerCase().includes(term)) : all

  const lines = all
    .map((item) => ({ item, value: parseWaste(entries[item.id]?.qty), reason: entries[item.id]?.reason ?? '' }))
    .filter(({ value }) => value !== null)
  const invalid = lines.filter(({ value }) => Number.isNaN(value))
  const hiddenBySearch = lines.filter(({ item }) => !shown.includes(item)).length
  const canSubmit = lines.length > 0 && invalid.length === 0 && !submitting

  async function submit() {
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const { data } = await api.post('/waste/', {
        items: lines.map(({ item, value, reason }) => ({ item_id: item.id, quantity: value, reason: reason.trim() || null })),
      })
      setNotice({
        tone: 'success',
        title: `Waste booked for ${data.length} item${data.length === 1 ? '' : 's'}.`,
        detail: 'Stock has been reduced accordingly.',
      })
      setEntries({})
      setSearch('')
      items.reload()
      today.reload()
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't book the waste. Nothing was changed.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">End of day</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Waste Booking</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Enter the amount wasted next to each item that had waste and leave the rest empty. Everything is booked in one go
          and deducted from stock.
        </p>
      </header>

      {notice && (
        <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
          {notice.detail}
        </Banner>
      )}
      {items.error && <Banner tone="error" title="Couldn't load the inventory.">{items.error}</Banner>}

      <div className="relative mt-6">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={`Search ${all.length || ''} items…`}
          aria-label="Search items"
          className="block w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 sm:w-80"
        />
      </div>

      <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">Item</th>
                <th scope="col" className="px-4 py-3 text-right">Stock</th>
                <th scope="col" className="px-4 py-3 text-right">Wasted</th>
                <th scope="col" className="px-4 py-3">Reason <span className="font-normal normal-case">(optional)</span></th>
                <th scope="col" className="px-4 py-3 text-right">New stock</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {!items.data &&
                Array.from({ length: 8 }, (_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 5 }, (_, j) => (
                      <td key={j} className="px-4 py-3.5">
                        <div className="h-4 rounded bg-slate-100" />
                      </td>
                    ))}
                  </tr>
                ))}
              {shown.map((item) => {
                const entry = entries[item.id] ?? { qty: '', reason: '' }
                const value = parseWaste(entry.qty)
                const bad = Number.isNaN(value)
                const active = value !== null && !bad
                return (
                  <tr key={item.id} className={active ? 'bg-red-50/60' : ''}>
                    <td className="px-4 py-2 font-medium">
                      {item.name}
                      {item.is_daily_tracked && (
                        <span className="ml-2 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-indigo-700">Key</span>
                      )}
                    </td>
                    <td className={`px-4 py-2 text-right tabular-nums ${item.quantity < 0 ? 'text-red-700' : 'text-slate-600'}`}>
                      {fmt(item.quantity)} <span className="text-slate-400">{item.unit}</span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-right">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={entry.qty}
                        onChange={(e) => setEntry(item.id, { qty: e.target.value })}
                        aria-label={`Wasted ${item.name} in ${item.unit}`}
                        aria-invalid={bad}
                        placeholder="0"
                        className={`w-20 rounded-md border px-2 py-1 text-right tabular-nums focus:outline-none focus:ring-2 ${
                          bad ? 'border-red-400 focus:ring-red-500/30' : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/30'
                        }`}
                      />
                      <span className="ml-1.5 inline-block w-8 text-left text-slate-400">{item.unit}</span>
                    </td>
                    <td className="px-4 py-2">
                      <input
                        type="text"
                        value={entry.reason}
                        onChange={(e) => setEntry(item.id, { reason: e.target.value })}
                        maxLength={500}
                        aria-label={`Reason for ${item.name} waste`}
                        placeholder={active ? 'e.g. Expired' : ''}
                        className="w-full min-w-40 rounded-md border border-slate-200 px-2 py-1 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                      />
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {bad ? (
                        <span className="text-red-700">invalid</span>
                      ) : active ? (
                        <span className={item.quantity - value < 0 ? 'text-red-700' : ''}>
                          {fmt(item.quantity - value)} <span className="text-slate-400">{item.unit}</span>
                        </span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
              {items.data && shown.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">No items match “{search}”.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="sticky bottom-0 z-10 -mx-4 mt-4 border-t border-slate-200 bg-slate-50/95 px-4 py-4 backdrop-blur sm:-mx-6 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-600">
            <span className="font-semibold text-slate-900">{lines.length - invalid.length}</span> item
            {lines.length - invalid.length === 1 ? '' : 's'} with waste
            {hiddenBySearch > 0 && <span className="text-slate-500"> ({hiddenBySearch} hidden by search)</span>}
            {invalid.length > 0 && <span className="text-red-700"> · {invalid.length} invalid (use numbers ≥ 0)</span>}
            {lines.length > 0 && (
              <button type="button" onClick={() => setEntries({})} className="ml-3 text-slate-500 underline-offset-2 hover:underline">
                Clear all
              </button>
            )}
          </p>
          <button
            type="button"
            onClick={submit}
            disabled={!canSubmit}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 px-6 py-3.5 text-base font-semibold text-white shadow-md transition hover:bg-red-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 disabled:opacity-50 sm:min-w-96"
          >
            {submitting ? <Loader2 className="size-5 animate-spin" aria-hidden="true" /> : <Trash2 className="size-5" aria-hidden="true" />}
            Submit End-of-Day Waste Booking
          </button>
        </div>
      </div>

      <section className="mt-10" aria-labelledby="booked-today">
        <h2 id="booked-today" className="font-semibold">
          Booked today {today.data?.length > 0 && <span className="font-normal text-slate-500">· {today.data.length}</span>}
        </h2>
        <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm shadow-sm">
          {today.data?.length === 0 && <li className="px-4 py-6 text-center text-slate-500">No waste booked today.</li>}
          {today.data?.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <div className="min-w-0">
                <p className="font-medium">{w.item_name}</p>
                {w.reason && <p className="truncate text-slate-500">{w.reason}</p>}
              </div>
              <div className="shrink-0 text-right">
                <p className="tabular-nums text-red-700">−{fmt(w.quantity)} {w.unit}</p>
                <p className="text-xs text-slate-400">{formatDateTime(w.created_at)}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
