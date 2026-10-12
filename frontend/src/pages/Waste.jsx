import { Loader2, Sandwich, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import { VIEW_OPTIONS, currentMonth } from '../archive.js'
import ArchiveView, { ArchiveTable } from '../components/ArchiveView.jsx'
import Banner from '../components/Banner.jsx'
import ItemName from '../components/ItemName.jsx'
import PdfButton from '../components/PdfButton.jsx'
import Segmented from '../components/Segmented.jsx'
import { formatDateTime, formatNumber as fmt, todayInBerlin } from '../format.js'
import { WASTE_COLUMNS, WASTE_HEAD, downloadChecklist, wasteRows } from '../pdf.js'
import { useFetch } from '../useFetch.js'

/** "2,5" or "2.5" -> 2.5; '' or 0 -> null (no waste); anything invalid -> NaN. */
function parseWaste(text) {
  const trimmed = (text ?? '').trim().replace(',', '.')
  if (trimmed === '') return null
  if (!/^\d+(\.\d+)?$/.test(trimmed)) return NaN
  return Number(trimmed) === 0 ? null : Number(trimmed)
}

/** Whole menu items only: "3" -> 3; '' or 0 -> null; anything else -> NaN. */
function parseCount(text) {
  const trimmed = (text ?? '').trim()
  if (trimmed === '') return null
  if (!/^\d+$/.test(trimmed)) return NaN
  return Number(trimmed) === 0 ? null : Number(trimmed)
}

const recipeText = (menuItem, times = 1) =>
  menuItem.ingredients.map((i) => `${fmt(i.quantity_needed * times)} ${i.unit === 'pcs' ? '×' : i.unit} ${i.item_name}`).join(' + ')

const inputClass = (bad) =>
  `w-20 rounded-md border px-2 py-1 text-right tabular-nums focus:outline-none focus:ring-2 ${
    bad ? 'border-red-400 focus:ring-red-500/30' : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/30'
  }`

const reasonClass =
  'w-full min-w-40 rounded-md border border-slate-200 px-2 py-1 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30'

const headClass = 'bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500'

function SkeletonRows({ rows, cols }) {
  return Array.from({ length: rows }, (_, i) => (
    <tr key={i} className="animate-pulse">
      {Array.from({ length: cols }, (_, j) => (
        <td key={j} className="px-4 py-3.5">
          <div className="h-4 rounded bg-slate-100" />
        </td>
      ))}
    </tr>
  ))
}

export default function Waste() {
  const items = useFetch('/inventory/')
  const menu = useFetch('/menu-items/')
  const today = useFetch('/waste/', { params: { on: todayInBerlin(), limit: 200 } })

  const [view, setView] = useState('active')
  const [month, setMonth] = useState(currentMonth)
  const [entries, setEntries] = useState({}) // item_id -> { qty, reason }
  const [menuEntries, setMenuEntries] = useState({}) // menu_item_id -> { qty, reason }
  const [search, setSearch] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const setEntry = (id, changes) => setEntries((prev) => ({ ...prev, [id]: { qty: '', reason: '', ...prev[id], ...changes } }))
  const setMenuEntry = (id, changes) =>
    setMenuEntries((prev) => ({ ...prev, [id]: { qty: '', reason: '', ...prev[id], ...changes } }))

  const all = items.data ?? []
  const itemsById = Object.fromEntries(all.map((i) => [i.id, i]))
  const menuItems = menu.data ?? []
  const term = search.trim().toLowerCase()
  const shown = term ? all.filter((item) => item.name.toLowerCase().includes(term)) : all

  const lines = all
    .map((item) => ({ item, value: parseWaste(entries[item.id]?.qty), reason: entries[item.id]?.reason ?? '' }))
    .filter(({ value }) => value !== null)
  const menuLines = menuItems
    .map((menuItem) => ({
      menuItem,
      value: parseCount(menuEntries[menuItem.id]?.qty),
      reason: menuEntries[menuItem.id]?.reason ?? '',
    }))
    .filter(({ value }) => value !== null)
  const invalid = [...lines, ...menuLines].filter(({ value }) => Number.isNaN(value))
  const valid = lines.length + menuLines.length - invalid.length
  const hiddenBySearch = lines.filter(({ item }) => !shown.includes(item)).length
  const canSubmit = valid > 0 && invalid.length === 0 && !submitting

  async function submit() {
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const { data } = await api.post('/waste/', {
        items: [
          ...lines.map(({ item, value, reason }) => ({ item_id: item.id, quantity: value, reason: reason.trim() || null })),
          ...menuLines.map(({ menuItem, value, reason }) => ({
            menu_item_id: menuItem.id,
            quantity: value,
            reason: reason.trim() || null,
          })),
        ],
      })
      const burgers = menuLines.reduce((sum, { value }) => sum + value, 0)
      setNotice({
        tone: 'success',
        title: `Waste booked: ${data.length} stock entr${data.length === 1 ? 'y' : 'ies'}.`,
        detail: burgers
          ? `${burgers} menu item${burgers === 1 ? ' was' : 's were'} broken down into ingredients; stock has been reduced accordingly.`
          : 'Stock has been reduced accordingly.',
      })
      setEntries({})
      setMenuEntries({})
      setSearch('')
      items.reload()
      today.reload()
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't book the waste. Nothing was changed.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  const downloadPdf = () =>
    downloadChecklist({
      title: 'Waste Checklist',
      subtitle: `End of day ${todayInBerlin()}`,
      filename: `waste-checklist-${todayInBerlin()}.pdf`,
      sections: [
        { title: 'Menu Items / Burgers', head: WASTE_HEAD, body: wasteRows(menuItems, () => '-'), columnStyles: WASTE_COLUMNS },
        { title: 'Raw Ingredients', head: WASTE_HEAD, body: wasteRows(all), columnStyles: WASTE_COLUMNS },
      ],
    })

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">End of day</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Waste Booking</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Enter wasted burgers and raw ingredients, leaving the rest empty. Burgers are broken down into their ingredients.
          Everything is booked in one go and deducted from stock.
        </p>
      </header>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="View" options={VIEW_OPTIONS} value={view} onChange={setView} />
        {view === 'active' && <PdfButton onDownload={downloadPdf} disabled={!items.data || !menu.data} />}
      </div>

      {view === 'archive' ? (
        <ArchiveView
          path="/archive/waste"
          month={month}
          onMonthChange={setMonth}
          noun="booking"
          summary={(batch) => (
            <>
              <span className="font-medium">{formatDateTime(batch.created_at)}</span>
              <span className="text-slate-500">
                {batch.lines.length} entr{batch.lines.length === 1 ? 'y' : 'ies'}
              </span>
            </>
          )}
          details={(batch) => (
            <ArchiveTable
              head={[{ label: 'Item' }, { label: 'Wasted', align: 'right' }, { label: 'Reason' }]}
              rows={batch.lines.map((w) => (
                <tr key={w.id}>
                  <td className="px-4 py-2 font-medium">
                    <ItemName item={itemsById[w.item_id]} name={w.item_name} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-right tabular-nums text-red-700">
                    −{fmt(w.quantity)} {w.unit}
                  </td>
                  <td className="px-4 py-2 text-slate-500">{w.reason ?? '—'}</td>
                </tr>
              ))}
            />
          )}
        />
      ) : (
        <>
          {notice && (
            <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
              {notice.detail}
            </Banner>
          )}
          {items.error && <Banner tone="error" title="Couldn't load the inventory.">{items.error}</Banner>}
          {menu.error && <Banner tone="error" title="Couldn't load the menu items.">{menu.error}</Banner>}

          <section className="mt-6" aria-labelledby="menu-heading">
            <h2 id="menu-heading" className="flex items-center gap-2 font-semibold">
              <Sandwich className="size-5 text-indigo-600" aria-hidden="true" />
              Menu Items / Burgers
            </h2>
            <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className={headClass}>
                    <tr>
                      <th scope="col" className="px-4 py-3">Menu item</th>
                      <th scope="col" className="px-4 py-3 text-right">Wasted</th>
                      <th scope="col" className="px-4 py-3">Reason <span className="font-normal normal-case">(optional)</span></th>
                      <th scope="col" className="px-4 py-3">Deducts from stock</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {!menu.data && <SkeletonRows rows={3} cols={4} />}
                    {menu.data?.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-4 py-6 text-center text-slate-500">No menu items set up yet.</td>
                      </tr>
                    )}
                    {menuItems.map((menuItem) => {
                      const entry = menuEntries[menuItem.id] ?? { qty: '', reason: '' }
                      const value = parseCount(entry.qty)
                      const bad = Number.isNaN(value)
                      const active = value !== null && !bad
                      return (
                        <tr key={menuItem.id} className={active ? 'bg-red-50/60' : ''}>
                          <td className="px-4 py-2 font-medium">{menuItem.name}</td>
                          <td className="whitespace-nowrap px-4 py-2 text-right">
                            <input
                              type="text"
                              inputMode="numeric"
                              value={entry.qty}
                              onChange={(e) => setMenuEntry(menuItem.id, { qty: e.target.value })}
                              aria-label={`Wasted ${menuItem.name}`}
                              aria-invalid={bad}
                              placeholder="0"
                              className={inputClass(bad)}
                            />
                            <span className="ml-1.5 inline-block w-8 text-left text-slate-400">pcs</span>
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="text"
                              value={entry.reason}
                              onChange={(e) => setMenuEntry(menuItem.id, { reason: e.target.value })}
                              maxLength={400}
                              aria-label={`Reason for ${menuItem.name} waste`}
                              placeholder={active ? 'e.g. Dropped' : ''}
                              className={reasonClass}
                            />
                          </td>
                          <td className={`px-4 py-2 ${active ? 'text-red-700' : 'text-slate-400'}`}>
                            {bad ? 'whole numbers only' : recipeText(menuItem, active ? value : 1)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section className="mt-8" aria-labelledby="raw-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="raw-heading" className="font-semibold">Raw Ingredients</h2>
              <div className="relative w-full sm:w-80">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={`Search ${all.length || ''} items…`}
                  aria-label="Search items"
                  className="block w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </div>
            </div>

            <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className={headClass}>
                    <tr>
                      <th scope="col" className="px-4 py-3">Item</th>
                      <th scope="col" className="px-4 py-3 text-right">Stock</th>
                      <th scope="col" className="px-4 py-3 text-right">Wasted</th>
                      <th scope="col" className="px-4 py-3">Reason <span className="font-normal normal-case">(optional)</span></th>
                      <th scope="col" className="px-4 py-3 text-right">New stock</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {!items.data && <SkeletonRows rows={8} cols={5} />}
                    {shown.map((item) => {
                      const entry = entries[item.id] ?? { qty: '', reason: '' }
                      const value = parseWaste(entry.qty)
                      const bad = Number.isNaN(value)
                      const active = value !== null && !bad
                      return (
                        <tr key={item.id} className={active ? 'bg-red-50/60' : ''}>
                          <td className="px-4 py-2 font-medium">
                            <ItemName item={item} />
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
                              className={inputClass(bad)}
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
                              className={reasonClass}
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
          </section>

          <div className="sticky bottom-0 z-10 -mx-4 mt-4 border-t border-slate-200 bg-slate-50/95 px-4 py-4 backdrop-blur sm:-mx-6 sm:px-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-600">
                <span className="font-semibold text-slate-900">{valid}</span> line{valid === 1 ? '' : 's'} with waste
                {menuLines.length > 0 && <span className="text-slate-500"> ({menuLines.length} menu item{menuLines.length === 1 ? '' : 's'})</span>}
                {hiddenBySearch > 0 && <span className="text-slate-500"> · {hiddenBySearch} hidden by search</span>}
                {invalid.length > 0 && <span className="text-red-700"> · {invalid.length} invalid</span>}
                {lines.length + menuLines.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setEntries({})
                      setMenuEntries({})
                    }}
                    className="ml-3 text-slate-500 underline-offset-2 hover:underline"
                  >
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
      )}
    </>
  )
}
