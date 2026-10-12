import { FileDown, Loader2 } from 'lucide-react'
import { useState } from 'react'

/** "Download PDF Checklist": runs `onDownload` (async) and shows progress / failure. */
export default function PdfButton({ onDownload, disabled }) {
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  async function click() {
    setBusy(true)
    setFailed(false)
    try {
      await onDownload()
    } catch (err) {
      console.error(err)
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      {failed && <span className="text-sm text-red-700">Couldn&apos;t create the PDF.</span>}
      <button
        type="button"
        onClick={click}
        disabled={disabled || busy}
        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-50"
      >
        {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <FileDown className="size-4" aria-hidden="true" />}
        Download PDF Checklist
      </button>
    </span>
  )
}
