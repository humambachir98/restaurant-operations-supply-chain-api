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

/** Today's date in Berlin as YYYY-MM-DD (the API's notion of "today"). */
export const todayInBerlin = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date())

/** "Carton: 48 | Sub: 12" from an item's packaging, or '' when it has none. */
export function packagingLabel(item) {
  const parts = []
  if (item?.units_per_carton) parts.push(`Carton: ${item.units_per_carton}`)
  if (item?.units_per_subpackage) parts.push(`Sub: ${item.units_per_subpackage}`)
  return parts.join(' | ')
}

/** "Whopper Patties (Carton: 48 | Sub: 12)", or just the name when there is no packaging. */
export function itemLabel(item) {
  const packaging = packagingLabel(item)
  return packaging ? `${item.name} (${packaging})` : item.name
}
