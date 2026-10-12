import type { ReactNode } from 'react'
import { CircleNotch, WarningCircle } from '@phosphor-icons/react'

/** Etats de liste partages : chargement, erreur, vide. */
export function Loading() {
  return (
    <div className="card flex h-48 items-center justify-center text-muted">
      <CircleNotch size={22} className="animate-spin" />
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="card flex h-48 flex-col items-center justify-center gap-3 text-center">
      <WarningCircle size={28} className="text-error" />
      <div className="text-[13px] text-muted">Impossible de charger les donnees : {error.message}</div>
      <button type="button" className="btn btn-ghost" onClick={onRetry}>
        Reessayer
      </button>
    </div>
  )
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex h-48 flex-col items-center justify-center gap-3 text-center">
      <div className="text-[13px] text-muted">{children}</div>
      {action}
    </div>
  )
}
