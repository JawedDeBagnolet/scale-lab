import type { CompteStatus } from '../../types/compte'

export const STATUS_LABELS: Record<CompteStatus, string> = {
  ok: 'OK',
  session: 'Session expiree',
  error: 'Erreur',
  suspendu: 'Suspendu',
}

export const STATUS_COLORS: Record<CompteStatus, string> = {
  ok: 'var(--success)',
  session: 'var(--warning)',
  error: 'var(--error)',
  suspendu: 'var(--error)',
}
