import { AlertTriangle, CalendarDays, ChevronLeft, ChevronRight, Loader2, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import api, { errorMessage } from '../api.js'
import Banner from '../components/Banner.jsx'
import Modal from '../components/Modal.jsx'
import Segmented from '../components/Segmented.jsx'
import { todayInBerlin } from '../format.js'
import {
  COVERAGE_SHIFT_HOURS,
  COVERAGE_WARNING,
  ROLE_LABELS,
  TIME_OFF,
  addDays,
  clockTime,
  dayCoverage,
  dayMonth,
  mondayOf,
  shiftLabel,
  shiftTimes,
  weekRange,
  weekdayLong,
  weekdayShort,
} from '../roster.js'
import { useFetch } from '../useFetch.js'

const ROLE_GROUPS = ['shift_manager', 'crew'] // Schichtführer first

const MODE_OPTIONS = [
  { value: 'shift', label: 'Assign Shift' },
  { value: 'time_off', label: 'Mark Time-Off' },
]

const ROLE_OPTIONS = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))

const fieldClass =
  'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30'

function TimeOffBadge({ status }) {
  const { label, emoji, className } = TIME_OFF[status]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}>
      {emoji && <span aria-hidden="true">{emoji}</span>}
      {label}
    </span>
  )
}

function CoverageHeader({ day, coverage }) {
  return (
    <th scope="col" className="min-w-32 px-3 py-3 text-left align-top">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">{weekdayShort(day)}</span>
        <span className="text-xs font-normal text-slate-400">{dayMonth(day)}</span>
        {coverage && !coverage.ok && (
          <span className="group relative inline-flex" tabIndex={0} title={COVERAGE_WARNING}>
            <AlertTriangle className="size-4 text-red-600" aria-hidden="true" />
            <span className="sr-only">{`${weekdayLong(day)}: ${COVERAGE_WARNING}`}</span>
            <span
              role="tooltip"
              className="pointer-events-none absolute left-1/2 top-full z-20 mt-2 hidden w-56 -translate-x-1/2 rounded-lg bg-red-700 px-3 py-2 text-xs font-medium normal-case tracking-normal text-white shadow-lg group-hover:block group-focus:block"
            >
              {COVERAGE_WARNING}
            </span>
          </span>
        )}
      </div>
      {coverage && (
        <p className={`mt-1 text-[11px] font-medium normal-case tracking-normal ${coverage.ok ? 'text-emerald-700' : 'text-red-700'}`}>
          SF {coverage.managers}/1 · MA {coverage.crew}/2
        </p>
      )}
    </th>
  )
}

function RosterCell({ cell, employee, onOpen }) {
  const { shifts, time_off: timeOff } = cell
  const empty = shifts.length === 0 && !timeOff
  return (
    <td className="border-l border-slate-100 p-1.5 align-top">
      <button
        type="button"
        onClick={onOpen}
        aria-label={
          empty
            ? `Plan ${employee.name} on ${weekdayLong(cell.date)}`
            : `Edit ${employee.name} on ${weekdayLong(cell.date)}`
        }
        className={`group flex min-h-14 w-full flex-col items-start justify-center gap-1 rounded-lg px-2 py-1.5 text-left text-sm transition focus-visible:outline-2 focus-visible:outline-indigo-600 ${
          empty ? 'border border-dashed border-transparent hover:border-slate-300 hover:bg-slate-50' : 'hover:bg-slate-50'
        }`}
      >
        {timeOff && <TimeOffBadge status={timeOff.status} />}
        {shifts.map((shift) => (
          <span
            key={shift.id}
            className={`w-full rounded-md px-2 py-1 font-medium tabular-nums ${
              shift.role_worked === 'shift_manager' ? 'bg-indigo-100 text-indigo-800' : 'bg-emerald-100 text-emerald-800'
            }`}
          >
            {shiftLabel(shift)}
            {shift.role_worked !== employee.role && (
              <span className="block text-[11px] font-normal opacity-80">as {ROLE_LABELS[shift.role_worked]}</span>
            )}
          </span>
        ))}
        {empty && <Plus className="mx-auto size-4 text-slate-300 group-hover:text-slate-500" aria-hidden="true" />}
      </button>
    </td>
  )
}

/** The modal's body: assign a shift / mark time-off on an empty day, or change / remove what's planned. */
function CellEditor({ cell, employee, onDone, onCancel }) {
  const shift = cell.shifts[0] ?? null
  const timeOff = cell.time_off
  const [mode, setMode] = useState(timeOff ? 'time_off' : 'shift')
  const [start, setStart] = useState(shift ? clockTime(shift.start_time) : '08:00')
  const [end, setEnd] = useState(shift ? clockTime(shift.end_time) : '16:00')
  const [roleWorked, setRoleWorked] = useState(shift?.role_worked ?? employee.role)
  const [status, setStatus] = useState(timeOff?.status ?? 'Urlaub')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const editing = shift || timeOff
  const times = shiftTimes(cell.date, start, end)

  async function run(request) {
    setBusy(true)
    setError(null)
    try {
      await request()
      onDone()
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const save = (event) => {
    event.preventDefault()
    if (mode === 'shift') {
      const body = { start_time: times.start_time, end_time: times.end_time, role_worked: roleWorked }
      return run(() =>
        shift ? api.patch(`/shifts/${shift.id}`, body) : api.post('/shifts/', { employee_id: employee.id, ...body }),
      )
    }
    return run(() =>
      timeOff
        ? api.patch(`/time-off/${timeOff.id}`, { status })
        : api.post('/time-off/', { employee_id: employee.id, date: cell.date, status }),
    )
  }

  const remove = () => run(() => (shift ? api.delete(`/shifts/${shift.id}`) : api.delete(`/time-off/${timeOff.id}`)))

  return (
    <form onSubmit={save}>
      <p className="text-sm text-slate-500">
        <span className="font-medium text-slate-900">{employee.name}</span> · {ROLE_LABELS[employee.role]} ·{' '}
        {weekdayLong(cell.date)} {dayMonth(cell.date)}
      </p>

      {!editing && <Segmented label="What to plan" options={MODE_OPTIONS} value={mode} onChange={setMode} />}

      {mode === 'shift' ? (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm font-medium">
              Start time
              <input type="time" required value={start} onChange={(e) => setStart(e.target.value)} className={fieldClass} data-autofocus />
            </label>
            <label className="block text-sm font-medium">
              End time
              <input type="time" required value={end} onChange={(e) => setEnd(e.target.value)} className={fieldClass} />
            </label>
          </div>
          {times.overnight && <p className="text-sm text-amber-700">Ends the next day (night shift).</p>}
          <div className="text-sm font-medium">
            Role worked
            <div>
              <Segmented label="Role worked" options={ROLE_OPTIONS} value={roleWorked} onChange={setRoleWorked} />
            </div>
          </div>
          <p className="text-xs text-slate-500">
            Max. 10 hours (ArbZG). Counts toward daily coverage when it lasts at least {COVERAGE_SHIFT_HOURS} hours.
          </p>
        </div>
      ) : (
        <fieldset className="mt-4">
          <legend className="text-sm font-medium">Status</legend>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {Object.entries(TIME_OFF).map(([value, { label, emoji }]) => (
              <label
                key={value}
                className={`flex cursor-pointer flex-col items-center gap-1 rounded-xl border px-3 py-3 text-sm font-medium transition ${
                  status === value ? 'border-indigo-500 bg-indigo-50 text-indigo-800 ring-2 ring-indigo-500/30' : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <input type="radio" name="status" value={value} checked={status === value} onChange={() => setStatus(value)} className="sr-only" />
                <span className="text-xl" aria-hidden="true">{emoji || '🗓️'}</span>
                {label}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {error && (
        <Banner tone="error" title="Couldn't save." className="mt-4">
          {error}
        </Banner>
      )}

      <div className="mt-6 flex items-center justify-between gap-3">
        {editing ? (
          <button
            type="button"
            onClick={remove}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Remove {shift ? 'shift' : 'time-off'}
          </button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {editing ? 'Save changes' : mode === 'shift' ? 'Assign shift' : 'Mark time-off'}
          </button>
        </div>
      </div>
    </form>
  )
}

export default function Schedule() {
  // The week lives in the URL (?week=YYYY-MM-DD), so it survives switching modules and reloads.
  const [searchParams, setSearchParams] = useSearchParams()
  const week = mondayOf(searchParams.get('week') ?? todayInBerlin())
  const setWeek = (monday) => setSearchParams({ week: monday })

  const { data, error, loading, reload } = useFetch('/schedule/weekly', { params: { start_date: week } })
  const [editing, setEditing] = useState(null) // { employee, cell }

  const current = data?.start_date === week ? data : null
  const rows = current?.rows ?? []
  const coverage = current ? current.days.map((_, i) => dayCoverage(rows, i)) : []
  const gaps = coverage.filter((c) => !c.ok).length
  const days = current?.days ?? Array.from({ length: 7 }, (_, i) => addDays(week, i))

  return (
    <>
      <header>
        <p className="text-sm font-medium text-indigo-600">Shift Management</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Schichtplan</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Click a cell to assign a shift or mark Urlaub, Krank or Frei. Each day needs at least 1 Schichtführer and 2
          Mitarbeiter on {COVERAGE_SHIFT_HOURS}-hour shifts.
        </p>
      </header>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white p-0.5 shadow-sm">
          <button type="button" onClick={() => setWeek(addDays(week, -7))} className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" aria-label="Previous week">
            <ChevronLeft className="size-4" />
          </button>
          <span className="inline-flex min-w-56 items-center justify-center gap-2 px-2 text-sm font-medium">
            <CalendarDays className="size-4 text-slate-400" aria-hidden="true" />
            {weekRange(days[0], days[6])}
          </span>
          <button type="button" onClick={() => setWeek(addDays(week, 7))} className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" aria-label="Next week">
            <ChevronRight className="size-4" />
          </button>
        </div>
        <div className="flex items-center gap-3">
          {current && (
            <span className={`text-sm font-medium ${gaps ? 'text-red-700' : 'text-emerald-700'}`}>
              {gaps ? `${gaps} day${gaps === 1 ? '' : 's'} below minimum coverage` : 'Every day is covered'}
            </span>
          )}
          <button
            type="button"
            onClick={() => setWeek(mondayOf(todayInBerlin()))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            This week
          </button>
        </div>
      </div>

      {error && <Banner tone="error" title="Couldn't load the roster.">{error}</Banner>}

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr>
                <th scope="col" className="sticky left-0 z-10 min-w-44 bg-slate-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Employee
                </th>
                {days.map((day, i) => (
                  <CoverageHeader key={day} day={day} coverage={coverage[i]} />
                ))}
              </tr>
            </thead>
            {loading && !current ? (
              <tbody>
                {Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="animate-pulse border-t border-slate-100">
                    {Array.from({ length: 8 }, (_, j) => (
                      <td key={j} className="px-4 py-5">
                        <div className="h-4 rounded bg-slate-100" />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            ) : (
              ROLE_GROUPS.map((role) => {
                const group = rows.filter((row) => row.employee.role === role)
                if (group.length === 0) return null
                return (
                  <tbody key={role} className="divide-y divide-slate-100">
                    <tr className="bg-slate-50/70">
                      <th colSpan={8} scope="colgroup" className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        {ROLE_LABELS[role]} <span className="font-normal">· {group.length}</span>
                      </th>
                    </tr>
                    {group.map((row) => (
                      <tr key={row.employee.id}>
                        <th scope="row" className="sticky left-0 z-10 bg-white px-4 py-2 text-left font-medium">
                          {row.employee.name}
                          {!row.employee.is_active && <span className="ml-2 text-xs font-normal text-slate-400">inactive</span>}
                        </th>
                        {row.days.map((cell) => (
                          <RosterCell key={cell.date} cell={cell} employee={row.employee} onOpen={() => setEditing({ employee: row.employee, cell })} />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                )
              })
            )}
            {current && rows.length === 0 && (
              <tbody>
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                    No active employees. Add staff via the API (POST /employees/) or run the seed script.
                  </td>
                </tr>
              </tbody>
            )}
          </table>
        </div>
      </div>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing && (editing.cell.shifts.length || editing.cell.time_off ? 'Edit day' : 'Plan day')}
      >
        {editing && (
          <CellEditor
            key={`${editing.employee.id}-${editing.cell.date}`}
            cell={editing.cell}
            employee={editing.employee}
            onCancel={() => setEditing(null)}
            onDone={() => {
              setEditing(null)
              reload()
            }}
          />
        )}
      </Modal>
    </>
  )
}
