import { CalendarClock, CheckCircle2, Loader2, PackageCheck, Send, Sparkles, X, XCircle } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import { formatDate, formatNumber as fmt } from '../format.js'

function Banner({ tone, Icon, title, children, onDismiss }) {
  const tones = {
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    error: 'border-red-200 bg-red-50 text-red-800',
  }
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`mt-6 flex items-start gap-3 rounded-xl border p-4 text-sm ${tones[tone]}`}>
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        {children && <p className="mt-1">{children}</p>}
      </div>
      <button type="button" onClick={onDismiss} className="rounded p-0.5 opacity-70 hover:opacity-100" aria-label="Dismiss">
        <X className="size-4" />
      </button>
    </div>
  )
}

export default function RestockOrders() {
  const [draft, setDraft] = useState(null) // response of POST /purchase-orders/auto-suggest
  const [packs, setPacks] = useState({}) // item_id -> packs as typed (digits only)
  const [busy, setBusy] = useState(null) // 'generating' | 'submitting' | null
  const [error, setError] = useState(null)
  const [placedOrder, setPlacedOrder] = useState(null)

  const packsFor = (itemId) => Number(packs[itemId] || 0)
  const orderLines = (draft?.items ?? [])
    .map((item) => ({ item_id: item.item_id, packs: packsFor(item.item_id) }))
    .filter((line) => line.packs > 0)
  const totalPacks = orderLines.reduce((sum, line) => sum + line.packs, 0)

  async function generate() {
    setBusy('generating')
    setError(null)
    setPlacedOrder(null)
    try {
      const { data } = await api.post('/purchase-orders/auto-suggest')
      setDraft(data)
      setPacks(Object.fromEntries(data.items.map((item) => [item.item_id, String(item.packs)])))
    } catch (err) {
      setError({ title: "Couldn't generate a restock order.", detail: errorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  async function submit() {
    setBusy('submitting')
    setError(null)
    try {
      const { data: order } = await api.post('/purchase-orders/', { items: orderLines })
      setPlacedOrder({ ...order, totalPacks })
      setDraft(null)
      setPacks({})
    } catch (err) {
      setError({ title: "Couldn't place the order.", detail: errorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Purchasing</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Restock Orders</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Drafts an order for every item at or below its reorder level. Each item is topped up to twice its reorder
          level, minus deliveries already on the way, then rounded up to whole supplier packs.
        </p>
      </header>

      <div className="mt-6 rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold">Smart restock</h2>
            <p className="mt-1 text-sm text-slate-600">Nothing is ordered until you review and submit the draft.</p>
          </div>
          <button
            type="button"
            onClick={generate}
            disabled={busy !== null}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-60"
          >
            {busy === 'generating' ? (
              <Loader2 className="size-5 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="size-5" aria-hidden="true" />
            )}
            Generate Smart Restock Order
          </button>
        </div>
      </div>

      {placedOrder && (
        <Banner tone="success" Icon={CheckCircle2} title={`Order #${placedOrder.id} placed.`} onDismiss={() => setPlacedOrder(null)}>
          {placedOrder.items.length} item{placedOrder.items.length === 1 ? '' : 's'}, {placedOrder.totalPacks} pack
          {placedOrder.totalPacks === 1 ? '' : 's'}. Expected delivery: {formatDate(placedOrder.expected_delivery_date)}.
        </Banner>
      )}

      {error && (
        <Banner tone="error" Icon={XCircle} title={error.title} onDismiss={() => setError(null)}>
          {error.detail}
        </Banner>
      )}

      {draft && draft.items.length === 0 && (
        <div className="mt-6 flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <PackageCheck className="size-10 text-emerald-500" aria-hidden="true" />
          <p className="mt-3 font-medium">Nothing to order</p>
          <p className="mt-1 text-sm text-slate-500">
            No item is at or below its reorder level, or pending deliveries already cover it.
          </p>
        </div>
      )}

      {draft && draft.items.length > 0 && (
        <section className="mt-6" aria-labelledby="draft-heading">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <h2 id="draft-heading" className="font-semibold">
              Draft order <span className="font-normal text-slate-500">· {draft.items.length} items</span>
            </h2>
            <p className="inline-flex items-center gap-1.5 text-sm text-slate-600">
              <CalendarClock className="size-4 text-slate-400" aria-hidden="true" />
              Delivery if placed now: <span className="font-medium text-slate-900">{formatDate(draft.expected_delivery_date)}</span>
            </p>
          </div>

          <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th scope="col" className="px-4 py-3">Item</th>
                    <th scope="col" className="px-4 py-3 text-right">Current stock</th>
                    <th scope="col" className="px-4 py-3 text-right">Reorder level</th>
                    <th scope="col" className="px-4 py-3 text-right">Suggested packs</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {draft.items.map((item) => {
                    const ordered = packsFor(item.item_id)
                    const edited = ordered !== item.packs
                    return (
                      <tr key={item.item_id} className={ordered === 0 ? 'bg-slate-50 text-slate-400' : ''}>
                        <td className="px-4 py-3 font-medium">{item.name}</td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          <span className={item.current_quantity < 0 ? 'font-semibold text-red-700' : ''}>
                            {fmt(item.current_quantity)}
                          </span>{' '}
                          <span className="text-slate-400">{item.unit}</span>
                          {item.on_order > 0 && (
                            <span className="block text-xs text-slate-500">
                              +{fmt(item.on_order)} {item.unit} on order
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {fmt(item.reorder_level)} <span className="text-slate-400">{item.unit}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="text"
                            inputMode="numeric"
                            value={packs[item.item_id] ?? ''}
                            onChange={(e) => setPacks((prev) => ({ ...prev, [item.item_id]: e.target.value.replace(/\D/g, '') }))}
                            aria-label={`Packs of ${item.name}`}
                            className="w-20 rounded-md border border-slate-300 px-2 py-1 text-right font-semibold tabular-nums text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                          />
                          <span className="mt-1 block text-xs text-slate-500 tabular-nums">
                            {ordered === 0
                              ? 'skipped'
                              : `× ${fmt(item.pack_size)} ${item.unit} = ${fmt(ordered * item.pack_size)} ${item.unit}`}
                            {edited && ` (suggested ${item.packs})`}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              {orderLines.length} of {draft.items.length} items · <span className="font-medium text-slate-900">{totalPacks} packs</span>
              {orderLines.length < draft.items.length && ' · items set to 0 are skipped'}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setDraft(null)}
                disabled={busy !== null}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium shadow-sm transition hover:bg-slate-100 disabled:opacity-60"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={busy !== null || orderLines.length === 0}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:opacity-60"
              >
                {busy === 'submitting' ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="size-4" aria-hidden="true" />
                )}
                Submit Final Order
              </button>
            </div>
          </div>
        </section>
      )}
    </>
  )
}
