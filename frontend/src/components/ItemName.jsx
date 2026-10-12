import { packagingLabel } from '../format.js'

/** An item's name followed by its packaging, e.g. "Whopper Patties (Carton: 48 | Sub: 12)". */
export default function ItemName({ item, name = item?.name }) {
  const packaging = packagingLabel(item)
  return (
    <>
      {name}
      {packaging && <span className="ml-1.5 whitespace-nowrap text-xs font-normal text-slate-400">({packaging})</span>}
    </>
  )
}
