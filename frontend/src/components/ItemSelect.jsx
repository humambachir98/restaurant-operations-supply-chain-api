export const fieldClass =
  'mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 disabled:bg-slate-50 disabled:text-slate-400'

/** A labelled <select> of inventory items; `describe(item)` adds detail after the name. */
export default function ItemSelect({ label = 'Item', items, value, onChange, describe = (item) => item.unit }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={!items?.length} className={fieldClass}>
        <option value="">{items === null ? 'Loading…' : items.length ? 'Select an item' : 'No items'}</option>
        {items?.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name} ({describe(item)})
          </option>
        ))}
      </select>
    </label>
  )
}
