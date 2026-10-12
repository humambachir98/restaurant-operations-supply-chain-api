import { todayInBerlin } from './format.js'

/** The Active View / Monthly Archive switch shown under each page header. */
export const VIEW_OPTIONS = [
  { value: 'active', label: 'Active View' },
  { value: 'archive', label: 'Monthly Archive' },
]

/** Current Berlin month as "YYYY-MM", the archive's starting point. */
export const currentMonth = () => todayInBerlin().slice(0, 7)
