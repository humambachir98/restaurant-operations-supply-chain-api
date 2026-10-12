import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, Check, Loader2, Plus, Search, Send, Trash2 } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import { VIEW_OPTIONS, currentMonth } from '../archive.js'
import ArchiveView, { ArchiveTable } from '../components/ArchiveView.jsx'
import Banner from '../components/Banner.jsx'
import ItemName from '../components/ItemName.jsx'
import { fieldClass } from '../components/ItemSelect.jsx'
import Modal from '../components/Modal.jsx'
import PdfButton from '../components/PdfButton.jsx'
import Segmented from '../components/Segmented.jsx'
import { formatDateTime, formatNumber as fmt, formatSigned, todayInBerlin } from '../format.js'
import { COUNTING_COLUMNS, COUNTING_HEAD, countingRows, downloadChecklist } from '../pdf.js'
import { useFetch } from '../useFetch.js'

const DIRECTIONS = [
  { value: 'out', label: 'Send out' },
  { value: 'in', label: 'Receive in' },
]

/** "2,5" or "2.5" -> 2.5; '' -> null; anything else (incl. 0) -> NaN. */
function parseQuantity(text) {
  const trimmed = text.trim().replace(',', '.')
  if (trimmed === '') return null
  return /^\d+(\.\d+)?$/.test(trimmed) && Number(trimmed) > 0 ? Number(trimmed) : NaN
}

function ItemPicker({ open, onClose, items, inList, onPick }) {
  const [search, setSearch] = useState('')
  const term = search.trim().toLowerCase()
  const shown = (items ?? []).filter((item) => item.name.toLowerCase().includes(term))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add items to the transfer"
      footer={
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">{inList.size} in the list</p>
          <button type="button" onClick={onClose} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500">
            Done
          </button>
        </div>
      }
    >
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search items…"
          aria-label="Search items"
          data-autofocus
          className="block w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
        />
      </div>
      <ul className="mt-3 divide-y divide-slate-100">
        {items === null && <li className="py-4 text-center text-sm text-slate-500">Loading…</li>}
        {items && shown.length === 0 && <li className="py-4 text-center text-sm text-slate-500">No items match.</li>}
        {shown.map((item) => {
          const added = inList.has(item.id)
          return (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onPick(item)}
                disabled={added}
                className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-2.5 text-left text-sm transition hover:bg-slate-50 disabled:cursor-default disabled:hover:bg-transparent"
              >
                <span>
                  <span className="font-medium">
                    <ItemName item={item} />
                  </span>
                  <span className="ml-2 tabular-nums text-slate-400">
                    {fmt(item.quantity)} {item.unit} in stock
                  </span>
                </span>
                {added ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700">
                    <Check className="size-4" aria-hidden="true" /> Added
                  </span>
                ) : (
                  <Plus className="size-4 text-indigo-600" aria-label="Add" />
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </Modal>
  )
}

function TransferArchive({ month, onMonthChange, itemsById }) {
  return (
    <ArchiveView
      path="/archive/transfers"
      month={month}
      onMonthChange={onMonthChange}
      noun="transfer list"
      summary={(batch) => {
        const out = batch.lines.filter((l) => l.direction === 'out').length
        return (
          <>
            <span>
              <span className="font-medium">{batch.target_store_name}</span>
              <span className="ml-2 text-slate-500">{formatDateTime(batch.created_at)}</span>
            </span>
            <span className="text-slate-500">
              {out} out · {batch.lines.length - out} in
            </span>
          </>
        )
      }}
      details={(batch) => (
        <ArchiveTable
          head={[{ label: 'Item' }, { label: 'Direction' }, { label: 'Stock change', align: 'right' }]}
          rows={batch.lines.map((t) => {
            const incoming = t.direction === 'in'
            const Icon = incoming ? ArrowDownLeft : ArrowUpRight
            return (
              <tr key={t.id}>
                <td className="px-4 py-2 font-medium">
                  <ItemName item={itemsById[t.item_id]} name={t.item_name} />
                </td>
                <td className="px-4 py-2">
                  <span className={`inline-flex items-center gap-1 ${incoming ? 'text-emerald-700' : 'text-amber-700'}`}>
                    <Icon className="size-4" aria-hidden="true" />
                    {incoming ? 'Received in' : 'Sent out'}
                  </span>
                </td>
                <td className={`px-4 py-2 text-right tabular-nums ${incoming ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {formatSigned(t.stock_change)} {t.unit}
                </td>
              </tr>
            )
          })}
        />
      )}
    />
  )
}

export default function Transfers() {
  const [view, setView] = useState('active')
  const [month, setMonth] = useState(currentMonth)
  const items = useFetch('/inventory/')
  const recent = useFetch('/transfers/', { params: { limit: 15 } })

  const [list, setList] = useState([]) // [{ itemId, direction, qty }]
  const [store, setStore] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const itemsById = Object.fromEntries((items.data ?? []).map((i) => [i.id, i]))
  const updateLine = (itemId, changes) => setList((prev) => prev.map((l) => (l.itemId === itemId ? { ...l, ...changes } : l)))

  const parsed = list.map((line) => ({ ...line, value: parseQuantity(line.qty) }))
  const incomplete = parsed.filter((l) => l.value === null || Number.isNaN(l.value)).length
  const outCount = parsed.filter((l) => l.direction === 'out').length
  const canSubmit = list.length > 0 && incomplete === 0 && store.trim() && !submitting

  // The current list if there is one, otherwise every item: a sheet for counting what goes on the truck.
  const downloadPdf = () => {
    const listed = list.map((l) => itemsById[l.itemId]).filter(Boolean)
    return downloadChecklist({
      title: 'Store Transfer Checklist',
      subtitle: [store.trim() && `Other store: ${store.trim()}`, todayInBerlin()].filter(Boolean).join('  -  '),
      filename: `transfer-checklist-${todayInBerlin()}.pdf`,
      sections: [
        {
          head: COUNTING_HEAD,
          body: countingRows(listed.length ? listed : (items.data ?? [])),
          columnStyles: COUNTING_COLUMNS,
        },
      ],
    })
  }

  async function submit() {
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const { data } = await api.post('/transfers/', {
        target_store_name: store.trim(),
        items: parsed.map((l) => ({ item_id: l.itemId, quantity: l.value, direction: l.direction })),
      })
      setNotice({
        tone: 'success',
        title: `Transfer list with ${data[0].target_store_name} recorded.`,
        detail: `${data.length} item${data.length === 1 ? '' : 's'}; stock updated.`,
      })
      setList([])
      setStore('')
      items.reload()
      recent.reload()
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't record the transfer list. Nothing was changed.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Between stores</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Store Transfers</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Build a list of items moving to or from another store, then record it in one go. Each line updates stock.
        </p>
      </header>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="View" options={VIEW_OPTIONS} value={view} onChange={setView} />
        {view === 'active' && <PdfButton onDownload={downloadPdf} disabled={!items.data} />}
      </div>

      {view === 'archive' ? (
        <TransferArchive month={month} onMonthChange={setMonth} itemsById={itemsById} />
      ) : (
        <>
          {notice && (
            <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
              {notice.detail}
            </Banner>
          )}
          {items.error && <Banner tone="error" title="Couldn't load the inventory.">{items.error}</Banner>}

          <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-labelledby="builder-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="builder-heading" className="flex items-center gap-2 font-semibold">
                <ArrowLeftRight className="size-5 text-indigo-600" aria-hidden="true" />
                Current transfer list
                {list.length > 0 && <span className="font-normal text-slate-500">· {list.length}</span>}
              </h2>
              <button
                type="button"
                onClick={() => setPickerOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100"
              >
                <Plus className="size-4" aria-hidden="true" />
                Add Item
              </button>
            </div>

            <div className="mt-4 overflow-hidden rounded-xl border border-slate-200">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Item</th>
                      <th scope="col" className="px-4 py-3">Direction</th>
                      <th scope="col" className="px-4 py-3 text-right">Quantity</th>
                      <th scope="col" className="px-4 py-3 text-right">Stock after</th>
                      <th scope="col" className="px-2 py-3"><span className="sr-only">Remove</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {list.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                          The list is empty. Use <span className="font-medium">Add Item</span> to start.
                        </td>
                      </tr>
                    )}
                    {parsed.map((line) => {
                      const item = itemsById[line.itemId]
                      if (!item) return null
                      const bad = Number.isNaN(line.value)
                      const after = line.value > 0 ? item.quantity + (line.direction === 'in' ? line.value : -line.value) : null
                      return (
                        <tr key={line.itemId}>
                          <td className="px-4 py-2.5">
                            <p className="font-medium">
                              <ItemName item={item} />
                            </p>
                            <p className="text-xs tabular-nums text-slate-400">{fmt(item.quantity)} {item.unit} in stock</p>
                          </td>
                          <td className="px-4 py-2.5">
                            <Segmented
                              label={`Direction for ${item.name}`}
                              options={DIRECTIONS}
                              value={line.direction}
                              onChange={(direction) => updateLine(line.itemId, { direction })}
                            />
                          </td>
                          <td className="whitespace-nowrap px-4 py-2.5 text-right">
                            <input
                              type="text"
                              inputMode="decimal"
                              value={line.qty}
                              onChange={(e) => updateLine(line.itemId, { qty: e.target.value })}
                              aria-label={`Quantity of ${item.name} in ${item.unit}`}
                              aria-invalid={bad}
                              placeholder="0"
                              className={`w-20 rounded-md border px-2 py-1 text-right tabular-nums focus:outline-none focus:ring-2 ${
                                bad ? 'border-red-400 focus:ring-red-500/30' : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/30'
                              }`}
                            />
                            <span className="ml-1.5 inline-block w-8 text-left text-slate-400">{item.unit}</span>
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums">
                            {after === null ? (
                              <span className="text-slate-300">—</span>
                            ) : (
                              <span className={after < 0 ? 'text-red-700' : line.direction === 'in' ? 'text-emerald-700' : 'text-amber-700'}>
                                {fmt(after)} <span className="text-slate-400">{item.unit}</span>
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-2.5 text-right">
                            <button
                              type="button"
                              onClick={() => setList((prev) => prev.filter((l) => l.itemId !== line.itemId))}
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

            <div className="mt-5 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
              <label className="block text-sm font-medium">
                Other store <span className="font-normal text-slate-400">(applies to the whole list)</span>
                <input
                  type="text"
                  value={store}
                  onChange={(e) => setStore(e.target.value)}
                  maxLength={100}
                  placeholder="e.g. Berlin Alexanderplatz"
                  className={fieldClass}
                />
              </label>
              <button
                type="button"
                onClick={submit}
                disabled={!canSubmit}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
              >
                {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
                Submit Transfer List
              </button>
            </div>
            <p className="mt-2 text-sm text-slate-500">
              {list.length === 0
                ? 'Add at least one item.'
                : `${outCount} out · ${list.length - outCount} in${incomplete ? ` · ${incomplete} without a valid quantity` : ''}${
                    store.trim() ? '' : ' · enter the other store'
                  }`}
            </p>
          </section>

          <section className="mt-10" aria-labelledby="recent-transfers">
            <h2 id="recent-transfers" className="font-semibold">Recent transfers</h2>
            <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm shadow-sm">
              {recent.data?.length === 0 && <li className="px-4 py-6 text-center text-slate-500">No transfers yet.</li>}
              {recent.data?.map((t) => {
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
        </>
      )}

      <ItemPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        items={items.data}
        inList={new Set(list.map((l) => l.itemId))}
        onPick={(item) => setList((prev) => [...prev, { itemId: item.id, direction: 'out', qty: '' }])}
      />
    </>
  )
}
