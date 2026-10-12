import { CheckCircle, WarningCircle } from '@phosphor-icons/react'
import { useToasts } from '../stores/toast'

export default function Toaster() {
  const { toasts, dismiss } = useToasts()
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <button
          key={t.id}
          onClick={() => dismiss(t.id)}
          className="glass flex max-w-sm items-center gap-2.5 rounded-xl px-4 py-3 text-left text-[13px] font-medium"
        >
          {t.kind === 'success' ? (
            <CheckCircle size={18} className="shrink-0 text-success" />
          ) : (
            <WarningCircle size={18} className="shrink-0 text-error" />
          )}
          {t.message}
        </button>
      ))}
    </div>
  )
}
