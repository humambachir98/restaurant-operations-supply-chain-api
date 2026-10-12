const numberFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 })

export const formatNumber = (value) => numberFormat.format(value)

// Date-only strings ("2026-10-15") parse as UTC midnight, so format them in UTC to keep the day.
const dateFormat = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
})

export const formatDate = (isoDate) => dateFormat.format(new Date(isoDate))

// Full timestamps from the API carry an offset; show them on the restaurant's clock.
const dateTimeFormat = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin',
})

export const formatDateTime = (isoDateTime) => dateTimeFormat.format(new Date(isoDateTime))

/** "+6" / "−30": explicit sign for stock changes. */
export const formatSigned = (value) => (value > 0 ? '+' : value < 0 ? '−' : '') + numberFormat.format(Math.abs(value))
