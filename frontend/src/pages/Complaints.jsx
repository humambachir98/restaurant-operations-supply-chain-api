import { Ban, Check, ClipboardX, Loader2, Send } from 'lucide-react'
import { useEffect, useState } from 'react'

import api, { errorMessage } from '../api.js'
import Banner from '../components/Banner.jsx'
import { formatDateTime, formatNumber as fmt, formatSigned } from '../format.js'

const RECENT_ORDERS = 10
const EMPTY_FORM = { orderId: '', itemId: '', kind: 'missing', amount: '', unitMode: 'packs', notes: '' }

const inputClass =
  'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:bg-slate-50 disabled:text-slate-400'

function Segmented({ label, options, value, onChange }) {
  return (
    <div role="radiogroup" aria-label={label} className="mt-1 inline-flex rounded-lg border border-slate-300 bg-slate-50 p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            value === option.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default function Complaints() {
  const [orders, setOrders] = useState(null) // recent received orders; null while loading
  const [complaints, setComplaints] = useState(null)
  const [complaintsKey, setComplaintsKey] = useState(0) // bump to reload complaints
  const [loadError, setLoadError] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [deciding, setDeciding] = useState(null) // id of the complaint being approved/rejected
  const [notice, setNotice] = useState(null) // { tone, title, detail }

  useEffect(() => {
    const controller = new AbortController()
    api
      .get('/purchase-orders/', { params: { status: 'received' }, signal: controller.signal })
      .then(({ data }) => {
        const newest = [...data].sort((a, b) => new Date(b.received_at) - new Date(a.received_at))
        setOrders(newest.slice(0, RECENT_ORDERS))
      })
      .catch((err) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(err))
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api
      .get('/complaints/', { signal: controller.signal })
      .then(({ data }) => setComplaints(data))
      .catch((err) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(err))
      })
    return () => controller.abort()
  }, [complaintsKey])

  const update = (changes) => setForm((prev) => ({ ...prev, ...changes }))

  const order = orders?.find((o) => String(o.id) === form.orderId)
  const line = order?.items.find((l) => String(l.item_id) === form.itemId)
  const amount = Number(form.amount)
  const units = line ? amount * (form.unitMode === 'packs' ? line.pack_size : 1) : 0
  const difference = form.kind === 'missing' ? -units : units
  const exceedsDelivery = line && form.kind === 'missing' && units > line.quantity
  const canSubmit = line && amount > 0 && !exceedsDelivery && form.notes.trim() && !submitting

  async function submit(event) {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const { data } = await api.post('/complaints/', {
        order_id: order.id,
        item_id: line.item_id,
        quantity_difference: difference,
        notes: form.notes.trim(),
      })
      setNotice({
        tone: 'success',
        title: `Complaint #${data.id} filed.`,
        detail: `${data.item_name}: ${formatSigned(data.quantity_difference)} ${data.unit}, waiting for approval.`,
      })
      setForm(EMPTY_FORM)
      setComplaintsKey((key) => key + 1)
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't file the complaint.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  async function decide(complaint, action) {
    setDeciding(complaint.id)
    setNotice(null)
    try {
      await api.post(`/complaints/${complaint.id}/${action}`)
      if (action === 'approve') {
        const { data: item } = await api.get(`/inventory/${complaint.item_id}`)
        setNotice({
          tone: 'success',
          title: `Complaint #${complaint.id} approved.`,
          detail: `${item.name} stock adjusted by ${formatSigned(complaint.quantity_difference)} ${item.unit}, now ${fmt(item.quantity)} ${item.unit}.`,
        })
      } else {
        setNotice({ tone: 'success', title: `Complaint #${complaint.id} rejected.`, detail: 'Stock unchanged.' })
      }
    } catch (err) {
      setNotice({ tone: 'error', title: `Couldn't ${action} complaint #${complaint.id}.`, detail: errorMessage(err) })
    } finally {
      setDeciding(null)
      setComplaintsKey((key) => key + 1)
    }
  }

  const pending = complaints?.filter((c) => c.status === 'pending') ?? []
  const resolved = complaints?.filter((c) => c.status !== 'pending').slice(0, 5) ?? []

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Deliveries</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Complaints</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Report missing, damaged or extra goods from a delivery (Reklamation). Stock is corrected once a complaint is
          approved.
        </p>
      </header>

      {loadError && <Banner tone="error" title="Couldn't load complaints data.">{loadError}</Banner>}
      {notice && (
        <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
          {notice.detail}
        </Banner>
      )}

      <form onSubmit={submit} className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm" aria-labelledby="new-complaint">
        <h2 id="new-complaint" className="flex items-center gap-2 font-semibold">
          <ClipboardX className="size-5 text-indigo-600" aria-hidden="true" />
          New complaint
        </h2>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium">
            Delivery
            <select
              value={form.orderId}
              onChange={(e) => update({ orderId: e.target.value, itemId: '' })}
              disabled={!orders?.length}
              className={inputClass}
            >
              <option value="">
                {orders === null ? 'Loading…' : orders.length ? 'Select a received order' : 'No received orders yet'}
              </option>
              {orders?.map((o) => (
                <option key={o.id} value={o.id}>
                  #{o.id} · received {formatDateTime(o.received_at)} · {o.items.length} item{o.items.length === 1 ? '' : 's'}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm font-medium">
            Item
            <select
              value={form.itemId}
              onChange={(e) => update({ itemId: e.target.value })}
              disabled={!order}
              className={inputClass}
            >
              <option value="">{order ? 'Select an item' : 'Select a delivery first'}</option>
              {order?.items.map((l) => (
                <option key={l.item_id} value={l.item_id}>
                  {l.item_name} · {l.packs} × {fmt(l.pack_size)} {l.unit} delivered
                </option>
              ))}
            </select>
          </label>

          <div className="text-sm font-medium">
            Problem
            <div>
              <Segmented
                label="Problem"
                value={form.kind}
                onChange={(kind) => update({ kind })}
                options={[
                  { value: 'missing', label: 'Missing / damaged' },
                  { value: 'extra', label: 'Extra delivered' },
                ]}
              />
            </div>
          </div>

          <div className="text-sm font-medium">
            <label htmlFor="complaint-amount">Quantity</label>
            <div className="mt-1 flex items-center gap-2">
              <input
                id="complaint-amount"
                type="number"
                min="0"
                step="any"
                inputMode="decimal"
                value={form.amount}
                onChange={(e) => update({ amount: e.target.value })}
                placeholder="e.g. 2"
                className={`${inputClass} mt-0 w-28 text-right tabular-nums`}
              />
              <Segmented
                label="Quantity unit"
                value={form.unitMode}
                onChange={(unitMode) => update({ unitMode })}
                options={[
                  { value: 'packs', label: 'packs' },
                  { value: 'units', label: line?.unit ?? 'units' },
                ]}
              />
            </div>
          </div>

          <label className="block text-sm font-medium sm:col-span-2">
            Notes
            <textarea
              value={form.notes}
              onChange={(e) => update({ notes: e.target.value })}
              rows={2}
              maxLength={500}
              placeholder="e.g. Squished buns due to bad pallets"
              className={inputClass}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className={`text-sm ${exceedsDelivery ? 'text-red-700' : 'text-slate-600'}`}>
            {!line || !(amount > 0)
              ? 'Select a delivery and item, then enter a quantity.'
              : exceedsDelivery
                ? `Only ${fmt(line.quantity)} ${line.unit} of ${line.item_name} were delivered.`
                : (
                  <>
                    When approved, {line.item_name} stock changes by{' '}
                    <span className={`font-semibold tabular-nums ${difference < 0 ? 'text-red-700' : 'text-emerald-700'}`}>
                      {formatSigned(difference)} {line.unit}
                    </span>
                    .
                  </>
                )}
          </p>
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
          >
            {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
            File complaint
          </button>
        </div>
      </form>

      <section className="mt-10" aria-labelledby="pending-complaints">
        <h2 id="pending-complaints" className="font-semibold">
          Pending complaints
          {pending.length > 0 && <span className="font-normal text-slate-500"> · {pending.length}</span>}
        </h2>

        {complaints === null && !loadError && (
          <div className="mt-3 h-20 animate-pulse rounded-xl border border-slate-200 bg-white" />
        )}
        {complaints !== null && pending.length === 0 && (
          <p className="mt-3 rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">
            No complaints waiting for a decision.
          </p>
        )}

        {pending.length > 0 && (
          <ul className="mt-3 divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            {pending.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="font-medium">
                    {c.item_name}{' '}
                    <span className={`tabular-nums ${c.quantity_difference < 0 ? 'text-red-700' : 'text-emerald-700'}`}>
                      {formatSigned(c.quantity_difference)} {c.unit}
                    </span>
                  </p>
                  <p className="mt-0.5 text-sm text-slate-600">{c.notes}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    #{c.id} · order #{c.order_id} · filed {formatDateTime(c.created_at)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => decide(c, 'reject')}
                    disabled={deciding !== null}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium shadow-sm transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    <Ban className="size-4" aria-hidden="true" />
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => decide(c, 'approve')}
                    disabled={deciding !== null}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {deciding === c.id ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Check className="size-4" aria-hidden="true" />
                    )}
                    Approve
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {resolved.length > 0 && (
        <section className="mt-8" aria-labelledby="recent-decisions">
          <h2 id="recent-decisions" className="text-sm font-semibold text-slate-500">Recent decisions</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {resolved.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-x-2 text-slate-600">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${
                    c.status === 'approved'
                      ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
                      : 'bg-slate-100 text-slate-600 ring-slate-500/20'
                  }`}
                >
                  {c.status}
                </span>
                {c.item_name} <span className="tabular-nums">{formatSigned(c.quantity_difference)} {c.unit}</span>
                <span className="text-xs text-slate-400">· #{c.id} · {formatDateTime(c.resolved_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
