// Roster helpers: week dates, shift times on the Berlin clock and the daily coverage rule.

export const ROLE_LABELS = { shift_manager: 'Schichtführer', crew: 'Mitarbeiter' }

export const TIME_OFF = {
  Urlaub: { label: 'Urlaub', emoji: '🌴', className: 'bg-sky-100 text-sky-800 ring-sky-200' },
  Krank: { label: 'Krank', emoji: '🤒', className: 'bg-amber-100 text-amber-800 ring-amber-200' },
  Frei: { label: 'Frei', emoji: '', className: 'bg-slate-100 text-slate-600 ring-slate-200' },
}

// Fast-food standard: every day needs at least 1 Schichtführer and 2 Mitarbeiter, each on a
// shift covering a full 8-hour operating window.
export const MIN_COVERAGE = { shift_manager: 1, crew: 2 }
export const COVERAGE_SHIFT_HOURS = 8
export const COVERAGE_WARNING = 'Coverage Warning: Minimum 1 Manager and 2 Workers required.'

// --- Dates ("YYYY-MM-DD" strings, calendar days with no time zone) ---

const toUtcDate = (isoDate) => new Date(`${isoDate}T00:00:00Z`)
const fromUtcDate = (date) => date.toISOString().slice(0, 10)

export function addDays(isoDate, days) {
  const date = toUtcDate(isoDate)
  date.setUTCDate(date.getUTCDate() + days)
  return fromUtcDate(date)
}

/** The Monday of the week containing `isoDate`. */
export function mondayOf(isoDate) {
  const weekday = (toUtcDate(isoDate).getUTCDay() + 6) % 7 // Monday = 0
  return addDays(isoDate, -weekday)
}

const weekdayFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'short', timeZone: 'UTC' })
const longWeekdayFormat = new Intl.DateTimeFormat('en-GB', { weekday: 'long', timeZone: 'UTC' })
const dayMonthFormat = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', timeZone: 'UTC' })
const rangeFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })

export const weekdayShort = (isoDate) => weekdayFormat.format(toUtcDate(isoDate)) // "Mon"
export const weekdayLong = (isoDate) => longWeekdayFormat.format(toUtcDate(isoDate)) // "Monday"
export const dayMonth = (isoDate) => dayMonthFormat.format(toUtcDate(isoDate)) // "12.10."
export const weekRange = (start, end) => `${rangeFormat.format(toUtcDate(start))} – ${rangeFormat.format(toUtcDate(end))}`

// --- Shift times ---

const clockFormat = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' })

/** "08:00" on the Berlin clock, from an API timestamp. */
export const clockTime = (isoDateTime) => clockFormat.format(new Date(isoDateTime))

/** "08:00 - 16:00" */
export const shiftLabel = (shift) => `${clockTime(shift.start_time)} - ${clockTime(shift.end_time)}`

/** Real hours worked: the timestamps carry offsets, so a DST night is counted correctly. */
export const shiftHours = (shift) => (new Date(shift.end_time) - new Date(shift.start_time)) / 3_600_000

/**
 * Start and end for the API from a calendar day and two "HH:MM" times, as Berlin local time
 * (no offset: the API reads it as Berlin). An end at or before the start is on the next day (night shift).
 */
export function shiftTimes(isoDate, start, end) {
  const endDate = end <= start ? addDays(isoDate, 1) : isoDate
  return { start_time: `${isoDate}T${start}:00`, end_time: `${endDate}T${end}:00`, overnight: endDate !== isoDate }
}

// --- Coverage ---

/**
 * Coverage for one day of the weekly roster (`dayIndex` 0 = Monday): how many different people
 * work each role on a shift of at least 8 hours, and whether that meets the minimum.
 */
export function dayCoverage(rows, dayIndex) {
  const people = { shift_manager: new Set(), crew: new Set() }
  for (const row of rows) {
    for (const shift of row.days[dayIndex].shifts) {
      if (shiftHours(shift) >= COVERAGE_SHIFT_HOURS) people[shift.role_worked]?.add(row.employee.id)
    }
  }
  const managers = people.shift_manager.size
  const crew = people.crew.size
  return { managers, crew, ok: managers >= MIN_COVERAGE.shift_manager && crew >= MIN_COVERAGE.crew }
}
