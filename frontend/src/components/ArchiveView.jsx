import { ChevronRight } from 'lucide-react'

import { todayInBerlin } from '../format.js'
import { useFetch } from '../useFetch.js'
import Banner from './Banner.jsx'
import { fieldClass } from './ItemSelect.jsx'

const monthFormat = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })

/**
 * Read-only history for one month: a month picker and the submissions (batches) of that month,
 * each expanding into its lines. `summary(batch)` is the collapsed row, `details(batch)` the
 * expanded content.
 */
export default function ArchiveView({ path, params, month, onMonthChange, summary, details, noun = 'submission' }) {
  const [year, monthNumber] = month.split('-').map(Number)
  const { data: batches, error, loading } = useFetch(path, { params: { ...params, year, month: monthNumber } })
  const thisMonth = todayInBerlin().slice(0, 7)

  return (
    <section className="mt-6" aria-labelledby="archive-heading">
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="block text-sm font-medium">
          Month
          <input
            type="month"
            value={month}
            max={thisMonth}
            onChange={(e) => e.target.value && onMonthChange(e.target.value)}
            className={`${fieldClass} w-48`}
          />
        </label>
        <p id="archive-heading" className="text-sm text-slate-500">
          {loading
            ? 'Loading…'
            : `${batches?.length ?? 0} ${noun}${batches?.length === 1 ? '' : 's'} in ${monthFormat.format(new Date(`${month}-01`))}`}
        </p>
      </div>

      {error && <Banner tone="error" title="Couldn't load the archive.">{error}</Banner>}

      <ul className="mt-4 space-y-2">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <li key={i} className="h-14 animate-pulse rounded-xl border border-slate-200 bg-white" />
          ))}
        {!loading && batches?.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center text-sm text-slate-500">
            Nothing was submitted this month.
          </li>
        )}
        {!loading &&
          batches?.map((batch) => (
            <li key={batch.batch_id}>
              <details className="group overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
                  <ChevronRight className="size-4 shrink-0 text-slate-400 transition group-open:rotate-90" aria-hidden="true" />
                  <div className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-4 gap-y-1">{summary(batch)}</div>
                </summary>
                <div className="border-t border-slate-200">{details(batch)}</div>
              </details>
            </li>
          ))}
      </ul>
    </section>
  )
}

/** A read-only table for an archived batch's lines. */
export function ArchiveTable({ head, rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            {head.map(({ label, align }) => (
              <th key={label} scope="col" className={`px-4 py-2 ${align === 'right' ? 'text-right' : ''}`}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{rows}</tbody>
      </table>
    </div>
  )
}
