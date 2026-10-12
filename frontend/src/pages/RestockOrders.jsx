import { AlertTriangle, Check, ListPlus, Loader2, Plus, Send, ShoppingCart, Trash2, Truck } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import Banner from '../components/Banner.jsx'
import ItemSelect, { fieldClass } from '../components/ItemSelect.jsx'
import { formatDate, formatNumber as fmt } from '../format.js'
import { useFetch } from '../useFetch.js'

const digitsOnly = (text) => text.replace(/\D/g, '')

function AlertsPanel({ alerts, suggestions, draftPacks, onAdd, onAddAll }) {
  const suggestionFor = Object.fromEntries((suggestions.data?.items ?? []).map((s) => [s.item_id, s]))
  const addable = (alerts.data ?? []).filter((a) => suggestionFor[a.id] && draftPacks(a.id) !== suggestionFor[a.id].packs)
  const loading = alerts.loading || suggestions.loading

  return (
    <aside className="rounded-2xl border border-amber-200 bg-amber-50/50 p-4 shadow-sm lg:sticky lg:top-20" aria-labelledby="alerts-heading">
      <div className="flex items-center justify-between gap-2">
        <h2 id="alerts-heading" className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="size-5 text-amber-600" aria-hidden="true" />
          Low stock alerts
          {alerts.data?.length > 0 && <span className="font-normal text-slate-500">· {alerts.data.length}</span>}
        </h2>
        {addable.length > 1 && (
          <button
            type="button"
            onClick={() => onAddAll(addable.map((a) => suggestionFor[a.id]))}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
          >
            <ListPlus className="size-4" aria-hidden="true" />
            Add all
          </button>
        )}
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Suggestions top up to twice the reorder level, minus deliveries on the way, in whole packs.
      </p>

      {(alerts.error || suggestions.error) && (
        <Banner tone="error" title="Couldn't load alerts." className="mt-3">{alerts.error || suggestions.error}</Banner>
      )}
      {loading && !alerts.data && <div className="mt-3 h-24 animate-pulse rounded-xl bg-white" />}
      {alerts.data?.length === 0 && (
        <p className="mt-3 rounded-xl bg-white px-3 py-4 text-center text-sm text-slate-500">All items are above their reorder level.</p>
      )}

      <ul className="mt-3 space-y-2">
        {alerts.data?.map((item) => {
          const suggestion = suggestionFor[item.id]
          const inDraft = draftPacks(item.id)
          const matches = suggestion && inDraft === suggestion.packs
          const fill = Math.max(0, Math.min(100, (item.quantity / item.reorder_level) * 100))
          return (
            <li key={item.id} className="rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-medium">{item.name}</p>
                <p className={`text-sm tabular-nums ${item.quantity < 0 ? 'font-semibold text-red-700' : 'text-slate-600'}`}>
                  {fmt(item.quantity)} / {fmt(item.reorder_level)} {item.unit}
                </p>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
                <div className={`h-full rounded-full ${item.quantity < 0 ? 'bg-red-500' : 'bg-amber-500'}`} style={{ width: `${fill}%` }} />
              </div>
              <div className="mt-2 flex items-center justify-between gap-2 text-sm">
                {suggestion ? (
                  <>
                    <span className="text-slate-600">
                      Suggested <span className="font-semibold text-slate-900">{suggestion.packs} packs</span>{' '}
                      <span className="text-slate-400">({fmt(suggestion.quantity)} {suggestion.unit})</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => onAdd(suggestion)}
                      disabled={matches}
                      className={`inline-flex shrink-0 items-center gap-1 rounded-md px-2.5 py-1 text-sm font-medium transition ${
                        matches ? 'text-emerald-700' : 'bg-indigo-600 text-white hover:bg-indigo-500'
                      }`}
                    >
                      {matches ? <Check className="size-4" aria-hidden="true" /> : <Plus className="size-4" aria-hidden="true" />}
                      {matches ? 'In order' : inDraft ? `Set to ${suggestion.packs}` : 'Add to Order'}
                    </button>
                  </>
                ) : suggestions.loading ? (
                  <span className="text-slate-400">Calculating…</span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-slate-500">
                    <Truck className="size-4" aria-hidden="true" /> Covered by deliveries on the way
                  </span>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </aside>
  )
}

export default function RestockOrders() {
  const items = useFetch('/inventory/')
  const alerts = useFetch('/inventory/low-stock')
  const suggestions = useFetch('/purchase-orders/auto-suggest', { method: 'post' })
  const pending = useFetch('/purchase-orders/', { params: { status: 'pending' } })

  const [lines, setLines] = useState([]) // [{ itemId, packs: string }] in the order they were added
  const [pick, setPick] = useState({ itemId: '', packs: '1' })
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const itemsById = Object.fromEntries((items.data ?? []).map((i) => [i.id, i]))
  const draftPacks = (itemId) => {
    const line = lines.find((l) => l.itemId === itemId)
    return line ? Number(line.packs || 0) : 0
  }

  /** Put `packs` of an item in the draft: added to an existing line, or replacing it. */
  function upsert(itemId, packs, mode) {
    setLines((prev) => {
      const existing = prev.find((l) => l.itemId === itemId)
      if (!existing) return [...prev, { itemId, packs: String(packs) }]
      const next = mode === 'add' ? Number(existing.packs || 0) + packs : packs
      return prev.map((l) => (l.itemId === itemId ? { ...l, packs: String(next) } : l))
    })
  }

  function addPicked(event) {
    event.preventDefault()
    const packs = Number(pick.packs)
    if (!pick.itemId || !(packs > 0)) return
    upsert(Number(pick.itemId), packs, 'add')
    setPick({ itemId: '', packs: '1' })
  }

  const orderLines = lines.map((l) => ({ item_id: l.itemId, packs: Number(l.packs || 0) })).filter((l) => l.packs > 0)
  const totalPacks = orderLines.reduce((sum, l) => sum + l.packs, 0)

  async function submit() {
    setSubmitting(true)
    setNotice(null)
    try {
      const { data: order } = await api.post('/purchase-orders/', { items: orderLines })
      setNotice({
        tone: 'success',
        title: `Order #${order.id} placed.`,
        detail: `${order.items.length} item${order.items.length === 1 ? '' : 's'}, ${totalPacks} pack${
          totalPacks === 1 ? '' : 's'
        }. Scheduled for automatic delivery on ${formatDate(order.expected_delivery_date)}.`,
      })
      setLines([])
      suggestions.reload() // the new order now counts as "on the way"
      pending.reload()
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't place the order.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Purchasing</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Restock Orders</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Build an order from any item, or add the suggested amounts from the low stock alerts. Orders are in whole
          supplier packs.
        </p>
      </header>

      {notice && (
        <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
          {notice.detail}
        </Banner>
      )}

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="builder-heading">
            <h2 id="builder-heading" className="flex items-center gap-2 font-semibold">
              <ShoppingCart className="size-5 text-indigo-600" aria-hidden="true" />
              Manual order builder
            </h2>

            <form onSubmit={addPicked} className="mt-4 grid gap-3 sm:grid-cols-[1fr_7rem_auto] sm:items-end">
              <ItemSelect
                items={items.data}
                value={pick.itemId}
                onChange={(itemId) => setPick({ ...pick, itemId })}
                describe={(item) => `${fmt(item.pack_size)} ${item.unit} / pack`}
              />
              <label className="block text-sm font-medium">
                Packs
                <input
                  type="text"
                  inputMode="numeric"
                  value={pick.packs}
                  onChange={(e) => setPick({ ...pick, packs: digitsOnly(e.target.value) })}
                  className={`${fieldClass} text-right tabular-nums`}
                />
              </label>
              <button
                type="submit"
                disabled={!pick.itemId || !(Number(pick.packs) > 0)}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50"
              >
                <Plus className="size-4" aria-hidden="true" />
                Add
              </button>
            </form>

            <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Item</th>
                      <th scope="col" className="px-4 py-3 text-right">Current stock</th>
                      <th scope="col" className="px-4 py-3 text-right">Packs</th>
                      <th scope="col" className="px-4 py-3 text-right">Total</th>
                      <th scope="col" className="px-2 py-3"><span className="sr-only">Remove</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {lines.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                          The draft is empty. Add items above or from the alerts.
                        </td>
                      </tr>
                    )}
                    {lines.map((line) => {
                      const item = itemsById[line.itemId]
                      const packs = Number(line.packs || 0)
                      if (!item) return null
                      return (
                        <tr key={line.itemId} className={packs === 0 ? 'text-slate-400' : ''}>
                          <td className="px-4 py-2.5 font-medium">{item.name}</td>
                          <td className={`px-4 py-2.5 text-right tabular-nums ${item.quantity < 0 ? 'text-red-700' : ''}`}>
                            {fmt(item.quantity)} <span className="text-slate-400">{item.unit}</span>
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <input
                              type="text"
                              inputMode="numeric"
                              value={line.packs}
                              onChange={(e) =>
                                setLines((prev) => prev.map((l) => (l.itemId === line.itemId ? { ...l, packs: digitsOnly(e.target.value) } : l)))
                              }
                              aria-label={`Packs of ${item.name}`}
                              className="w-20 rounded-md border border-slate-300 px-2 py-1 text-right font-semibold tabular-nums text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                            />
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-slate-600">
                            {packs} × {fmt(item.pack_size)} = {fmt(packs * item.pack_size)} {item.unit}
                          </td>
                          <td className="px-2 py-2.5 text-right">
                            <button
                              type="button"
                              onClick={() => setLines((prev) => prev.filter((l) => l.itemId !== line.itemId))}
                              className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"
                              aria-label={`Remove ${item.name}`}
                            >
                              <Trash2 className="size-4" />
                            </button>
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
                {orderLines.length} item{orderLines.length === 1 ? '' : 's'} ·{' '}
                <span className="font-medium text-slate-900">{totalPacks} packs</span>
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setLines([])}
                  disabled={lines.length === 0 || submitting}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium shadow-sm transition hover:bg-slate-100 disabled:opacity-50"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={submit}
                  disabled={orderLines.length === 0 || submitting}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:opacity-50"
                >
                  {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
                  Submit Final Order
                </button>
              </div>
            </div>
          </section>

          <section aria-labelledby="pending-heading">
            <h2 id="pending-heading" className="font-semibold">
              Upcoming deliveries
              {pending.data?.length > 0 && <span className="font-normal text-slate-500"> · {pending.data.length}</span>}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Received automatically at 06:00 on their delivery day. Report problems on the Complaints page.
            </p>
            {pending.error && <Banner tone="error" title="Couldn't load upcoming deliveries." className="mt-3">{pending.error}</Banner>}
            {pending.data?.length === 0 && (
              <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">
                No deliveries scheduled.
              </p>
            )}
            <ul className="mt-3 space-y-3">
              {pending.data?.map((order) => (
                <li key={order.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">
                      Order #{order.id}{' '}
                      <span className="font-normal text-slate-500">· {order.items.length} item{order.items.length === 1 ? '' : 's'}</span>
                    </p>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-inset ring-sky-600/20">
                      <Truck className="size-3.5" aria-hidden="true" />
                      Scheduled for automatic delivery on {formatDate(order.expected_delivery_date)}
                    </span>
                  </div>
                  <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
                    {order.items.map((l) => (
                      <li key={l.id}>
                        {l.item_name}{' '}
                        <span className="tabular-nums text-slate-400">{l.packs} × {fmt(l.pack_size)} {l.unit}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <AlertsPanel
          alerts={alerts}
          suggestions={suggestions}
          draftPacks={draftPacks}
          onAdd={(s) => upsert(s.item_id, s.packs, 'set')}
          onAddAll={(list) => list.forEach((s) => upsert(s.item_id, s.packs, 'set'))}
        />
      </div>
    </>
  )
}
