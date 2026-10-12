import { ClipboardCheck, Loader2, Send } from 'lucide-react'
import { useState } from 'react'

import api, { errorMessage } from '../api.js'
import { VIEW_OPTIONS, currentMonth } from '../archive.js'
import ArchiveView, { ArchiveTable } from '../components/ArchiveView.jsx'
import Banner from '../components/Banner.jsx'
import ItemName from '../components/ItemName.jsx'
import PdfButton from '../components/PdfButton.jsx'
import Segmented from '../components/Segmented.jsx'
import { formatDateTime, formatNumber as fmt, formatSigned, todayInBerlin } from '../format.js'
import { COUNTING_COLUMNS, COUNTING_HEAD, countingRows, downloadChecklist } from '../pdf.js'
import { useFetch } from '../useFetch.js'

const AUDIT_TYPES = {
  daily: { label: 'Daily (Key Items)', path: '/inventory/daily-items', hint: 'High-turnover Key Items only.' },
  weekly: { label: 'Weekly (full count)', path: '/inventory/', hint: 'Every item in the store.' },
  monthly: { label: 'End of Month (full count)', path: '/inventory/', hint: 'Every item, for the month-end stock-take.' },
}

/** "12,5" or "12.5" -> 12.5; '' -> null; anything invalid -> NaN. */
function parseCount(text) {
  const trimmed = text.trim().replace(',', '.')
  if (trimmed === '') return null
  return /^\d+(\.\d+)?$/.test(trimmed) ? Number(trimmed) : NaN
}

const varianceClass = (variance) =>
  variance < 0 ? 'text-red-700' : variance > 0 ? 'text-emerald-700' : 'text-slate-500'

function AuditArchive({ month, onMonthChange }) {
  const [auditType, setAuditType] = useState('')
  const inventory = useFetch('/inventory/') // packaging details for the archived lines
  const itemsById = Object.fromEntries((inventory.data ?? []).map((i) => [i.id, i]))

  return (
    <>
      <label className="mt-6 block text-sm font-medium">
        Audit type
        <select
          value={auditType}
          onChange={(e) => setAuditType(e.target.value)}
          className="mt-1 block w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
        >
          <option value="">All audit types</option>
          {Object.entries(AUDIT_TYPES).map(([value, { label }]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <ArchiveView
        path="/archive/audits"
        params={auditType ? { audit_type: auditType } : undefined}
        month={month}
        onMonthChange={onMonthChange}
        noun="audit"
        summary={(audit) => {
          const shrinkage = audit.lines.filter((l) => l.variance < 0).length
          return (
            <>
              <span>
                <span className="font-medium">{AUDIT_TYPES[audit.audit_type].label}</span>
                <span className="ml-2 text-slate-500">#{audit.batch_id} · {formatDateTime(audit.created_at)}</span>
              </span>
              <span className="text-slate-500">
                {audit.lines.length} item{audit.lines.length === 1 ? '' : 's'}
                {shrinkage > 0 && <span className="text-red-700"> · {shrinkage} with shrinkage</span>}
              </span>
            </>
          )
        }}
        details={(audit) => (
          <>
            {audit.notes && <p className="px-4 pt-3 text-sm text-slate-500">Notes: {audit.notes}</p>}
            <ArchiveTable
              head={[
                { label: 'Item' },
                { label: 'Previous', align: 'right' },
                { label: 'Counted', align: 'right' },
                { label: 'Variance', align: 'right' },
              ]}
              rows={audit.lines.map((line) => (
                <tr key={line.item_id}>
                  <td className="px-4 py-2 font-medium">
                    <ItemName item={itemsById[line.item_id]} name={line.item_name} />
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                    {fmt(line.expected_quantity)} {line.unit}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {fmt(line.counted_quantity)} {line.unit}
                  </td>
                  <td className={`px-4 py-2 text-right tabular-nums ${varianceClass(line.variance)}`}>
                    {formatSigned(line.variance)} {line.unit}
                  </td>
                </tr>
              ))}
            />
          </>
        )}
      />
    </>
  )
}

export default function Audits() {
  const [view, setView] = useState('active')
  const [month, setMonth] = useState(currentMonth)
  const [auditType, setAuditType] = useState('daily')
  const [counts, setCounts] = useState({}) // item_id -> text as typed
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [notice, setNotice] = useState(null)

  const { data: items, error, loading, reload } = useFetch(AUDIT_TYPES[auditType].path)
  const visible = loading ? [] : (items ?? [])

  const parsed = visible.map((item) => ({ item, value: parseCount(counts[item.id] ?? '') }))
  const entered = parsed.filter(({ value }) => value !== null)
  const invalid = entered.filter(({ value }) => Number.isNaN(value))
  // A complete count only: every row needs a number (0 if none is left) before the batch can go in.
  const blank = parsed.length - entered.length
  const canSubmit = parsed.length > 0 && blank === 0 && invalid.length === 0 && !submitting

  const downloadPdf = () =>
    downloadChecklist({
      title: `${AUDIT_TYPES[auditType].label} Audit Checklist`,
      subtitle: todayInBerlin(),
      filename: `audit-${auditType}-${todayInBerlin()}.pdf`,
      sections: [{ head: COUNTING_HEAD, body: countingRows(visible), columnStyles: COUNTING_COLUMNS }],
    })

  async function submit(event) {
    event.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setNotice(null)
    try {
      const { data: audit } = await api.post('/inventory/audit', {
        audit_type: auditType,
        notes: notes.trim() || null,
        counts: parsed.map(({ item, value }) => ({ item_id: item.id, counted_quantity: value })),
      })
      const shrinkage = audit.lines.filter((line) => line.variance < 0).length
      setNotice({
        tone: 'success',
        title: `${AUDIT_TYPES[auditType].label} audit #${audit.id} saved.`,
        detail: `Stock for ${audit.lines.length} item${audit.lines.length === 1 ? '' : 's'} now matches the count${
          shrinkage ? `; ${shrinkage} showed shrinkage` : ''
        }.`,
      })
      setCounts({})
      setNotes('')
      reload()
    } catch (err) {
      setNotice({ tone: 'error', title: "Couldn't save the audit.", detail: errorMessage(err) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Inventory</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Stock Audits</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Enter what is physically on the shelves for every item in the list (0 if none is left). The audit is submitted
          as one complete batch: it sets each item&apos;s stock to the count and logs the variance.
        </p>
      </header>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <Segmented label="View" options={VIEW_OPTIONS} value={view} onChange={setView} />
        {view === 'active' && <PdfButton onDownload={downloadPdf} disabled={loading || visible.length === 0} />}
      </div>

      {view === 'archive' ? (
        <AuditArchive month={month} onMonthChange={setMonth} />
      ) : (
        <>
          {notice && (
            <Banner tone={notice.tone} title={notice.title} onDismiss={() => setNotice(null)}>
              {notice.detail}
            </Banner>
          )}

          <form onSubmit={submit} className="mt-6">
            <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <label className="block text-sm font-medium">
                Audit type
                <select
                  value={auditType}
                  onChange={(e) => setAuditType(e.target.value)}
                  className="mt-1 block w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                >
                  {Object.entries(AUDIT_TYPES).map(([value, { label }]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="text-sm text-slate-500">{AUDIT_TYPES[auditType].hint}</p>
            </div>

            {error && <Banner tone="error" title="Couldn't load the items to count.">{error}</Banner>}

            <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th scope="col" className="px-4 py-3">Item</th>
                      <th scope="col" className="px-4 py-3 text-right">System stock</th>
                      <th scope="col" className="px-4 py-3 text-right">Counted</th>
                      <th scope="col" className="px-4 py-3 text-right">Variance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading &&
                      Array.from({ length: 6 }, (_, i) => (
                        <tr key={i} className="animate-pulse">
                          {Array.from({ length: 4 }, (_, j) => (
                            <td key={j} className="px-4 py-3.5">
                              <div className="h-4 rounded bg-slate-100" />
                            </td>
                          ))}
                        </tr>
                      ))}
                    {parsed.map(({ item, value }) => {
                      const bad = Number.isNaN(value)
                      const variance = value === null || bad ? null : value - item.quantity
                      return (
                        <tr key={item.id} className={value === null ? 'bg-amber-50/60' : bad ? '' : 'bg-indigo-50/40'}>
                          <td className="px-4 py-2.5 font-medium">
                            <ItemName item={item} />
                          </td>
                          <td className={`px-4 py-2.5 text-right tabular-nums ${item.quantity < 0 ? 'text-red-700' : 'text-slate-600'}`}>
                            {fmt(item.quantity)} <span className="text-slate-400">{item.unit}</span>
                          </td>
                          <td className="px-4 py-2.5 text-right">
                            <input
                              type="text"
                              inputMode="decimal"
                              value={counts[item.id] ?? ''}
                              onChange={(e) => setCounts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                              aria-label={`Counted ${item.name} in ${item.unit}`}
                              aria-invalid={bad}
                              required
                              placeholder="—"
                              className={`w-24 rounded-md border px-2 py-1 text-right tabular-nums focus:outline-none focus:ring-2 ${
                                bad
                                  ? 'border-red-400 focus:ring-red-500/30'
                                  : value === null
                                    ? 'border-amber-400 focus:border-amber-500 focus:ring-amber-500/30'
                                    : 'border-slate-300 focus:border-indigo-500 focus:ring-indigo-500/30'
                              }`}
                            />
                            <span className="ml-1.5 inline-block w-8 text-left text-slate-400">{item.unit}</span>
                          </td>
                          <td
                            className={`px-4 py-2.5 text-right tabular-nums ${
                              variance === null ? 'text-slate-300' : varianceClass(variance)
                            }`}
                          >
                            {bad ? <span className="text-red-700">invalid</span> : variance === null ? '—' : `${formatSigned(variance)} ${item.unit}`}
                          </td>
                        </tr>
                      )
                    })}
                    {!loading && visible.length === 0 && !error && (
                      <tr>
                        <td colSpan={4} className="px-4 py-10 text-center text-slate-500">No items to count.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
              <label className="block text-sm font-medium">
                Notes <span className="font-normal text-slate-400">(optional)</span>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  maxLength={500}
                  placeholder="e.g. Counted by the closing shift"
                  className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                />
              </label>
              <button
                type="submit"
                disabled={!canSubmit}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50"
              >
                {submitting ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
                Submit Audit
              </button>
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-500">
              <ClipboardCheck className="size-4" aria-hidden="true" />
              {entered.length} of {visible.length} counted
              {invalid.length > 0 && <span className="text-red-700"> · {invalid.length} invalid (use numbers ≥ 0)</span>}
              {blank > 0 && (
                <span className="text-amber-700">
                  {' '}
                  · {blank} still blank: every row needs a count (enter 0 if none is left) before you can submit
                </span>
              )}
            </p>
          </form>
        </>
      )}
    </>
  )
}
