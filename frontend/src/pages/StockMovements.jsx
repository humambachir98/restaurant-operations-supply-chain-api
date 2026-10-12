import { ArrowDownLeft, ArrowUpRight, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import Banner from '../components/Banner.jsx'
import ItemSelect, { fieldClass } from '../components/ItemSelect.jsx'
import Segmented from '../components/Segmented.jsx'
import { formatDateTime, formatNumber as fmt, formatSigned, todayInBerlin } from '../format.js'
import { useFetch } from '../useFetch.js'

const PERIODS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
]

const parseAmount = (text) => Number(text.trim().replace(',', '.'))

function SubmitButton({ busy, disabled, children }) {
  return (
    <button
      type="submit"
      disabled={disabled || busy}
      className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
    >
      {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
}

function WasteForm({ items, onDone }) {
  const empty = { itemId: '', amount: '', period: 'daily', reason: '' }
  const [form, setForm] = useState(empty)
  const [busy, setBusy] = useState(false)
  const item = items?.find((i) => String(i.id) === form.itemId)
  const amount = parseAmount(form.amount)
  const valid = item && amount > 0 && form.reason.trim()

  async function submit(event) {
    event.preventDefault()
    if (!valid) return
    setBusy(true)
    try {
      const { data } = await api.post('/waste/', {
        item_id: item.id, quantity: amount, audit_type: form.period, reason: form.reason.trim(),
      })
      setForm(empty)
      onDone({ tone: 'success', title: 'Waste logged.', detail: `${data.item_name}: −${fmt(data.quantity)} ${data.unit} deducted from stock.` })
    } catch (err) {
      onDone({ tone: 'error', title: "Couldn't log the waste.", detail: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="waste-form">
      <h2 id="waste-form" className="flex items-center gap-2 font-semibold">
        <Trash2 className="size-5 text-red-600" aria-hidden="true" />
        Log waste
      </h2>
      <div className="mt-4 space-y-4">
        <ItemSelect items={items} value={form.itemId} onChange={(itemId) => setForm({ ...form, itemId })} />
        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm font-medium">
            Quantity{item && <span className="font-normal text-slate-400"> ({item.unit})</span>}
            <input
              type="text"
              inputMode="decimal"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              placeholder="e.g. 2,5"
              className={`${fieldClass} text-right tabular-nums`}
            />
          </label>
          <div className="text-sm font-medium">
            Period
            <div>
              <Segmented label="Period" options={PERIODS} value={form.period} onChange={(period) => setForm({ ...form, period })} />
            </div>
          </div>
        </div>
        <label className="block text-sm font-medium">
          Reason
          <input
            type="text"
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            maxLength={500}
            placeholder="e.g. Fries held past 7 minutes"
            className={fieldClass}
          />
        </label>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{item && amount > 0 ? `Stock: ${fmt(item.quantity)} → ${fmt(item.quantity - amount)} ${item.unit}` : ' '}</p>
        <SubmitButton busy={busy} disabled={!valid}>Log waste</SubmitButton>
      </div>
    </form>
  )
}

function TransferForm({ items, onDone }) {
  const empty = { itemId: '', amount: '', direction: 'out', store: '' }
  const [form, setForm] = useState(empty)
  const [busy, setBusy] = useState(false)
  const item = items?.find((i) => String(i.id) === form.itemId)
  const amount = parseAmount(form.amount)
  const valid = item && amount > 0 && form.store.trim()
  const change = form.direction === 'in' ? amount : -amount

  async function submit(event) {
    event.preventDefault()
    if (!valid) return
    setBusy(true)
    try {
      const { data } = await api.post('/transfers/', {
        item_id: item.id, quantity: amount, direction: form.direction, target_store_name: form.store.trim(),
      })
      setForm(empty)
      onDone({
        tone: 'success',
        title: 'Transfer recorded.',
        detail: `${data.item_name}: ${formatSigned(data.stock_change)} ${data.unit} (${data.direction === 'in' ? 'from' : 'to'} ${data.target_store_name}).`,
      })
    } catch (err) {
      onDone({ tone: 'error', title: "Couldn't record the transfer.", detail: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="transfer-form">
      <h2 id="transfer-form" className="flex items-center gap-2 font-semibold">
        <ArrowUpRight className="size-5 text-indigo-600" aria-hidden="true" />
        Store transfer
      </h2>
      <div className="mt-4 space-y-4">
        <ItemSelect items={items} value={form.itemId} onChange={(itemId) => setForm({ ...form, itemId })} />
        <div className="grid grid-cols-2 gap-4">
          <div className="text-sm font-medium">
            Direction
            <div>
              <Segmented
                label="Direction"
                value={form.direction}
                onChange={(direction) => setForm({ ...form, direction })}
                options={[
                  { value: 'out', label: 'Send out' },
                  { value: 'in', label: 'Receive in' },
                ]}
              />
            </div>
          </div>
          <label className="block text-sm font-medium">
            Quantity{item && <span className="font-normal text-slate-400"> ({item.unit})</span>}
            <input
              type="text"
              inputMode="decimal"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              placeholder="e.g. 30"
              className={`${fieldClass} text-right tabular-nums`}
            />
          </label>
        </div>
        <label className="block text-sm font-medium">
          {form.direction === 'out' ? 'To store' : 'From store'}
          <input
            type="text"
            value={form.store}
            onChange={(e) => setForm({ ...form, store: e.target.value })}
            maxLength={100}
            placeholder="e.g. Berlin Alexanderplatz"
            className={fieldClass}
          />
        </label>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{item && amount > 0 ? `Stock: ${fmt(item.quantity)} → ${fmt(item.quantity + change)} ${item.unit}` : ' '}</p>
        <SubmitButton busy={busy} disabled={!valid}>Record transfer</SubmitButton>
      </div>
    </form>
  )
}

export default function StockMovements() {
  const [notice, setNotice] = useState(null)
  const today = todayInBerlin()
  const items = useFetch('/inventory/')
  const waste = useFetch('/waste/', { params: { on: today } })
  const transfers = useFetch('/transfers/', { params: { limit: 10 } })

  function done(result) {
    setNotice(result)
    if (result.tone === 'success') {
      items.reload()
      waste.reload()
      transfers.reload()
    }
  }

  const loadError = items.error || waste.error || transfers.error

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Inventory</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Waste &amp; Transfers</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Stock that leaves without being sold, or moves between stores. Each entry updates stock immediately.
        </p>
      </header>

      {loadError && <Banner tone="error" title="Couldn't load inventory data.">{loadError}</Banner>}
      {notice && (
        <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
          {notice.detail}
        </Banner>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <WasteForm items={items.data} onDone={done} />
        <TransferForm items={items.data} onDone={done} />
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="waste-today">
          <h2 id="waste-today" className="font-semibold">
            Waste today {waste.data?.length > 0 && <span className="font-normal text-slate-500">· {waste.data.length}</span>}
          </h2>
          <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm shadow-sm">
            {waste.data?.length === 0 && <li className="px-4 py-6 text-center text-slate-500">Nothing wasted today.</li>}
            {waste.data?.map((w) => (
              <li key={w.id} className="flex items-start justify-between gap-3 px-4 py-2.5">
                <div className="min-w-0">
                  <p className="font-medium">{w.item_name}</p>
                  <p className="truncate text-slate-500">{w.reason}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="tabular-nums text-red-700">−{fmt(w.quantity)} {w.unit}</p>
                  <p className="text-xs text-slate-400">{w.audit_type} · {formatDateTime(w.created_at)}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="recent-transfers">
          <h2 id="recent-transfers" className="font-semibold">Recent transfers</h2>
          <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm shadow-sm">
            {transfers.data?.length === 0 && <li className="px-4 py-6 text-center text-slate-500">No transfers yet.</li>}
            {transfers.data?.map((t) => {
              const incoming = t.direction === 'in'
              const Icon = incoming ? ArrowDownLeft : ArrowUpRight
              return (
                <li key={t.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <div className="flex min-w-0 items-center gap-2">
                    <Icon className={`size-4 shrink-0 ${incoming ? 'text-emerald-600' : 'text-amber-600'}`} aria-hidden="true" />
                    <div className="min-w-0">
                      <p className="font-medium">{t.item_name}</p>
                      <p className="truncate text-slate-500">{incoming ? 'from' : 'to'} {t.target_store_name}</p>
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className={`tabular-nums ${incoming ? 'text-emerald-700' : 'text-amber-700'}`}>
                      {formatSigned(t.stock_change)} {t.unit}
                    </p>
                    <p className="text-xs text-slate-400">{formatDateTime(t.created_at)}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      </div>
    </>
  )
}
