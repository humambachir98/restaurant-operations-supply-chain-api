import {
  ArrowLeftRight,
  CalendarDays,
  ChefHat,
  ClipboardCheck,
  ClipboardX,
  LayoutDashboard,
  Menu,
  Trash2,
  Truck,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

const NAV_SECTIONS = [
  {
    title: '🍔 Operations & Inventory',
    items: [
      { to: '/', label: 'Dashboard', Icon: LayoutDashboard, end: true },
      { to: '/orders', label: 'Restock Orders', Icon: Truck },
      { to: '/audits', label: 'Audits', Icon: ClipboardCheck },
      { to: '/waste', label: 'Waste', Icon: Trash2 },
      { to: '/transfers', label: 'Transfers', Icon: ArrowLeftRight },
      { to: '/complaints', label: 'Complaints', Icon: ClipboardX },
    ],
  },
  {
    title: '👥 Shift Management',
    items: [{ to: '/schedule', label: 'Schichtplan', Icon: CalendarDays }],
  },
]

function navLinkClass({ isActive }) {
  const base =
    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600'
  return isActive
    ? `${base} bg-indigo-50 text-indigo-700`
    : `${base} text-slate-600 hover:bg-slate-100 hover:text-slate-900`
}

function Brand() {
  return (
    <NavLink to="/" className="inline-flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid size-8 place-items-center rounded-lg bg-indigo-600 text-white">
        <ChefHat className="size-5" aria-hidden="true" />
      </span>
      Restaurant Ops
    </NavLink>
  )
}

function SidebarNav({ onNavigate }) {
  return (
    <nav aria-label="Main" className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
      {NAV_SECTIONS.map(({ title, items }) => (
        <div key={title}>
          <p className="px-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
          <ul className="mt-2 space-y-0.5">
            {items.map(({ to, label, Icon, end }) => (
              <li key={to}>
                <NavLink to={to} end={end} className={navLinkClass} onClick={onNavigate}>
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  )
}

/** App shell: a persistent left sidebar (a drawer on small screens) around the routed page. */
export default function Layout() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = () => setDrawerOpen(false)

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 lg:flex">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="border-b border-slate-200 px-5 py-4">
          <Brand />
        </div>
        <SidebarNav />
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
          aria-label="Open navigation"
          aria-expanded={drawerOpen}
        >
          <Menu className="size-5" />
        </button>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={closeDrawer} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <Brand />
              <button type="button" onClick={closeDrawer} className="rounded-md p-1 text-slate-400 hover:bg-slate-100" aria-label="Close navigation">
                <X className="size-5" />
              </button>
            </div>
            <SidebarNav onNavigate={closeDrawer} />
          </aside>
        </div>
      )}

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
