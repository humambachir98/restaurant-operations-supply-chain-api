import {
  AlertTriangle,
  ArrowDownLeft,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ClipboardX,
  HeartPulse,
  Package,
  RefreshCw,
  Trash2,
  TrendingDown,
  Truck,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import Banner from '../components/Banner.jsx'
import ItemName from '../components/ItemName.jsx'
import { formatDateTime, formatNumber as fmt, formatSigned } from '../format.js'
import { useFetch } from '../useFetch.js'

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

function Card({ title, Icon, iconClass, link, children }) {
  return (
    <section className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-600">
          <Icon className={`size-4 ${iconClass}`} aria-hidden="true" />
          {title}
        </h2>
        {link && (
          <Link to={link.to} className="inline-flex items-center gap-0.5 text-xs font-medium text-indigo-600 hover:underline">
            {link.label} <ArrowRight className="size-3" aria-hidden="true" />
          </Link>
        )}
      </div>
      <div className="mt-3 flex-1">{children}</div>
    </section>
  )
}

const Skeleton = ({ className = 'h-16' }) => <div className={`animate-pulse rounded-lg bg-slate-100 ${className}`} />

function StockHealthCard({ health }) {
  const parts = health
    ? [
        { key: 'ok', label: 'Healthy', value: health.ok, bar: 'bg-emerald-500', dot: 'bg-emerald-500' },
        { key: 'low', label: 'At reorder level', value: health.low, bar: 'bg-amber-400', dot: 'bg-amber-400' },
        { key: 'negative', label: 'Negative', value: health.negative, bar: 'bg-red-500', dot: 'bg-red-500' },
      ]
    : []
  const healthyPct = health?.total_items ? Math.round((health.ok / health.total_items) * 100) : null

  return (
    <Card title="Current stock health" Icon={HeartPulse} iconClass="text-emerald-600" link={{ to: '/orders', label: 'Alerts' }}>
      {!health ? (
        <Skeleton />
      ) : (
        <>
          <p className="text-3xl font-semibold tabular-nums">
            {healthyPct ?? '–'}
            {healthyPct !== null && <span className="text-lg text-slate-400">%</span>}
            <span className="ml-2 text-sm font-normal text-slate-500">of {health.total_items} items healthy</span>
          </p>
          <div className="mt-3 flex h-2.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
            {parts.map((p) =>
              p.value ? <div key={p.key} className={p.bar} style={{ width: `${(p.value / health.total_items) * 100}%` }} /> : null,
            )}
          </div>
          <ul className="mt-3 space-y-1 text-sm">
            {parts.map((p) => (
              <li key={p.key} className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-slate-600">
                  <span className={`size-2 rounded-full ${p.dot}`} aria-hidden="true" />
                  {p.label}
                </span>
                <span className="font-medium tabular-nums">{p.value}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

function WasteCard({ waste }) {
  return (
    <Card title="Today's waste" Icon={Trash2} iconClass="text-red-600" link={{ to: '/waste', label: 'Book waste' }}>
      {!waste ? (
        <Skeleton />
      ) : (
        <>
          <p className="text-3xl font-semibold tabular-nums">
            {waste.entries}
            <span className="ml-2 text-sm font-normal text-slate-500">entr{waste.entries === 1 ? 'y' : 'ies'} today</span>
          </p>
          {waste.items.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">Nothing wasted so far today.</p>
          ) : (
            <ul className="mt-3 space-y-1 text-sm">
              {waste.items.slice(0, 4).map((w) => (
                <li key={w.item_id} className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-600">{w.item_name}</span>
                  <span className={`shrink-0 tabular-nums ${w.quantity < 0 ? 'text-emerald-700' : 'text-red-700'}`}>
                    {formatSigned(-w.quantity)} {w.unit}
                  </span>
                </li>
              ))}
              {waste.items.length > 4 && <li className="text-xs text-slate-400">+{waste.items.length - 4} more items</li>}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}

function TransfersCard({ transfers }) {
  return (
    <Card title="Recent transfers" Icon={ArrowUpRight} iconClass="text-indigo-600" link={{ to: '/transfers', label: 'New transfer' }}>
      {!transfers ? (
        <Skeleton />
      ) : transfers.length === 0 ? (
        <p className="text-sm text-slate-500">No transfers between stores yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {transfers.map((t) => {
            const incoming = t.direction === 'in'
            const Icon = incoming ? ArrowDownLeft : ArrowUpRight
            return (
              <li key={t.id} className="flex items-start justify-between gap-2">
                <span className="flex min-w-0 items-start gap-2">
                  <Icon className={`mt-0.5 size-4 shrink-0 ${incoming ? 'text-emerald-600' : 'text-amber-600'}`} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block truncate">{t.item_name}</span>
                    <span className="block truncate text-xs text-slate-400">
                      {incoming ? 'from' : 'to'} {t.target_store_name} · {formatDateTime(t.created_at)}
                    </span>
                  </span>
                </span>
                <span className={`shrink-0 tabular-nums ${incoming ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {formatSigned(t.stock_change)} {t.unit}
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function OpenWork({ summary }) {
  const tiles = [
    { to: '/orders', Icon: Truck, label: 'Deliveries scheduled', value: summary?.pending_deliveries, tone: 'text-sky-700' },
    { to: '/complaints', Icon: ClipboardX, label: 'Complaints awaiting decision', value: summary?.pending_complaints, tone: 'text-amber-700' },
  ]
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      {tiles.map(({ to, Icon, label, value, tone }) => (
        <Link
          key={to}
          to={to}
          className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition hover:border-indigo-300"
        >
          <span className="inline-flex items-center gap-2 text-sm text-slate-600">
            <Icon className="size-4 text-slate-400" aria-hidden="true" />
            {label}
          </span>
          <span className={`text-xl font-semibold tabular-nums ${value ? tone : 'text-slate-400'}`}>{value ?? '–'}</span>
        </Link>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const summary = useFetch('/dashboard/summary')
  const keyItems = useFetch('/inventory/daily-items')
  const loading = summary.loading || keyItems.loading
  const data = summary.data

  function refresh() {
    summary.reload()
    keyItems.reload()
  }

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-indigo-600">Area manager</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            {data ? `Updated ${formatDateTime(data.generated_at)} (Berlin time)` : 'Loading the latest figures…'}
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

      {summary.error && <Banner tone="error" title="Couldn't load the dashboard.">{summary.error}</Banner>}

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <StockHealthCard health={data?.stock_health} />
        <WasteCard waste={data?.waste_today} />
        <TransfersCard transfers={data?.recent_transfers} />
      </div>
      <OpenWork summary={data} />

      <section className="mt-10" aria-labelledby="key-items">
        <div className="flex items-end justify-between gap-2">
          <div>
            <h2 id="key-items" className="font-semibold">Key Items</h2>
            <p className="text-sm text-slate-500">High-turnover items counted every day.</p>
          </div>
          <Link to="/audits" className="inline-flex items-center gap-0.5 text-sm font-medium text-indigo-600 hover:underline">
            Start daily audit <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>

        {keyItems.error ? (
          <Banner tone="error" title="Couldn't load the Key Items." className="mt-3">{keyItems.error}</Banner>
        ) : (
          <div className="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
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
                  {!keyItems.data &&
                    Array.from({ length: 8 }, (_, i) => (
                      <tr key={i} className="animate-pulse">
                        {Array.from({ length: 5 }, (_, j) => (
                          <td key={j} className="px-4 py-3.5">
                            <div className="h-4 rounded bg-slate-100" />
                          </td>
                        ))}
                      </tr>
                    ))}
                  {keyItems.data?.map((item) => {
                    const status = stockStatus(item)
                    return (
                      <tr key={item.id} className="transition hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium">
                          <span className="inline-flex items-center gap-2">
                            <Package className="size-4 text-slate-400" aria-hidden="true" />
                            <span>
                              <ItemName item={item} />
                            </span>
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
                  {keyItems.data?.length === 0 && (
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
      </section>
    </>
  )
}
