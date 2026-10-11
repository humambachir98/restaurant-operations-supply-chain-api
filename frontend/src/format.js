const numberFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 })

export const formatNumber = (value) => numberFormat.format(value)

// Date-only strings ("2026-10-15") parse as UTC midnight, so format them in UTC to keep the day.
const dateFormat = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
})

export const formatDate = (isoDate) => dateFormat.format(new Date(isoDate))
