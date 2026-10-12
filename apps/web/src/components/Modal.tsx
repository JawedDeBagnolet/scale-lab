import { useEffect, type ReactNode } from 'react'
import { X } from '@phosphor-icons/react'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: number
}

export default function Modal({ title, onClose, children, footer, width = 720 }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="glass flex max-h-full flex-col rounded-3xl shadow-2xl"
        style={{ width }}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-line px-6 py-4">
          <h2 className="text-base font-bold">{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer && (
          <div className="flex shrink-0 justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>
        )}
      </div>
    </div>
  )
}
