import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'

/** A native <dialog>: focus is trapped, Escape and backdrop clicks call onClose.
 * The element marked `data-autofocus` gets focus each time it opens. */
export default function Modal({ open, onClose, title, children, footer }) {
  const ref = useRef(null)

  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) {
      dialog.showModal()
      dialog.querySelector('[data-autofocus]')?.focus()
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="modal-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-2xl bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-900/40 backdrop:backdrop-blur-sm"
    >
      <div className="flex max-h-[80vh] flex-col">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 id="modal-title" className="font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="border-t border-slate-200 px-5 py-3">{footer}</div>}
      </div>
    </dialog>
  )
}
