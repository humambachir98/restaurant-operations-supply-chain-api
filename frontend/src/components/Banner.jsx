import { CheckCircle2, X, XCircle } from 'lucide-react'

const TONES = {
  success: { className: 'border-emerald-200 bg-emerald-50 text-emerald-800', Icon: CheckCircle2, role: 'status' },
  error: { className: 'border-red-200 bg-red-50 text-red-800', Icon: XCircle, role: 'alert' },
}

export default function Banner({ tone, title, children, onDismiss, className = 'mt-6' }) {
  const { className: toneClass, Icon, role } = TONES[tone]
  return (
    <div role={role} className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${toneClass} ${className}`}>
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        {children && <p className="mt-1">{children}</p>}
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="rounded p-0.5 opacity-70 hover:opacity-100" aria-label="Dismiss">
          <X className="size-4" />
        </button>
      )}
    </div>
  )
}
